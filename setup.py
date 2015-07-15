# -*- coding: utf-8 -*-

import setuptools
import os

# for some reason os gets munged after this point on Windows, so compute it here.
readme_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md")

setuptools.setup(
    name="nion.ui",
    version="0.0.1",
    long_description=open(readme_path).read(),
    packages=setuptools.find_packages(exclude=['contrib', 'docs', 'tests*']),
    install_requires=['scipy', 'numpy'],
    classifiers=[
        "Development Status :: 2 - Pre-Alpha"
    ],
    include_package_data=True,
    package_data={
        'nion.ui': ['*.html'],
    },
    test_suite="nion.ui.test"
)
