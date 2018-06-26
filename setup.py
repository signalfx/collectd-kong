#!/usr/bin/env python
from setuptools import setup, find_packages


version = '0.0.2'


setup(name='collectd-kong',
      version=version,
      author='Ryan Fitzpatrick',
      author_email='rmfitzpatrick@signalfx.com',
      description='collectd Kong SFx plugin',
      packages=find_packages())
