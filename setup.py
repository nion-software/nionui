# -*- coding: utf-8 -*-

import setuptools
import os

# for some reason os gets munged after this point on Windows, so compute it here.
readme_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md")

setuptools.setup(
    name="nionui",
    version="0.0.1",
    author="Nion Software",
    author_email="swift@nion.com",
    description="Nion UI framework.",
    long_description=open(readme_path).read(),
    url="https://github.com/nion-software/nionui",
    packages=["nion.ui", "nionui_app.none"],
    install_requires=['scipy', 'numpy', 'nionutils'],
    license='Apache 2.0',
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.5",
    ],
    include_package_data=True,
    package_data={
        'nion.ui': ['*.html'],
    },
    test_suite="nion.ui.test"
)
