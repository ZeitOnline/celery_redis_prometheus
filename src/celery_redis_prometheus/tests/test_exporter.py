import json
import threading
import unittest.mock

import kombu
import prometheus_client
import pytest

import celery_redis_prometheus.exporter

from . import conftest


def test_collects_task_events(celery_worker):
    receiver = celery_redis_prometheus.exporter.CeleryEventReceiver(conftest.CELERY)
    # 3 = recived + started + succeeded
    thread = threading.Thread(target=lambda: receiver.capture(limit=3))
    thread.start()
    conftest.celery_ping.delay().get()
    thread.join()
    data = celery_redis_prometheus.exporter.STATS['tasks'].collect()
    item = [x for x in data[0].samples if x.labels.get('state', '') == 'succeeded']
    assert item[0].value == 1


def test_sets_separate_state_for_retry_failed(celery_worker):
    receiver = celery_redis_prometheus.exporter.CeleryEventReceiver(conftest.CELERY)
    # 6 = received + started + retry + received + started + failed
    thread = threading.Thread(target=lambda: receiver.capture(limit=6))
    thread.start()
    with pytest.raises(Exception):
        conftest.provoke_retry.delay().get()
    thread.join()
    data = celery_redis_prometheus.exporter.STATS['tasks'].collect()
    item = [x for x in data[0].samples if x.labels.get('state', '') == 'retries-exceeded']
    assert item[0].value == 1


def redis_app(*results):
    """Returns a mock app whose redis pipeline answers each scrape with the
    next of `results`: `[llen per queue..., hvals('unacked')]`.

    The collector reads them via `with app.connection() as connection:` and
    `connection.channel().client.pipeline(...)`.
    """
    pipe = unittest.mock.Mock()
    pipe.execute.side_effect = [list(x) for x in results]
    connection = unittest.mock.MagicMock()
    connection.__enter__.return_value = connection
    connection.channel.return_value.client.pipeline.return_value = pipe
    app = unittest.mock.Mock()
    app.connection.return_value = connection
    app.conf = {'task_queues': [kombu.Queue('default'), kombu.Queue('other')]}
    return app


def broken_app(**conf):
    app = unittest.mock.MagicMock()
    app.conf = {'task_queues': [kombu.Queue('default')], **conf}
    app.connection.side_effect = ConnectionError('broker down')
    return app


def registry_with_queue_metrics(app):
    registry = prometheus_client.CollectorRegistry(auto_describe=True)
    registry.register(celery_redis_prometheus.exporter.QueueLengthCollector(app))
    return registry


def unacked(queue):
    return json.dumps([{}, '', queue]).encode('utf-8')


def scrape(registry):
    return {
        (sample.name, tuple(sample.labels.values())): sample.value
        for metric in registry.collect()
        for sample in metric.samples
    }


def test_adds_unacked_tasks_to_queue_length():
    app = redis_app([3, 0, [unacked('default'), unacked('default')]])
    assert scrape(registry_with_queue_metrics(app)) == {
        ('celery_queue_length', ('default',)): 5,
        ('celery_queue_length', ('other',)): 0,
    }


def test_reads_queue_lengths_on_each_scrape_only():
    app = redis_app([1, 0, []], [2, 0, []])
    registry = registry_with_queue_metrics(app)
    app.connection.assert_not_called()

    assert registry.get_sample_value('celery_queue_length', {'queue': 'default'}) == 1
    assert registry.get_sample_value('celery_queue_length', {'queue': 'default'}) == 2


def test_failed_read_leaves_out_queue_lengths():
    assert scrape(registry_with_queue_metrics(broken_app())) == {}


def test_recovers_after_failed_read():
    app = redis_app([1, 0, []])
    registry = registry_with_queue_metrics(app)
    app.connection.side_effect = [ConnectionError('broker down'), app.connection.return_value]

    assert registry.get_sample_value('celery_queue_length', {'queue': 'default'}) is None
    assert registry.get_sample_value('celery_queue_length', {'queue': 'default'}) == 1


def test_socket_configuration_set_by_default():
    app = broken_app()
    scrape(registry_with_queue_metrics(app))

    options = app.connection.call_args.kwargs['transport_options']
    assert options == {'socket_timeout': 3, 'socket_connect_timeout': 3}


def test_does_not_retry_connecting():
    app = redis_app([1, 0, []])
    scrape(registry_with_queue_metrics(app))

    connection = app.connection.return_value
    connection.ensure_connection.assert_called_once_with(max_retries=0)


def test_configured_transport_options_override_default_timeout():
    app = broken_app(broker_transport_options={'socket_timeout': 2})
    scrape(registry_with_queue_metrics(app))

    options = app.connection.call_args.kwargs['transport_options']
    assert options == {'socket_timeout': 2, 'socket_connect_timeout': 3}


def test_broker_outage_does_not_impact_task_metrics():
    collector = celery_redis_prometheus.exporter.QueueLengthCollector(broken_app())
    # main() registers on the global registry, next to the event metrics.
    registry = prometheus_client.REGISTRY
    registry.register(collector)
    try:
        STATS = celery_redis_prometheus.exporter.STATS
        STATS['tasks'].labels('coexist', 'succeeded').inc()

        labels = {'queue': 'coexist', 'state': 'succeeded'}
        assert registry.get_sample_value('celery_tasks_total', labels) == 1
        assert registry.get_sample_value('celery_queue_length', {'queue': 'default'}) is None
    finally:
        registry.unregister(collector)
