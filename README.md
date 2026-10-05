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

If you pass `--queuelength-interval=x` (any x > 0), the queue lengths are read from the broker on each scrape (NOTE: this only works with redis as the broker), resulting in these additional metrics:

* `celery_queue_length{queue="..."}`, gauge
* `celery_queue_length_up`, gauge: 1 if the queue lengths could be read, 0 otherwise.
  `celery_queue_length` is left out while the broker cannot be reached, so alert on `celery_queue_length_up == 0`.
  Reading times out after 5 seconds; set `socket_timeout`/`socket_connect_timeout` in `broker_transport_options` to change that.

## Run tests

With `bin/test` wrapper script (or `uv run pytest`).
