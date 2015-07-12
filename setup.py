#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from setuptools import setup, find_packages

# Utility function to read the README file.

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "nion.ui",
    version = "0.0.1",
    long_description=read('README.md'),
    packages=find_packages(exclude=['contrib', 'docs', 'tests*']),
    install_requires=['scipy', 'numpy'],
    classifiers=[
        "Development Status :: 2 - Pre-Alpha"
    ],
    include_package_data = True,
    package_data = {
        'nion.ui': ['*.html'],
    },
    test_suite="nion.ui.test"
)
