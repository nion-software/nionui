# -*- coding: utf-8 -*-

import setuptools
import os

# for some reason os gets munged after this point on Windows, so compute it here.
readme_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md")

setuptools.setup(
    name="nionui",
    version="0.3.27",
    author="Nion Software",
    author_email="swift@nion.com",
    description="Nion UI framework.",
    long_description=open(readme_path).read(),
    url="https://github.com/nion-software/nionui",
    packages=["nion.ui", "nion.ui.test", "nionui_app.none", "nionui_app.nionui_examples.hello_world", "nionui_app.nionui_examples.ui_demo"],
    install_requires=['numpy', 'nionutils>=0.3.19', 'imageio'],
    license='Apache 2.0',
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.6",
    ],
    package_data={
        'nion.ui': ["resources/*"],
    },
    data_files=[
        ('', ["LICENSE.txt"]),
    ],
    test_suite="nion.ui.test",
    entry_points={
        'console_scripts': [
            'nionui=nion.ui.command:main',
            ],
        },
)
