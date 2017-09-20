# standard libraries
import gettext

# local libraries
from nion.ui import Dialog
from nion.utils import Binding


_ = gettext.gettext


class DeclarativeUI:

    # TODO: text edit
    # TODO: label
    # TODO: line edit
    # TODO: scroll area
    # TODO: group box
    # TODO: label
    # TODO: tool tips
    # TODO: expander
    # TODO: border
    # TODO: combobox
    # TODO: splitter
    # TODO: image
    # TODO: stack
    # TODO: tab
    # TODO: data view
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

    def __init__(self):
        pass

    def create_column(self, *d_children):
        d = {"type": "column"}
        if len(d_children) > 0:
            children = d.setdefault("children", list())
            for d_child in d_children:
                children.append(d_child)
        return d

    def create_row(self, *d_children):
        d = {"type": "row"}
        if len(d_children) > 0:
            children = d.setdefault("children", list())
            for d_child in d_children:
                children.append(d_child)
        return d

    def create_spacing(self, size):
        return {"type": "spacing", "size": size}

    def create_stretch(self):
        return {"type": "stretch"}

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

    def create_modeless_dialog(self, content, *, title: str=None):
        d = {"type": "modeless_dialog", "content": content}
        if title is not None:
            d["title"] = title
        return d

    def add_children(self, container, *items):
        children = container.setdefault("children", list())
        for item in items:
            children.append(item)
        return container


def connect_name(widget, d, handler):
    name = d.get("name", None)
    if name:
        setattr(handler, name, widget)


def connect_event(widget, d, handler, event_str):
    event_method_name = d.get(event_str, None)
    if event_method_name:
        event_fn = getattr(handler, event_method_name)
        if event_fn:
            setattr(widget, event_str, event_fn)
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


def construct(ui, window, d, handler):
    d_type = d.get("type")
    if d_type == "modeless_dialog":
        title = d.get("title", _("Untitled"))
        persistent_id = d.get("persistent_id")
        content = d.get("content")
        dialog = Dialog.ActionDialog(ui, title, app=window.app, parent_window=window, persistent_id=persistent_id)
        dialog._create_menus()
        dialog.content.add(construct(ui, window, content, handler))
        def close_handler():
            if handler and hasattr(handler, "close"):
                handler.close()
        dialog.on_close = close_handler
        return dialog
    elif d_type == "column":
        column_widget = ui.create_column_widget()
        children = d.get("children", list())
        for child in children:
            if child.get("type") == "spacing":
                column_widget.add_spacing(child.get("size", 0))
            elif child.get("type") == "stretch":
                column_widget.add_stretch()
            else:
                column_widget.add(construct(ui, window, child, handler))
        return column_widget
    elif d_type == "row":
        row_widget = ui.create_row_widget()
        children = d.get("children", list())
        for child in children:
            if child.get("type") == "spacing":
                row_widget.add_spacing(child.get("size", 0))
            elif child.get("type") == "stretch":
                row_widget.add_stretch()
            else:
                row_widget.add(construct(ui, window, child, handler))
        return row_widget
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
            connect_event(widget, d, handler, "on_checked_changed")
            connect_event(widget, d, handler, "on_check_state_changed")
            connect_binding(widget, d, handler, "checked_binding", "bind_checked")
            connect_binding(widget, d, handler, "check_state_binding", "bind_check_state")
        return widget
    elif d_type == "push_button":
        text = d.get("text", None)
        widget = ui.create_push_button_widget(text)
        if handler:
            connect_name(widget, d, handler)
            connect_event(widget, d, handler, "on_clicked")
        return widget
    return None
