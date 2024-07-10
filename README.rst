Introduction
============
This is a Python UI library that can run with a pyside6 or nionui-tool backend.

Installation
============
Install this library using pip or conda.

.. code-block::

    pip install nionui

Install using PySide6 or nionui-tool backend.

.. code-block::

    pip install nionui-tool

.. code-block::

    pip install pyside6

Usage
=====
This UI library supports an application.

To run the example application, use the following command with the appropriate application identifier. It will launch using either the nionui-tool or pyside6 backend, depending on which is installed. If both are installed, it will use the nionui-tool.

.. code-block::

    python -m nionui <application_identifier>

To run the UI demo app, use the following command (application identifier is 'nionui_examples.ui_demo'):

.. code-block::

    python -m nionui nionui_examples.ui_demo
