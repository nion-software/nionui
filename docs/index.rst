.. include:: defs.rst

Welcome to |ProjectName| documentation!
=======================================
|ProjectName| is a toolkit for building desktop user interfaces (UI) in Python. It includes tools for declarative UI
programming through simple Python dicts. It was primarily created to implement the Nion Swift application.

The toolkit includes a specific backend to work in conjunction with |LauncherName|, which is a high performance Qt-based
UI hosting application. |LauncherName| provides a Python environment in which to run and an API to implement the user
interface exposed by |ProjectName|.

At its base, the toolkit provides a basic application, menu, and window system. The windows are constructed using
widgets, which are standard UI elements such as buttons and text edit fields. The toolkit also provides canvas items,
which are special widgets that can be displayed using explicit drawing commands similar to HTML canvas items.

In addition to the explicit widget and canvas item capabilities, the toolkit provides a declarative UI.

With the declarative features of |ProjectName|, you construct your UI by defining a Python dict which describes your UI
and its connections to Python handlers. |ProjectName| provides functions to help you construct the Python dict quickly
and easily and connect it to your application specific code.

.. todo:: Widgets vs CanvasItems
.. todo:: Application and launcher, nionui_app namespace
.. todo:: args and bootstrap args
.. todo:: DrawingContext
.. todo:: Preferences
.. todo:: User interface (Qt + Test + other)
.. todo:: layout with rows/columns, spacing, stretches
.. todo:: labels
.. todo:: check boxes
.. todo:: combo boxes
.. todo:: bindings
.. todo:: compositions
.. todo:: converters
.. todo:: groups
.. todo:: line edits
.. todo:: progress bars
.. todo:: radio buttons
.. todo:: sliders
.. todo:: stacks
.. todo:: status bar
.. todo:: tabs
.. todo:: windows, modeless dialogs
.. todo:: embedding sub-components
.. todo:: resources

Installation
============

Configuring a Development Environment for Nion UI
-------------------------------------------------

It is recommended to create a Python virtual environment for Nion UI development, either one virtual environment per project or a single virtual environment for all Nion UI development.

For **macOS** and **Linux**, you can create a Python virtual environment using either
`pyenv <https://github.com/pyenv/pyenv>`_ and `pyenv-virtualenv <https://github.com/pyenv/pyenv-virtualenv>`_ or `uv <https://docs.astral.sh/uv/>`_.

For **Windows**, you can create a Python virtual environment using `uv <https://docs.astral.sh/uv/>`_.

Using pyenv (macOS and Linux)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Find the latest version of Python using ``pyenv install --list``. Install the latest version with ``pyenv install <version>``.

Create a new virtual environment with ``pyenv virtualenv <version> <env-name>`` where env-name is the name of your development virtual environment, something like ``nionui-dev``. Activate the environment with ``pyenv activate <env-name>``.

Configure your virtual environment with ``nionui`` and ``nionui-tool`` using pip:

.. code-block:: zsh

    pyenv install 3.13.11
    pyenv virtualenv 3.13.11 nionui-dev
    pyenv activate nionui-dev
    python -m pip install nionui nionui-tool

Using uv (macOS, Windows, and Linux)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Find the latest version of Python by updating uv and listing available versions with ``uv python list``.

Install the latest version of Python using ``uv python install <version>``.

Create a new virtual environment with ``uv venv <env-name>`` where env-name is the name of your development virtual environment, something like ``nionui-dev``. With uv, you can also just run ``uv venv`` to create a virtual environment for the current directory. Activate the environment (see uv documentation).

.. tab-set::

   .. tab-item:: Windows
      :sync: win

      .. code-block:: powershell

         uv python install 3.13.11
         uv venv nionui-dev
         .venv\nionui-dev\Scripts\activate
         python -m pip install nionui nionui-tool

   .. tab-item:: macOS
      :sync: mac

      To install on macOS, run:

      .. code-block:: bash

         uv python install 3.13.11
         uv venv nionui-dev
         source .venv/nionui-dev/bin/activate
         python -m pip install nionui nionui-tool

Running an Application
======================

Run an application using the ``nionui`` command line tool.

You can run a specific single file application using:

.. code-block:: zsh

    nionui my_app.py

You can run an application in your current Python environment by providing the module name:

.. code-block:: zsh

    nionui nionui_app.my_app_module

You can run the examples:

.. code-block:: zsh

    nionui nionui_app.nionui_examples.hello_world
    nionui nionui_app.nionui_examples.ui_demo
    nionui nionui_app.nionui_examples.canvas_demo

Introduction to the Declarative UI
==================================
The declarative features allow you to have a clean separation between the UI and your code for handling the UI.

Put this code into a file named ``hello_world.py`` and then run it using ``nionui hello_world.py``.

.. code-block:: python

    import gettext

    from nion.ui import Application
    from nion.ui import Declarative
    from nion.ui import UserInterface

    _ = gettext.gettext

    class Handler:
        def __init__(self) -> None:
            self.label_item = None
            self.click_count = 0

        def button_clicked(self, widget: UserInterface.PushButtonWidget) -> None:
            self.click_count += 1
            self.label_item.text = _("Clicked") + " " + str(self.click_count)

    def main(args: typing.Any, bootstrap_args: typing.Any) -> None:
        u = Declarative.DeclarativeUI()
        button = u.create_push_button(text=_("Hello World"), on_clicked="button_clicked")
        label = u.create_label(name="label_item", text=_("Not Clicked"))
        column = u.create_column(button, label, spacing=8)
        window = u.create_window(column, title=_("Hello World"), margin=12)
        handler = Handler()
        return Application.run_window(args, bootstrap_args, window, handler)

    if __name__ == "__main__":
        print("This script cannot be run directly. Use the nionui command line tool.")

At the top, a ``Handler`` class is defined which includes a property ``label_item`` and a method ``button_clicked``
which will be connected to the UI. It also includes a property ``click_count`` that will be used separately.

The ``main`` function begins by creating a ``u`` object which will help construct the Python dict representing the
layout.

With the ``u`` object, a ``button`` is declared. The button declares that the ``on_clicked`` event will be connected to
the ``button_clicked`` method of the handler.

Next, a ``label`` is declared. By specifying ``name`` to the label, the declarative UI engine will store the label
widget into the handler when the app is run (the ``label_item`` property in the handler).

Next, a ``column`` is declared with the ``button`` and ``label`` in the column. Both are put into a ``window``
declaration.

Next, an instance of ``Handler`` is created.

Finally, the ``window`` and ``handler`` are passed to ``Application.run_window`` which constructs the window user interface,
connects it to the handler, and presents the user window to the user.

The ``window`` variable is a Python dictionary. It gets connected to the ``Handler`` in the ``Application.run_window``
method. The dictionary looks like this::

    {'content': {'children': [{'on_clicked': 'button_clicked',
                               'text': 'Hello World',
                               'type': 'push_button'},
                              {'name': 'label_item',
                               'text': 'Not Clicked',
                               'type': 'text_label'}],
                 'spacing': 8,
                 'type': 'column'},
     'margin': 12,
     'title': 'Hello World',
     'type': 'window'}

.. toctree::
   :maxdepth: 2
   :caption: Contents:

User Interface Backends
-----------------------
|ProjectName| is intended to provide a Python oriented user interface API. You might consider it to be a wrapper on
a lower level API such as Qt. However, it is more general in that other low level UI's could be used as long as a
specific implementation of ``UserInterface`` is provided for those lower level UI's.

Currently only two low level implementations are provided:

- A |LauncherName| implementation in C++ based directly on Qt.
- A ``TestUI`` user interface, used for testing.

An HTML/JavaScript implementation is also in the works.

Organizing a Nion UI Application
================================

Although it is possible to write a complete Nion UI application in a single file, it is recommended to organize your code
into multiple files and modules.

A typical organization might look like this:

.. code-block:: text

    nionui_app/
        my_app/
            main.py

By convention, the top level module of your application is named ``nionui_app``. Inside that module, you can have
sub-modules for your specific application.

Putting your application into the ``nionui_app`` module allows future tooling to recognize your application as a Nion UI
application.

The main entry point for your application is typically a file named ``main.py``. This file contains the ``main`` function
which is called by the ``nionui`` command line tool to start your application.

.. LLM_CONTEXT: New projects should be created with the typical organization above. The projects should be fully typed. The main.py file should contain a safety check to ensure it is not run directly, but only through the nionui command line tool.

Declarative UI
==============
The declarative features allow you to have a clean separation between the UI and your code for handling the UI.

A declaration is split into a description (a Python dict, serializable to JSON) and a handler (code). This tookit takes
care of connecting the declaration to the handler when the declaration is attached to a window or other real UI.

Since the declaration is a Python dict (serializable to JSON), the declarative part of the UI can be stored in a JSON
text file. This opens the possibility of having a graphical editor for the declarative part, which reads and write the
JSON text file. A graphical editor is not yet available.

The declarative UI can be built explicitly using methods of a ``DeclarativeUI`` class or by providing an explicit dict.
This guide assumes it will be built using the ``DeclarativeUI`` class and explicit methods.

The declarative UI provides top level support for windows and dialogs.

It also provides support for layout into rows, columns, and stacks.

It provides labels, push buttons, check boxes, combo boxes, line edits, progress bars, radio buttons, sliders, groups,
and tabs.

It provides experimental support for compositions (reusable UI sections).

And finally it provides support for binding UI elements to your application specific code using bindings and converters.

Handlers
--------
The goal of the UI is to connect user actions to your code. The declarative UI does this by an object that you provide
called the handler.

When a declarative UI is instantiated it is turned into layouts and widgets that are displayed to the user. You can
get access to specific widgets, bind to parts of those widgets such as a text label, and respond to events such as a
button click.

To do all of these things, your declaration specifies how to make these connections to your handler.

Handler Lifecycle
^^^^^^^^^^^^^^^^^
For your top level handler, you will typically write the class yourself, initializing properties and providing methods
as explained below.

You will instantiate your handler yourself and pass the instance to the declarative UI engine along with the Python
``dict`` which describes your UI.

The declarative UI engine will build the widgets and put them in the appropriate container (such as a window) and then
connect the widgets, events, bindings, etc. to your handler.

For the most part, your handler can be initialized in its ``__init__`` method. However, at the point the handler is
created, it will not have access to any of the UI widgets.

Assuming your UI description is in a variable ``layout`` and that your handler class is named ``Handler``, initializing
the declarative UI might look something like this:

.. code-block:: python

    layout = build_ui_layout()
    handler = Handler()
    Declarative.run_dialog(layout, handler)

During ``run_dialog``, the declarative UI engine will populate properties of your handler connected to the UI, inject
useful objects such as ``_event_loop``, and then call the method ``init_handler`` which can be used to initialize any
values that require the UI to be in place.

Your handler can do any further initialization of the widgets in ``init_handler``.

.. todo: add section about event handler

Connecting Widgets
^^^^^^^^^^^^^^^^^^
Most widgets declarations provide an optional ``name`` parameter. If you pass a string value for ``name``, the widget
asssociated with that declaration will be stored into your handler under the ``name`` property.

For instance, let's say you create a button with the following method:

``button = ui.create_push_button(text="Push Me", name="my_button")``

Once your handler has been initialized, the ``PushButtonWidget`` associated with your declaration will be stored in the
property ``my_button`` of your handler.

This gives you direct access to the widget in your handler. Sometimes this is necessary, although direct widget access
may limit future compatibility, so it should be used sparingly.

Connecting Strings
^^^^^^^^^^^^^^^^^^
Some widgets, such as a label and group, display text. For those widgets, you can provide that text directly when
creating the widget.

``button = ui.create_push_button(text="Push Me", name="my_button")``

In the code above, the text "Push Me" is passed to the ``create_push_button`` method and will appear as the text of the
button.

This may seem obvious, but be sure to note the distinction between the string passed as ``text`` and the string passed
as ``name``. The string passed as ``text`` is used directly in the UI and displayed to the user. The string passed as
``name`` is used as a property name on your handler in which to store the ``PushButtonWidget`` instance.

In the binding section described below, you will see how to bind the text of the label to a variable in your handler.

.. todo:: reference version of string parameters, text_ref, etc.

Connecting References
^^^^^^^^^^^^^^^^^^^^^
Many widgets, such as check boxes, have associated values that can be set from code or changed by the user. For those
widgets, you can provide a handler property which holds the value.

.. code-block:: python

    class Handler:
        def __init__(self):
            self.enabled = False

    check_box = ui.create_check_box(text="Enable", name="enable_cb", checked="enabled")

As before, the label string displayed to the user is passed as ``text``. The ``CheckBoxWidget`` is stored into the
handler under the property ``enable_cb`` using the ``name`` property.

But in this case, by passing "enabled" as the ``checked`` parameter, the state of the checkbox will be initialized with
the ``enabled`` value in the handler. And when the user clicks on the checkbox, the ``enabled`` property of the handler
will be changed to reflect the checked state.

Events
^^^^^^
Many widgets, such as buttons, trigger events that can invoke methods in the handler.

.. code-block:: python

    class Handler:
        def handle_click(self):
            print("Clicked!")

    push_button = ui.create_push_button(text="Push Me", on_clicked="handle_click")

In this case, the string "handle_click" passed as the parameter ``on_clicked`` indicates that the event ``on_clicked``
should call the method ``handle_click`` on the handler when the user clicks the button.

Each widget defines its own set of events and each event may have unique parameters. Refer the documentation for the
specific widget for detailed information.

Bindings
^^^^^^^^
As you use string values, references, and events, a pattern will emerge where a value associated with a UI element will
be connected to the handler, you will listen for the changed event for that value, and you will update the widget when
the value changes.

The declarative UI engine provides a mechanism called *binding* which streamlines this pattern through the use of
property models, converters, and events.

.. code-block:: python

    class Handler:
        def __init__(self):
            self.enabled_model = Model.PropertyModel(False)
            self.enabled_model.on_value_changed = self.enabled_changed

        def enabled_changed(self, widget, new_enabled):
            print(f"Enabled changed to {new_enabled}")

    check_box = ui.create_check_box(text="Enabled", value="@binding(enabled_model.value)")

In the example above, the handler provides a *model* named ``enabled_model`` to hold the value of the ``enabled``
property. The handler attaches a listener to the *model* that gets called when the value of the model changes. Finally,
the declaration for the check box indicates that the ``value`` will bind to the value of the model
``enabled_model.value``.

Using this technique, interacting with the ``enabled`` value is easy. Just get and set the value from the
``enabled_model``.

If you wanted to connect a button to reset the value of ``enabled``, you could add a method to the handler and connect
it to a button.

.. code-block:: python

    class Handler:
        ...

        def button_pushed(self):
            self.enabled_model.value = True

Most places where you use a string value or a reference can be replaced with a *binding*.

Converters
^^^^^^^^^^
Often when using bindings, you will need to convert the value from one format to another. For instance, you might want
the user to enter an integer into a text field. You can do this by attaching a *converter* to a binding.

.. code-block:: python

    class Handler:
        def __init__(self):
            self.year_model = Model.PropertyModel(2001)
            self.year_converter = Converter.IntegerToStringConverter()

    year_field = ui.create_line_edit(text="Enabled", text="@binding(year_model.value, converter=year_converter)")

Now the value in ``year_model`` will be stored as an integer, but the line edit requires a string. The converter will do
the conversion automatically.

Bindings Technical Details
^^^^^^^^^^^^^^^^^^^^^^^^^^
This section refers to classes defined in the project |UtilsName|.

In the examples above, the bindings use a ``Model.PropertyModel`` to store the value. The ``PropertyModel`` class
interacts with bindings using a simple protocol.

First, it supports getting and setting a property, named ``value`` in this case.

Next, it provides a ``Event.Event`` named "property_changed" that gets fired whenever the ``value`` is set.

You can explicitly provide this functionality and bind to objects other than a ``Model.PropertyModel``.

.. code-block:: python

    class Handler:
        def __init__(self):
            self.property_changed_event = Event.Event()
            self.__name = "March"

        @property
        def name(self):
            return self.__name

        @name.setter
        def name(self, value):
            self.__name = value
            self.property_changed_event.fire("name")

    name_field = ui.create_line_edit(text="Your Name?", text="@binding(name)")

Application and Windows
-----------------------
The declarative UI provides top level support for windows and dialogs.

You can declare a window using ``ui.create_window`` (see below). Once you have a window declaration, you can run the
window using ``Application.run_window`` in your ``main`` function.

.. code-block:: python

    def main(args, bootstrap_args):
        ui = Declarative.DeclarativeUI()
        content = ui.create_column(ui.create_label(text="Hello World"))
        window = ui.create_window(content, title="Hello World", margin=12)
        handler = object()  # a dummy handler in this example
        return Application.run_window(args, bootstrap_args, window, handler)

.. autoclass:: nion.ui.Declarative.DeclarativeUI
    :members: create_window, create_modeless_dialog

Layout
------
Content layout is done using rows, columns, groups, and stacks. Tabs and groups participate in layout, but will be
discussed below under the widgets section since they can't be used as the top-most layout.

A row, column, or stack can be used as a base for additional content. Each element contains other elements (referred to
as *children* in this guide).

.. todo: dynamic children

Rows and columns layout their children horizontally or vertically. The children can optionally be separated by *spacing*
and the entire row or column can have a *margin* spacing.

In addition, you can explicitly add spacing or stretches to rows and columns. Spacing ensures the spacing for that item
never goes smaller than the spacing value. And stretch attempts to take up free space in the layout, effectly squishing
the other items to their minimum sizes. If there are more than one stretches, the free space will be distributed equally
between them.

Stacks layout their children on top of one another with only a single child visible at any given time. Stacks are useful
when presenting optional content where the specific content is controlled by another UI element. Stacks can have a
*margin* spacing.

Scroll areas layout their content in a scrollable area with scroll bars.

.. autoclass:: nion.ui.Declarative.DeclarativeUI
    :members: create_column, create_row, create_spacing, create_stretch, create_stack, create_scroll_area

Widgets
-------
You can create labels, push buttons, check boxes, combo boxes, line edits, progress bars, radio buttons, sliders,
groups, and tabs.

Each is described below.

.. autoclass:: nion.ui.Declarative.DeclarativeUI
    :members: create_check_box, create_combo_box, create_group, create_label, create_line_edit, create_progress_bar, create_push_button, create_radio_button, create_slider, create_tab, create_tabs

Components
----------
It provides experimental support for compositions (reusable UI sections).

Common Properties
-----------------
Many widgets and layouts share common properties. These common properties are described here.

``enabled``
    A boolean value indicating whether the widget is enabled or disabled. Bindable.
``visible``
    A boolean value indicating whether the widget is visible or hidden. Bindable.
``tool_tip``
    A string value indicating the tooltip text for the widget. Bindable.
``color``
    A string value indicating the color for the widget. Bindable.
``background_color``
    A string value indicating the background color for the widget. Bindable.
``font``
    A string value indicating the font for the widget. Bindable.
``border_color``
    A string value indicating the border color for the widget. Used for debugging. Bindable.

Resources
^^^^^^^^^
Widgets that construct their content dynamically get the dynamic content via resources. Resources can be returned by as a ``dict`` from the associated handler's ``resources`` property, or by implementing ``get_resources`` on the handler, or both.

.. code-block:: python

    class Handler:
        def __init__(self):
            u = Declarative.DeclarativeUI()
            self.resources = {"component": u.define_component(u.create_label(text="Component"))}

        def get_resource(resource_id: str, **kwargs) -> typing.Optional[UIDescription]:
            if resource_id == "component2":
                return u.define_component(u.create_label(text="Component 2"))
            return None

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
