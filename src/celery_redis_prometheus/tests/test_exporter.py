from . import conftest
import celery_redis_prometheus.exporter
import pytest
import threading


def test_collects_task_events(celery_worker):
    receiver = celery_redis_prometheus.exporter.CeleryEventReceiver(
        conftest.CELERY)
    # 3 = recived + started + succeeded
    thread = threading.Thread(target=lambda: receiver(limit=3))
    thread.start()
    conftest.celery_ping.delay().get()
    thread.join()
    data = celery_redis_prometheus.exporter.STATS['tasks'].collect()
    item = [x for x in data[0].samples
            if x.labels.get('state', '') == 'succeeded']
    assert item[0].value == 1


def test_sets_separate_state_for_retry_failed(celery_worker):
    receiver = celery_redis_prometheus.exporter.CeleryEventReceiver(
        conftest.CELERY)
    # 6 = received + started + retry + received + started + failed
    thread = threading.Thread(target=lambda: receiver(limit=6))
    thread.start()
    with pytest.raises(Exception):
        conftest.provoke_retry.delay().get()
    thread.join()
    data = celery_redis_prometheus.exporter.STATS['tasks'].collect()
    item = [x for x in data[0].samples
            if x.labels.get('state', '') == 'retries-exceeded']
    assert item[0].value == 1
