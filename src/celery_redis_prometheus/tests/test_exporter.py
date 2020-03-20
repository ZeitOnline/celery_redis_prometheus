from . import conftest
import celery_redis_prometheus.exporter
import threading


def test_collects_task_events(celery_worker):
    receiver = celery_redis_prometheus.exporter.CeleryEventReceiver(
        conftest.CELERY)
    # X + task started + task succeeded
    thread = threading.Thread(target=lambda: receiver(limit=3))
    thread.start()
    conftest.celery_ping.delay().get()
    thread.join()
    data = celery_redis_prometheus.exporter.STATS['tasks'].collect()
    item = [x for x in data[0].samples if x.labels == {'state': 'succeeded'}]
    assert item[0].value == 1
