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
    thread = threading.Thread(target=lambda: receiver(limit=3))
    thread.start()
    conftest.celery_ping.delay().get()
    thread.join()
    data = celery_redis_prometheus.exporter.STATS['tasks'].collect()
    item = [x for x in data[0].samples if x.labels.get('state', '') == 'succeeded']
    assert item[0].value == 1


def test_sets_separate_state_for_retry_failed(celery_worker):
    receiver = celery_redis_prometheus.exporter.CeleryEventReceiver(conftest.CELERY)
    # 6 = received + started + retry + received + started + failed
    thread = threading.Thread(target=lambda: receiver(limit=6))
    thread.start()
    with pytest.raises(Exception):
        conftest.provoke_retry.delay().get()
    thread.join()
    data = celery_redis_prometheus.exporter.STATS['tasks'].collect()
    item = [x for x in data[0].samples if x.labels.get('state', '') == 'retries-exceeded']
    assert item[0].value == 1


def queue_metrics(app):
    registry = prometheus_client.CollectorRegistry(auto_describe=True)
    registry.register(celery_redis_prometheus.exporter.QueueLengthCollector(app))
    return registry


def test_reads_queue_lengths_on_scrape():
    # The collector reads the queue lengths via
    # `with app.connection() as connection:` and
    # `connection.channel().client.pipeline(...)`, so hand it a pipeline
    # whose result we control.
    pipe = unittest.mock.Mock()
    # Every scrape gets a fresh result, like from real redis.
    pipe.execute.side_effect = lambda: [3, [b'[{}, "", "default"]']]
    connection = unittest.mock.MagicMock()
    connection.__enter__.return_value = connection
    connection.channel.return_value.client.pipeline.return_value = pipe
    app = unittest.mock.Mock()
    app.connection.return_value = connection
    app.conf = {'task_queues': [kombu.Queue('default')]}

    registry = queue_metrics(app)
    app.connection.assert_not_called()

    assert registry.get_sample_value('celery_queue_length', {'queue': 'default'}) == 4
    assert registry.get_sample_value('celery_queue_length_up') == 1
    pipe.llen.assert_called_with('default')
    pipe.hvals.assert_called_with('unacked')
    options = app.connection.call_args.kwargs['transport_options']
    assert options['socket_timeout'] == 5


def test_failed_queue_length_check_reports_down_without_lengths():
    app = unittest.mock.MagicMock()
    app.connection.side_effect = ConnectionError('broker down')

    registry = queue_metrics(app)

    assert registry.get_sample_value('celery_queue_length_up') == 0
    assert registry.get_sample_value('celery_queue_length', {'queue': 'default'}) is None


def test_configured_transport_options_override_default_timeout():
    app = unittest.mock.MagicMock()
    app.conf = {'broker_transport_options': {'socket_timeout': 2}}
    app.connection.side_effect = ConnectionError('broker down')

    queue_metrics(app).get_sample_value('celery_queue_length_up')

    options = app.connection.call_args.kwargs['transport_options']
    assert options == {'socket_timeout': 2, 'socket_connect_timeout': 5}
