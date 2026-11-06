# Changelog

## [2.0.2](https://github.com/ZeitOnline/celery_redis_prometheus/compare/2.0.1...2.0.2) (2026-11-06)


### Maintenance

* **deps:** lock file maintenance (uv) ([#17](https://github.com/ZeitOnline/celery_redis_prometheus/issues/17)) ([50b5282](https://github.com/ZeitOnline/celery_redis_prometheus/commit/50b5282179b5286b1bfb6de659a2587990eedef0))
* **deps:** lock file maintenance (uv) ([#22](https://github.com/ZeitOnline/celery_redis_prometheus/issues/22)) ([b954d99](https://github.com/ZeitOnline/celery_redis_prometheus/commit/b954d99d3c701127576fbb63f1d6b3d39615b0e2))
* **deps:** lock file maintenance (uv) ([#23](https://github.com/ZeitOnline/celery_redis_prometheus/issues/23)) ([2f39e8a](https://github.com/ZeitOnline/celery_redis_prometheus/commit/2f39e8a14fdf41f0a0d57582f253edaf2c122c89))
* **deps:** lock file maintenance (uv) ([#24](https://github.com/ZeitOnline/celery_redis_prometheus/issues/24)) ([76def0b](https://github.com/ZeitOnline/celery_redis_prometheus/commit/76def0b41bad1c52050d1c585afcda08df3adfda))
* **deps:** lock file maintenance (uv) ([#25](https://github.com/ZeitOnline/celery_redis_prometheus/issues/25)) ([faacaeb](https://github.com/ZeitOnline/celery_redis_prometheus/commit/faacaeb9c641fb9f3257addf86fd15dcdeb392c5))
* **deps:** update actions/setup-python action to v7.1.0 ([#20](https://github.com/ZeitOnline/celery_redis_prometheus/issues/20)) ([ef9bcbf](https://github.com/ZeitOnline/celery_redis_prometheus/commit/ef9bcbf92b1f1e5bcde09e643f78b0f2e609c6e3))
* **deps:** update zeitonline/gh-action-workflows action to 4.9.0 ([#21](https://github.com/ZeitOnline/celery_redis_prometheus/issues/21)) ([9382ab8](https://github.com/ZeitOnline/celery_redis_prometheus/commit/9382ab852a0b1ce5ba11252c9784aceebab56dc4))

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
