import threading
import time
import unittest.mock

import kombu
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


# Patch time.sleep so that we can reliably interrupt monitor.run()
def run_monitor_once(monkeypatch, app):
    monitor = celery_redis_prometheus.exporter.QueueLengthMonitor(app, 7)
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        monitor.stop()

    monkeypatch.setattr(celery_redis_prometheus.exporter.time, 'sleep', sleep)
    monitor.run()
    return sleeps


def last_queue_check():
    data = celery_redis_prometheus.exporter.STATS['queues_checked'].collect()
    return data[0].samples[0].value


def test_queue_length_check_records_success_time(monkeypatch):
    # run() reads the queue lengths via
    # `with app.connection() as connection:` and
    # `connection.channel().client.pipeline(...)`, so hand it a pipeline
    # whose result we control.
    pipe = unittest.mock.Mock()
    pipe.execute.return_value = [3, [b'[{}, "", "default"]']]
    connection = unittest.mock.MagicMock()
    connection.__enter__.return_value = connection
    connection.channel.return_value.client.pipeline.return_value = pipe
    app = unittest.mock.Mock()
    app.connection.return_value = connection
    app.conf = {'task_queues': [kombu.Queue('default')]}
    before = time.time()

    assert run_monitor_once(monkeypatch, app) == [7]
    pipe.llen.assert_called_once_with('default')
    pipe.hvals.assert_called_once_with('unacked')
    data = celery_redis_prometheus.exporter.STATS['queues'].collect()
    lengths = {x.labels['queue']: x.value for x in data[0].samples}
    assert lengths['default'] == 4
    assert last_queue_check() >= before


def test_failed_queue_length_check_waits_and_keeps_success_time(monkeypatch):
    app = unittest.mock.MagicMock()
    app.connection.side_effect = ConnectionError('broker down')
    checked = last_queue_check()

    assert run_monitor_once(monkeypatch, app) == [7]
    assert last_queue_check() == checked
