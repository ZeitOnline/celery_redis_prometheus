from setuptools import setup, find_packages


setup(
    name='celery_redis_prometheus',
    version='1.3.0',
    author='Zeit Online',
    author_email='zon-backend@zeit.de',
    url='https://github.com/zeitonline/celery_redis_prometheus',
    description="Exports task execution metrics in Prometheus format",
    long_description='\n\n'.join(
        open(x).read() for x in ['README.rst', 'CHANGES.txt']),
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    zip_safe=False,
    license='BSD',
    install_requires=[
        'celery >= 5.0.0.dev0',
        'click',
        'prometheus_client',
        'setuptools',
    ],
    extras_require={'test': [
        'pytest',
    ]},
    entry_points={
        'celery.commands': [
            'prometheus = celery_redis_prometheus.exporter:main',
        ]
    }
)
