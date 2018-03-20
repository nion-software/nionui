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


Introduction to the Declarative UI
----------------------------------

The declarative features allow you to have a clean separation between the UI and your code for handling the UI.

.. code-block:: python

    class Handler:
        def __init__(self):
            self.label_item = None
            self.click_count = 0

        def button_clicked(self, widget):
            self.click_count += 1
            self.label_item.text = _("Clicked") + " " + str(self.click_count)

    def main(args, bootstrap_args):
        ui = Declarative.DeclarativeUI()
        button = ui.create_push_button(text=_("Hello World"), on_clicked="button_clicked")
        label = ui.create_label(name="label_item", text=_("Not Clicked"))
        column = ui.create_column(button, label, spacing=8)
        window = ui.create_window(column, title=_("Hello World"), margin=12)
        handler = Handler()
        return Declarative.run_ui(args, bootstrap_args, window, handler)

At the top, a :code:`Handler` class is defined which includes a property :code:`label_item` and a method
:code:`button_clicked` which will be connected to the UI. It also includes a properyt :code:`click_count` that will be
used separately.

The :code:`main` function begins by creating a :code:`ui` object which will help construct the Python dict representing
the layout.

With the :code:`ui` object, a :code:`button` is declared. The button declares that the :code:`on_clicked` event will be
connected to the :code:`button_clicked` method of the handler.

Next, a :code:`label` is declared. By specifying :code:`name` to the label, the declarative UI engine will store the
label instance into the handler when the UI is run (the `label_item` property in the handler).

Next, a :code:`column` is declared with the :code:`button` and :code:`label` in the column, and both are but into a
:code:`window` declaration.

Next, an instance of :code:`Handler` is created.

Finally, the :code:`window` and :code:`handler` are passed to :code:`Declarative.run_ui` which constructs the window UI,
connects it to the handler, and presents the UI to the user.

The :code:`window` variable is a Python dictionary. It gets connected to the :code:`Handler` in the
:code:`Declarative.run_ui` method. The dictionary looks like this::

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
specific implementation of :code:`UserInterface` is provided for those lower level UI's.

Currently only two low level implementations are provided:

- A |LauncherName| implementation in C++ based directly on Qt.
- A :code:`TestUI` user interface, used for testing.

An HTML/JavaScript implementation is also in the works.

Declarative UI
==============

The declarative features allow you to have a clean separation between the UI and your code for handling the UI.

A declaration is split into a description (a Python dict, serializable to JSON) and a handler (code). This tookit takes
care of connecting the declaration to the handler when the declaration is attached to a window or other real UI.

Since the declaration is a Python dict (serializable to JSON), the declarative part of the UI can be stored in a JSON
text file. This opens the possibility of having a graphical editor for the declarative part, which reads and write the
JSON text file. A graphical editor is not yet available.

The declarative UI can be built explicitly using methods of a :code:`DeclarativeUI` class or by providing an explicit dict.
This guide assumes it will be built using the :code:`DeclarativeUI` class and explicit methods.

The declarative UI provides some top level support such as windows, dialogs, and specific features such as a status bar.

It also provides support for layout into rows, columns, groups, stacks.

It provides labels, check boxes, combo boxes, line edits, progress bars, radio buttons, sliders, and tabs.

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
:code:`dict` which describes your UI.

The declarative UI engine will build the widgets and put them in the appropriate container (such as a window) and then
connect the widgets, events, bindings, etc. to your handler.

For the most part, your handler can be initialized in its :code:`__init__` method. However, at the point the handler
is created, it will not have access to any of the UI widgets.

Assuming your UI description is in a variable :code:`layout` and that your handler class is named :code:`Handler`,
initializing the declarative UI might look something like this:

.. code-block:: python

    layout = build_ui_layout()
    handler = Handler()
    Declarative.run_dialog(layout, handler)

During :code:`run_dialog`, the declarative UI engine will populate properties of your handler connected to the UI and
then call the method :code:`init_handler` which can be used to initialize any values that require the UI to be in place.

Your handler can do any further initialization of the widgets in :code:`init_handler`.

Connecting Widgets
^^^^^^^^^^^^^^^^^^
Most widgets declarations provide an optional :code:`name` parameter. If you pass a string value for :code:`name`, the widget
asssociated with that declaration will be stored into your handler under the :code:`name` property.

For instance, let's say you create a button with the following method:

:code:`button = ui.create_push_button(text="Push Me", name="my_button")`

Once your handler has been initialized, the :code:`PushButtonWidget` associated with your declaration will be stored
in the property :code:`my_button` of your handler.

This gives you direct access to the widget in your handler. Sometimes this is necessary, although direct widget access
may limit future compatibility, so it should be used sparingly.

Connecting Strings
^^^^^^^^^^^^^^^^^^
Some widgets, such as a label and group, display text. For those widgets, you can provide that text directly when
creating the widget.

:code:`button = ui.create_push_button(text="Push Me", name="my_button")`

In the code above, the text "Push Me" is passed to the :code:`create_push_button` method and will appear as the text
of the button.

This may seem obvious, but be sure to note the distinction between the string passed as :code:`text` and the string
passed as :code:`name`. The string passed as :code:`text` is used directly in the UI and displayed to the user. The
string passed as :code:`name` is used as a property name on your handler in which to store the
:code:`PushButtonWidget` instance.

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

As before, the label string displayed to the user is passed as :code:`text`. The :code:`CheckBoxWidget` is
stored into the handler under the property :code:`enable_cb` using the :code:`name` property.

But in this case, by passing "enabled" as the :code:`checked` parameter, the state of the checkbox will be initialized
with the :code:`enabled` value in the handler. And when the user clicks on the checkbox, the :code:`enabled` property of
the handler will be changed to reflect the checked state.

Events
^^^^^^
Many widgets, such as buttons, trigger events that can invoke methods in the handler.

.. code-block:: python

    class Handler:
        def handle_click(self):
            print("Clicked!")

    push_button = ui.create_push_button(text="Push Me", on_clicked="handle_click")

In this case, the string "handle_click" passed as the parameter :code:`on_clicked` indicates that the event
:code:`on_clicked` should call the method :code:`handle_click` on the handler when the user clicks the button.

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

In the example above, the handler provides a *model* named :code:`enabled_model` to hold the value of the
:code:`enabled` property. The handler attaches a listener to the *model* that gets called when the value of the model
changes. Finally, the declaration for the check box indicates that the :code:`value` will bind to the value of the model
:code:`enabled_model.value`.

Using this technique, interacting with the :code:`enabled` value is easy. Just get and set the value from the
:code:`enabled_model`.

If you wanted to connect a button to reset the value of :code:`enabled`, you could add a method to the handler and
connect it to a button.

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

Now the value in :code:`year_model` will be stored as an integer, but the line edit requires a string. The converter
will do the conversion automatically.

Bindings Technical Details
^^^^^^^^^^^^^^^^^^^^^^^^^^
This section refers to classes defined in the project |UtilsName|.

In the examples above, the bindings use a :code:`Model.PropertyModel` to store the value. The :code:`PropertyModel` class
interacts with bindings using a simple protocol.

First, it supports getting and setting a property, named :code:`value` in this case.

Next, it provides a :code:`Event.Event` named "property_changed" that gets fired whenever the :code:`value` is set.

You can explicitly provide this functionality and bind to objects other than a :code:`Model.PropertyModel`.

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

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
