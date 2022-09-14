from functools import wraps
import celery.bin.base
import click
import collections
import json
import logging
import prometheus_client
import _thread
import threading
import time


log = logging.getLogger(__name__)


# Remove any `process_` and `python_` metrics, since we're proxying for the
# whole celery machinery, but those would only be about this process.
for collector in list(prometheus_client.REGISTRY._collector_to_names):
    prometheus_client.REGISTRY.unregister(collector)


STATS = {
    'tasks': prometheus_client.Counter(
        'celery_tasks_total', 'Number of tasks', ['queue', 'state']),
    'queuetime': prometheus_client.Histogram(
        'celery_task_queuetime_seconds', 'Task queue wait time'),
    'runtime': prometheus_client.Histogram(
        'celery_task_runtime_seconds', 'Task runtime'),
    'queues': prometheus_client.Gauge(
        'celery_queue_length', 'Queue length', ['queue'])
}


@click.command(name='prometheus', cls=celery.bin.base.CeleryCommand)
@click.option('--host', default='0.0.0.0', help='Listen host')
@click.option('--port', default=9691, help='Listen port')
@click.option(
    '--queuelength-interval', default=0,
    help='Check queue lengths every x seconds (0=disabled)')
@click.option('--verbose', is_flag=True, help='Enable debug logging')
@click.pass_context
def main(ctx, host, port, queuelength_interval, verbose):
    app = ctx.obj.app
    app.log.setup(logging.DEBUG if verbose else logging.INFO)

    queuelength_thread = None
    if queuelength_interval:
        queuelength_thread = QueueLengthMonitor(app, queuelength_interval)
        queuelength_thread.start()

    receiver = CeleryEventReceiver(app)
    prometheus_client.start_http_server(port, host)
    log.info('Listening on %s:%s', host, port)

    try_interval = 1
    while True:
        try:
            try_interval *= 2
            receiver()
            try_interval = 1
        except (KeyboardInterrupt, SystemExit):
            log.info('Exiting')
            if queuelength_thread:
                queuelength_thread.stop()
            _thread.interrupt_main()
            break
        except Exception as e:
            log.error(
                'Failed to capture events: "%s", trying again in %s seconds.',
                e, try_interval, exc_info=True)
            time.sleep(try_interval)


def task_handler(fn):
    @wraps(fn)
    def wrapper(self, event):
        self.state.event(event)
        task = self.state.tasks.get(event['uuid'])
        return fn(self, event, task)
    return wrapper


class CeleryEventReceiver:

    def __init__(self, app):
        self.app = app

    @task_handler
    def on_task_started(self, event, task):
        log.debug('Started %s', task)
        STATS['tasks'].labels(task.routing_key, 'started').inc()
        if task.sent:
            STATS['queuetime'].observe(time.time() - task.sent)

    @task_handler
    def on_task_succeeded(self, event, task):
        log.debug('Succeeded %s', task)
        STATS['tasks'].labels(task.routing_key, 'succeeded').inc()
        self.record_runtime(task)

    def record_runtime(self, task):
        if task is not None and task.runtime is not None:
            STATS['runtime'].observe(task.runtime)

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

    def __call__(self, *args, **kw):
        self.state = self.app.events.State()
        kw.setdefault('wakeup', False)

        with self.app.connection() as connection:
            recv = self.app.events.Receiver(connection, handlers={
                'task-started': self.on_task_started,
                'task-succeeded': self.on_task_succeeded,
                'task-failed': self.on_task_failed,
                'task-retried': self.on_task_retried,
                '*': self.state.event,
            })
            recv.capture(*args, **kw)


class QueueLengthMonitor(threading.Thread):

    def __init__(self, app, interval):
        super().__init__()
        self.app = app
        self.interval = interval
        self.running = True

    def run(self):
        while self.running:
            try:
                lengths = collections.Counter()

                with self.app.connection() as connection:
                    pipe = connection.channel().client.pipeline(
                        transaction=False)
                    for queue in self.app.conf['task_queues']:
                        # Not claimed by any worker yet
                        pipe.llen(queue.name)
                    # Claimed by worker but not acked/processed yet
                    pipe.hvals('unacked')

                    result = pipe.execute()

                unacked = result.pop()
                for task in unacked:
                    data = json.loads(task.decode('utf-8'))
                    queue = data[-1]
                    lengths[queue] += 1

                for llen, queue in zip(result, self.app.conf['task_queues']):
                    lengths[queue.name] += llen

                for queue, length in lengths.items():
                    STATS['queues'].labels(queue).set(length)

                time.sleep(self.interval)
            except Exception:
                log.error(
                    'Uncaught exception, preventing thread from crashing.',
                    exc_info=True)

    def stop(self):
        self.running = False
