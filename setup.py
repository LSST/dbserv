from setuptools import setup

setup(
    name='dbserv',
    package_dir={'lsst': 'python/lsst'},
    package_data={'lsst': ['dax/dbserv/templates/*', 'dax/dbserv/static/*']},
    packages=['lsst', 'lsst.dax.dbserv', 'lsst.dax.dbserv.compat'],
    zip_safe=False,
    use_scm_version=True
)
