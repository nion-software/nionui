# standard libraries
import gettext
import re

# local libraries
from nion.ui import Dialog
from nion.utils import Binding


_ = gettext.gettext


class DeclarativeUI:

    # ----: row
    # ----: column
    # ----: spacing
    # ----: stretch
    # ----: label
    # TODO: text edit
    # ----: line edit
    # TODO: scroll area
    # TODO: group box
    # TODO: tool tips
    # TODO: expander
    # TODO: border
    # ----: push button
    # ----: check box
    # ----: combo box
    # TODO: splitter
    # TODO: image
    # TODO: stack
    # TODO: tab
    # TODO: data view
    # ----: component
    # TODO: part
    # TODO: list view
    # TODO: tree view
    # TODO: slider
    # TODO: menus
    # TODO: context menu
    # TODO: radio buttons
    # TODO: progress bar
    # TODO: key handler
    # TODO: canvas
    # TODO: dock panels
    # TODO: windows
    # TODO: thumbnails
    # TODO: display panels
    # TODO: periodic
    # ----: bindings
    # TODO: commands
    # TODO: standard dialog boxes, open, save, print, confirm

    def __init__(self):
        pass

    def create_column(self, *d_children, spacing=None):
        d = {"type": "column"}
        if spacing is not None:
            d["spacing"] = spacing
        if len(d_children) > 0:
            children = d.setdefault("children", list())
            for d_child in d_children:
                children.append(d_child)
        return d

    def create_row(self, *d_children, spacing=None):
        d = {"type": "row"}
        if spacing is not None:
            d["spacing"] = spacing
        if len(d_children) > 0:
            children = d.setdefault("children", list())
            for d_child in d_children:
                children.append(d_child)
        return d

    def create_spacing(self, size):
        return {"type": "spacing", "size": size}

    def create_stretch(self):
        return {"type": "stretch"}

    def create_label(self, *,
                     text: str=None,
                     name=None):
        d = {"type": "text_label"}
        if text is not None:
            d["text"] = text
        if name is not None:
            d["name"] = name
        return d

    def create_line_edit(self, *,
                         text: str=None,
                         name=None,
                         editable=None,
                         placeholder_text=None,
                         clear_button_enabled=None,
                         on_editing_finished=None,
                         on_escape_pressed=None,
                         on_return_pressed=None,
                         on_key_pressed=None,
                         on_text_edited=None,
                         text_binding=None):
        d = {"type": "line_edit"}
        if text is not None:
            d["text"] = text
        if name is not None:
            d["name"] = name
        if editable is not None:
            d["editable"] = editable
        if placeholder_text is not None:
            d["placeholder_text"] = placeholder_text
        if clear_button_enabled is not None:
            d["clear_button_enabled"] = clear_button_enabled
        if on_editing_finished is not None:
            d["on_editing_finished"] = on_editing_finished
        if on_escape_pressed is not None:
            d["on_escape_pressed"] = on_escape_pressed
        if on_return_pressed is not None:
            d["on_return_pressed"] = on_return_pressed
        if on_key_pressed is not None:
            d["on_key_pressed"] = on_key_pressed
        if on_text_edited is not None:
            d["on_text_edited"] = on_text_edited
        if text_binding is not None:
            d["text_binding"] = text_binding
        return d

    def create_push_button(self, *,
                           text: str=None,
                           name=None,
                           on_clicked=None):
        d = {"type": "push_button"}
        if text is not None:
            d["text"] = text
        if name is not None:
            d["name"] = name
        if on_clicked is not None:
            d["on_clicked"] = on_clicked
        return d

    def create_check_box(self, *,
                         text: str=None,
                         name=None,
                         checked=None,
                         check_state=None,
                         tristate=None,
                         on_checked_changed=None,
                         on_check_state_changed=None,
                         checked_binding=None,
                         check_state_binding=None):
        d = {"type": "check_box"}
        if text is not None:
            d["text"] = text
        if checked is not None:
            d["checked"] = checked
        if check_state is not None:
            d["check_state"] = check_state
        if tristate is not None:
            d["tristate"] = tristate
        if name is not None:
            d["name"] = name
        if on_checked_changed is not None:
            d["on_checked_changed"] = on_checked_changed
        if on_check_state_changed is not None:
            d["on_check_state_changed"] = on_check_state_changed
        if checked_binding is not None:
            d["checked_binding"] = checked_binding
        if check_state_binding is not None:
            d["check_state_binding"] = check_state_binding
        return d

    def create_combo_box(self, *,
                         name=None,
                         items=None,
                         items_ref=None,
                         current_index=None,
                         on_current_index_changed=None):
        d = {"type": "combo_box"}
        if name is not None:
            d["name"] = name
        if items is not None:
            d["items"] = items
        if items_ref is not None:
            d["items_ref"] = items_ref
        if current_index is not None:
            d["current_index"] = current_index
        if on_current_index_changed is not None:
            d["on_current_index_changed"] = on_current_index_changed
        return d

    def create_modeless_dialog(self, content, *, title: str=None, resources=None, margin=None):
        d = {"type": "modeless_dialog", "content": content}
        if title is not None:
            d["title"] = title
        if margin is not None:
            d["margin"] = margin
        if resources is not None:
            d["resources"] = resources
        return d

    def define_component(self, content, create_handler_method_name, events=None):
        d = {"type": "component", "content": content, "create_handler_method_name": create_handler_method_name}
        if events is not None:
            d["events"] = events
        return d

    def create_component(self, identifier, properties, **kwargs):
        d = {"type": "component", "identifier": identifier, "properties": properties}
        for k, v in kwargs.items():
            d[k] = v
        return d


def connect_name(widget, d, handler):
    name = d.get("name", None)
    if name:
        setattr(handler, name, widget)


def connect_string(widget, d, handler, property, finishes):
    v = d.get(property)
    m = re.match("^@binding\((.+)\)$", v if v else "")
    # print(f"{v}, {m}, {m.group(1) if m else 'NA'}")
    if m:
        b = m.group(1)
        parts = [p.strip() for p in b.split(',')]
        def finish_binding():
            handler_property_path = parts[0].split('.')
            source = handler
            for p in handler_property_path[:-1]:
                source = getattr(source, p.strip())
            converter = None
            for part in parts:
                if part.startswith("converter="):
                    converter = getattr(handler, part[len("converter="):])
            binding = Binding.PropertyBinding(source, handler_property_path[-1].strip(), converter=converter)
            getattr(widget, "bind_" + property)(binding)
        finishes.append(finish_binding)
    else:
        setattr(widget, property, v)


def connect_value(widget, d, handler, property, finishes, binding_name=None):
    binding_name = binding_name if binding_name else property
    v = d.get(property)
    m = re.match("^@binding\((.+)\)$", v if v else "")
    # print(f"{v}, {m}, {m.group(1) if m else 'NA'}")
    if m:
        b = m.group(1)
        parts = [p.strip() for p in b.split(',')]
        def finish_binding():
            handler_property_path = parts[0].split('.')
            source = handler
            for p in handler_property_path[:-1]:
                source = getattr(source, p.strip())
            converter = None
            for part in parts:
                if part.startswith("converter="):
                    converter = getattr(handler, part[len("converter="):])
            binding = Binding.PropertyBinding(source, handler_property_path[-1].strip(), converter=converter)
            getattr(widget, "bind_" + binding_name)(binding)
        finishes.append(finish_binding)
    elif v is not None:
        setattr(widget, binding_name, getattr(handler, v))


def connect_event(widget, source, d, handler, event_str, arg_names):
    event_method_name = d.get(event_str, None)
    if event_method_name:
        event_fn = getattr(handler, event_method_name)
        if event_fn:
            def trampoline(*args, **kwargs):
                combined_args = dict()
                for arg_name, arg in zip(arg_names, args):
                    combined_args[arg_name] = arg
                combined_args.update(kwargs)
                event_fn(widget, **combined_args)
            setattr(source, event_str, trampoline)
        else:
            print("WARNING: '" + event_str + "' method " + event_method_name + " not found in handler.")


def connect_binding(widget, d, handler, binding_str, binding_connector):
    binding_name = d.get(binding_str, None)
    if binding_name:
        binding = getattr(handler, binding_name)
        if binding and isinstance(binding, Binding.Binding):
            getattr(widget, binding_connector)(binding)
        else:
            print("WARNING: '" + binding_str + "' binding " + binding_name + " not found in handler.")


def construct(ui, window, d, handler, finishes=None):
    d_type = d.get("type")
    if d_type == "modeless_dialog":
        title = d.get("title", _("Untitled"))
        margin = d.get("margin")
        persistent_id = d.get("persistent_id")
        content = d.get("content")
        resources = d.get("resources", dict())
        for k, v in resources.items():
            resources[k] = v
        if not hasattr(handler, "resources"):
            handler.resources = resources
        else:
            handler.resources.update(resources)
        finishes = list()
        dialog = Dialog.ActionDialog(ui, title, app=window.app, parent_window=window, persistent_id=persistent_id)
        dialog._create_menus()
        outer_row = ui.create_row_widget()
        outer_column = ui.create_column_widget()
        inner_content = construct(ui, window, content, handler, finishes)
        if margin is not None:
            outer_row.add_spacing(margin)
            outer_column.add_spacing(margin)
        outer_column.add(inner_content)
        outer_row.add(outer_column)
        if margin is not None:
            outer_row.add_spacing(margin)
            outer_column.add_spacing(margin)
        dialog.content.add(outer_row)
        for finish in finishes:
            finish()
        if handler and hasattr(handler, "init_handler"):
            handler.init_handler()
        def close_handler():
            if handler and hasattr(handler, "close"):
                handler.close()
        dialog.on_close = close_handler
        return dialog
    elif d_type == "column":
        column_widget = ui.create_column_widget()
        spacing = d.get("spacing")
        children = d.get("children", list())
        first = True
        for child in children:
            if not first and spacing is not None:
                column_widget.add_spacing(spacing)
            if child.get("type") == "spacing":
                column_widget.add_spacing(child.get("size", 0))
            elif child.get("type") == "stretch":
                column_widget.add_stretch()
            else:
                column_widget.add(construct(ui, window, child, handler, finishes))
            first = False
        return column_widget
    elif d_type == "row":
        row_widget = ui.create_row_widget()
        spacing = d.get("spacing")
        children = d.get("children", list())
        first = True
        for child in children:
            if not first and spacing is not None:
                row_widget.add_spacing(spacing)
            if child.get("type") == "spacing":
                row_widget.add_spacing(child.get("size", 0))
            elif child.get("type") == "stretch":
                row_widget.add_stretch()
            else:
                row_widget.add(construct(ui, window, child, handler, finishes))
            first = False
        return row_widget
    elif d_type == "text_label":
        widget = ui.create_label_widget()
        if handler:
            connect_string(widget, d, handler, "text", finishes)
            connect_name(widget, d, handler)
        return widget
    elif d_type == "line_edit":
        editable = d.get("editable", None)
        placeholder_text = d.get("placeholder_text", None)
        clear_button_enabled = d.get("clear_button_enabled", None)
        widget = ui.create_line_edit_widget()
        if editable is not None:
            widget.editable = editable
        if placeholder_text is not None:
            widget.placeholder_text = placeholder_text
        if clear_button_enabled is not None:
            widget.clear_button_enabled = clear_button_enabled
        if handler:
            connect_name(widget, d, handler)
            connect_string(widget, d, handler, "text", finishes)
            connect_event(widget, widget, d, handler, "on_editing_finished", ["text"])
            connect_event(widget, widget, d, handler, "on_escape_pressed", [])
            connect_event(widget, widget, d, handler, "on_return_pressed", [])
            connect_event(widget, widget, d, handler, "on_key_pressed", ["key"])
            connect_event(widget, widget, d, handler, "on_text_edited", ["text"])
            connect_binding(widget, d, handler, "text_binding", "bind_text")
        return widget
    elif d_type == "push_button":
        text = d.get("text", None)
        widget = ui.create_push_button_widget(text)
        if handler:
            connect_name(widget, d, handler)
            connect_event(widget, widget, d, handler, "on_clicked", [])
        return widget
    elif d_type == "check_box":
        text = d.get("text", None)
        checked = d.get("checked", None)
        check_state = d.get("check_state", None)
        tristate = d.get("tristate", None)
        widget = ui.create_check_box_widget(text)
        if tristate is not None:
            widget.tristate = tristate
        if check_state is not None:
            widget.check_state = check_state
        if checked is not None:
            widget.checked = checked
        if handler:
            connect_name(widget, d, handler)
            connect_event(widget, widget, d, handler, "on_checked_changed", ["checked"])
            connect_event(widget, widget, d, handler, "on_check_state_changed", ["check_state"])
            connect_binding(widget, d, handler, "checked_binding", "bind_checked")
            connect_binding(widget, d, handler, "check_state_binding", "bind_check_state")
        return widget
    elif d_type == "combo_box":
        items = d.get("items", None)
        widget = ui.create_combo_box_widget(items=items)
        if handler:
            connect_name(widget, d, handler)
            connect_value(widget, d, handler, "current_index", finishes)
            connect_value(widget, d, handler, "items_ref", finishes, binding_name="items")
            connect_event(widget, widget, d, handler, "on_current_index_changed", ["current_index"])
        return widget
    elif d_type == "component":
        # a component needs to be registered before it is instantiated.
        # look up the identifier in the handler resoureces.
        identifier = d.get("identifier", None)
        component = handler.resources.get(identifier)
        if component:
            assert component.get("type") == "component"
            # the component will have a content portion, which is just a widget description.
            # it will also have a function to create its handler. finally the component will
            # have a list of events that to be connected.
            content = component.get("content")
            create_handler_method_name = component.get("create_handler_method_name")
            events = component.get("events", list())
            # create the handler first, but don't initialize it.
            component_handler = getattr(handler, create_handler_method_name)() if create_handler_method_name and hasattr(handler, create_handler_method_name) else None
            if component_handler:
                # set properties in the component from the properties dict
                for k, v in d.get("properties", dict()).items():
                    # print(f"setting property {k} to {v}")
                    setattr(component_handler, k, v)
            # now construct the widget
            widget = construct(ui, window, content, component_handler, finishes)
            if handler:
                # connect the name to the handler if desired
                connect_name(widget, d, handler)
                # since the handler is custom to the widget, make a way to retrieve it from the widget
                widget.handler = component_handler
                if component_handler and hasattr(component_handler, "init_component"):
                    component_handler.init_component()
                # connect events
                for event in events:
                    # print(f"connecting {event['event']} ({event['parameters']})")
                    connect_event(widget, component_handler, d, handler, event["event"], event["parameters"])
            return widget
    return None
