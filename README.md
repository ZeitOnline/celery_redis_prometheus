# celery_redis_prometheus

Exports task execution metrics in Prometheus format: how many tasks were started
and have completed successfully or with failure, and how many tasks are still in
the queues (supported only for broker redis).

Inspired by <https://gitlab.com/kalibrr/celery-prometheus>


## Usage

### Start HTTP service

Start the HTTP server like this:

```
$ bin/celery prometheus --host=127.0.0.1 --port=9691
```


### Configure Prometheus

```
scrape_configs:
  - job_name: 'celery'
    static_configs:
      - targets: ['localhost:9691']
```

We export the following metrics:

* `celery_tasks_total{state="started|succeeded|failed|retried|retries-exceeded", queue="..."}`, counter
* `celery_task_queuetime_seconds{queue}`, histogram (only if `task_send_sent_event` is enabled in Celery)
* `celery_task_runtime_seconds{queue}`, histogram

If you pass `--queuelength-interval=x` (any x > 0), the queue lengths are read from the broker on each scrape (NOTE: this only works with redis as the broker), resulting in this additional metric:

* `celery_queue_length{queue="..."}`, gauge

While the broker cannot be reached, `celery_queue_length` is left out.
So an alert like `celery_queue_length > 100` silently stops firing;
add one that fires when the metric is missing.
With a single exporter per alert selector, `absent()` does that:

```yaml
- alert: CeleryQueueLengthMissing
  expr: absent(celery_queue_length{namespace="myapp"})
  for: 5m
```

`absent()` only fires if *no* series matches the selector at all.
If the selector covers several exporters (e.g. one per broker), 
one of them failing goes unnoticed as long as another still reports.
Compare against the `up` series Prometheus records for each scrape target instead, 
which yields one alert per exporter that is down or cannot read its broker:

```yaml
- alert: CeleryQueueLengthMissing
  expr: up{job="myapp/celery-metrics"} unless on(namespace, pod) celery_queue_length
  for: 5m
```

The `up` selector must match only exporters started with `--queuelength-interval`, and `on(...)`
must name labels that identify the exporter on both sides.

## Run tests

With `bin/test` wrapper script (or `uv run pytest`).
