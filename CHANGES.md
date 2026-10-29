# Changelog

## [2.0.1](https://github.com/ZeitOnline/celery_redis_prometheus/compare/2.0.0...2.0.1) (2026-10-29)


### Maintenance

* **deps:** update actions/setup-python digest to 6d4fd22 ([#12](https://github.com/ZeitOnline/celery_redis_prometheus/issues/12)) ([975f9f4](https://github.com/ZeitOnline/celery_redis_prometheus/commit/975f9f4ba31d076d63e96d90db118db9cd1dd721))
* enable Renovate with the shared eng presets ([b94e319](https://github.com/ZeitOnline/celery_redis_prometheus/commit/b94e31958ec49efc88cfbad90fe493f03e98d288))
* enable Renovate with the shared eng presets ([fce3373](https://github.com/ZeitOnline/celery_redis_prometheus/commit/fce337307502ce22cacbe62ba890821700c5c5e9))
* release with Release Please via the shared pypi-release workflow ([b8423b5](https://github.com/ZeitOnline/celery_redis_prometheus/commit/b8423b57b5391f2adc3d97e38347e669597da253))
* release with Release Please via the shared pypi-release workflow ([8ff0ade](https://github.com/ZeitOnline/celery_redis_prometheus/commit/8ff0ade6bf8644e41f4224d1eb504de179372316))

## 2.0.0 (2026-10-12)

### 

- Give up reading queue lengths on a hanging broker after 3 seconds per connect, handshake and query (so about 9 seconds at worst), to still answer within the default 10 second scrape timeout. Configurable via `socket_timeout`/`socket_connect_timeout` in `broker_transport_options`
- Read queue lengths from the broker on each scrape instead of polling them in a background thread. While the broker cannot be reached, `celery_queue_length` is left out instead of keeping stale values; see the README on how to alert on that
- Replace `--queuelength-interval=x` with the flag `--queue-length`. The old option is rejected, so update the exporter arguments when upgrading


## 2.0.0 (unreleased)

- Nothing changed yet.


## 1.5.2 (2026-07-27)

- Remove unused `setuptools` dependency


## 1.5.1 (2023-10-27)

- Fix brown-bag release


## 1.5.0 (2023-10-27)

- Be explicit about unregistering default collectors


## 1.4.0 (2022-10-28)

- Add `queue` label to task_queuetime and task_runtime metrics


## 1.3.0 (2022-09-14)

- Add `queue` label to `celery_tasks_total` metric
- Add separate state `retries-exceeded` (previously used `failed`)


## 1.2.0 (2022-06-23)

- Update to celery-5.x


## 1.1.1 (2020-03-20)

- Fix py2 class syntax issues


## 1.1.0 (2020-03-20)

- Make py2 compatible.


## 1.0.0 (2020-03-20)

- Initial release
