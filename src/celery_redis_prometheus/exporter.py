from functools import wraps
import collections
import json
import logging
import time

import celery.bin.base
import click
import prometheus_client
import prometheus_client.core
import prometheus_client.registry


log = logging.getLogger(__name__)


# Remove any `process_` and `python_` metrics, since we're proxying for the
# whole celery machinery, but those would only be about this process.
prometheus_client.REGISTRY.unregister(prometheus_client.GC_COLLECTOR)
prometheus_client.REGISTRY.unregister(prometheus_client.PLATFORM_COLLECTOR)
prometheus_client.REGISTRY.unregister(prometheus_client.PROCESS_COLLECTOR)


# Creating a metric registers it with prometheus_client's default REGISTRY,
# which the HTTP server started in main() renders anew on each request. So
# updating these is all it takes to export a new value.
STATS = {
    'tasks': prometheus_client.Counter('celery_tasks_total', 'Number of tasks', ['queue', 'state']),
    'queuetime': prometheus_client.Histogram(
        'celery_task_queuetime_seconds', 'Task queue wait time', ['queue']
    ),
    'runtime': prometheus_client.Histogram(
        'celery_task_runtime_seconds', 'Task runtime', ['queue']
    ),
}


@click.command(name='prometheus', cls=celery.bin.base.CeleryCommand)
@click.option('--host', default='0.0.0.0', help='Listen host')
@click.option('--port', default=9691, help='Listen port')
@click.option(
    '--queuelength-interval',
    default=0,
    help='Export queue lengths if > 0 (0=disabled). They are read on each scrape, '
    'the value itself is only kept for compatibility.',
)
@click.option('--verbose', is_flag=True, help='Enable debug logging')
@click.pass_context
def main(ctx, host, port, queuelength_interval, verbose):
    app = ctx.obj.app
    app.log.setup(logging.DEBUG if verbose else logging.INFO)

    if queuelength_interval:
        prometheus_client.REGISTRY.register(QueueLengthCollector(app))

    # Serves REGISTRY from a daemon thread.
    prometheus_client.start_http_server(port, host)
    log.info('Listening on %s:%s', host, port)

    CeleryEventReceiver(app).run_forever()


def task_handler(fn):
    """Applies the event to the tracked state first, and passes the task it
    belongs to, so handlers see what earlier events said about it (e.g. its
    queue, or when it was sent)."""

    @wraps(fn)
    def wrapper(self, event):
        self.state.event(event)
        task = self.state.tasks.get(event['uuid'])
        return fn(self, event, task)

    return wrapper


class CeleryEventReceiver:
    """Turns the Celery event stream into the metrics in STATS.

    Workers publish an event to the broker for each task state change, if
    they are started with `-E` (or `worker_send_task_events`). We subscribe
    to these and record them in a `celery.events.State`, which collects the
    events of each task. The handlers only update the metrics, Prometheus
    picks up their current values on its next scrape.
    """

    def __init__(self, app):
        self.app = app

    @task_handler
    def on_task_started(self, event, task):
        log.debug('Started %s', task)
        STATS['tasks'].labels(task.routing_key, 'started').inc()
        if task.sent:
            STATS['queuetime'].labels(task.routing_key).observe(time.time() - task.sent)

    @task_handler
    def on_task_succeeded(self, event, task):
        log.debug('Succeeded %s', task)
        STATS['tasks'].labels(task.routing_key, 'succeeded').inc()
        self.record_runtime(task)

    def record_runtime(self, task):
        if task is not None and task.runtime is not None:
            STATS['runtime'].labels(task.routing_key).observe(task.runtime)

    @task_handler
    def on_task_failed(self, event, task):
        log.debug('Failed %s', task)
        state = 'failed'
        exc = event.get('exception', 'Unknown').split('(')[0]
        if exc == 'MaxRetriesExceededError':
            state = 'retries-exceeded'
        STATS['tasks'].labels(task.routing_key, state).inc()
        self.record_runtime(task)

    @task_handler
    def on_task_retried(self, event, task):
        log.debug('Retried %s', task)
        STATS['tasks'].labels(task.routing_key, 'retried').inc()
        self.record_runtime(task)

    def run_forever(self):
        """Captures events until interrupted, reconnecting with a growing
        delay when the broker connection fails."""
        try_interval = 1
        while True:
            try:
                try_interval *= 2
                self.capture()
                try_interval = 1
            except (KeyboardInterrupt, SystemExit):
                log.info('Exiting')
                break
            except Exception as e:
                log.error(
                    'Failed to capture events: "%s", trying again in %s seconds.',
                    e,
                    try_interval,
                    exc_info=True,
                )
                time.sleep(try_interval)

    def capture(self, *args, **kw):
        """Captures events, blocking until `limit` events were handled or
        forever. Arguments are passed to `celery.events.Receiver.capture()`."""
        self.state = self.app.events.State()
        kw.setdefault('wakeup', False)

        with self.app.connection() as connection:
            recv = self.app.events.Receiver(
                connection,
                handlers={
                    'task-started': self.on_task_started,
                    'task-succeeded': self.on_task_succeeded,
                    'task-failed': self.on_task_failed,
                    'task-retried': self.on_task_retried,
                    '*': self.state.event,
                },
            )
            recv.capture(*args, **kw)


class QueueLengthCollector(prometheus_client.registry.Collector):
    """Reads the queue lengths from redis whenever Prometheus scrapes us.

    A failed read leaves out `celery_queue_length` instead of failing the whole
    scrape, so the event metrics are still exported during a broker outage.
    """

    # By default, the broker connection waits forever for a redis that stops
    # answering, but we have to respond within the Prometheus scrape timeout
    # (10s by default). Connecting, the handshake and the query can each take
    # one full timeout, so 3 x 3s at worst.
    TRANSPORT_OPTIONS = {'socket_timeout': 3, 'socket_connect_timeout': 3}

    def __init__(self, app):
        self.app = app

    # Without describe(), register() would call collect() and thus hit redis.
    def describe(self):
        yield self._lengths_metric()

    def collect(self):
        try:
            lengths = self.queue_lengths()
        except Exception:
            log.error('Failed to read queue lengths', exc_info=True)
            return
        metric = self._lengths_metric()
        for queue, length in lengths.items():
            metric.add_metric([queue], length)
        yield metric

    def queue_lengths(self):
        # Celery puts the options passed here over `broker_transport_options`,
        # so merge ours underneath to let the configured ones win.
        options = dict(
            self.TRANSPORT_OPTIONS, **self.app.conf.get('broker_transport_options') or {}
        )
        queues = self.app.conf['task_queues']
        with self.app.connection(transport_options=options) as connection:
            # channel() would otherwise connect with one retry after sleeping 2s,
            # which doubles the time we hang on an unresponsive broker.
            connection.ensure_connection(max_retries=0)
            pipe = connection.channel().client.pipeline(transaction=False)
            for queue in queues:
                # Not claimed by any worker yet
                pipe.llen(queue.name)
            # Claimed by worker but not acked/processed yet
            pipe.hvals('unacked')
            result = pipe.execute()

        lengths = collections.Counter()
        for task in result.pop():
            data = json.loads(task.decode('utf-8'))
            lengths[data[-1]] += 1
        for llen, queue in zip(result, queues):
            lengths[queue.name] += llen
        return lengths

    def _lengths_metric(self):
        return prometheus_client.core.GaugeMetricFamily(
            'celery_queue_length', 'Queue length', labels=['queue']
        )
