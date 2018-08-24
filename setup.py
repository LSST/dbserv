from setuptools import setup

requires = [
    'flask',
    'mysqlclient'
]

setup(
    name='dbserv',
    version='0.1',
    package_dir={'lsst': 'python/lsst'},
    package_data={'lsst': ['dax/dbserv/templates/*', 'dax/dbserv/static/*']},
    packages=['lsst', 'lsst.dax.dbserv', 'lsst.dax.dbserv.compat'],
    zip_safe=False,
    install_requires=requires
)
