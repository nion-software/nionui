import os
from setuptools import setup, find_packages

# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "nion.ui",
    version = "0.0.1",
    long_description=read('README.md'),
    packages=find_packages(exclude=["*.test", "nion.ui.html"]),
    classifiers=[
        "Development Status :: 2 - Pre-Alpha"
    ],
    include_package_data = True,
    package_data = {
        # If any package contains *.txt or *.rst files, include them:
        'nion.ui': ['*.html'],
    }
)
