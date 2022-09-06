from __future__ import annotations

# standard libraries
import asyncio
import gettext
import re
import typing

# local libraries
from nion.ui import CanvasItem
from nion.ui import Dialog
from nion.ui import UserInterface
from nion.ui import Window
from nion.ui import Widgets
from nion.utils import Binding
from nion.utils import Observable
from nion.utils import Registry
from nion.utils import Selection

if typing.TYPE_CHECKING:
    from nion.ui import Application


UIDescription = typing.Mapping[str, typing.Any]  # when napolean works: typing.NewType("UIDescription", typing.Dict)
UIDescriptionResult = typing.Dict[str, typing.Any]  # when napolean works: typing.NewType("UIDescription", typing.Dict)
UIResources = typing.Mapping[str, typing.Any]  # when napolean works: typing.NewType("UIResources", typing.Dict)
UIPoints = int  # when napolean works: typing.NewType("UIPoints", int)
UILabel = str
UIIdentifier = str  # typing.NewType("UIIndentifier", str)
UICallableIdentifier = str  # typing.NewType("UICallableIdentifier", str)
UIWidget = UserInterface.Widget
UIKey = UserInterface.Key

_FinishesListType = typing.List[typing.Callable[[], None]]

_ = gettext.gettext


class DeclarativeUI:

    # ----: row
    # ----: column
    # ----: spacing
    # ----: stretch
    # ----: stack
    # ----: tab
    # ----: label
    # ----: text edit
    # ----: line edit
    # TODO: scroll area
    # ----: group box
    # ----: status bar
    # ----: tool tips
    # TODO: expander
    # TODO: border
    # TODO: divider
    # ----: push button
    # ----: check box
    # ----: combo box
    # ----: radio buttons
    # TODO: splitter
    # ----: image
    # ----: component
    # TODO: part
    # TODO: data view
    # TODO: list view
    # TODO: tree view
    # ----: slider
    # TODO: menus
    # TODO: context menu
    # ----: progress bar
    # TODO: key handler
    # TODO: key validator
    # TODO: field validator
    # TODO: canvas
    # TODO: dock panels
    # TODO: windows
    # TODO: thumbnails
    # TODO: display panels
    # TODO: periodic
    # TODO: focus handler
    # ----: bindings
    # TODO: commands
    # TODO: standard dialog boxes, open, save, print, confirm
    # ----: all static text (checkbox 'text') should be bindable
    # TODO: how to define resources for a sub component?
    # TODO: windows: fit to content; fixed sizes
    # ----: tab label should be bindable
    # TODO: window and dialog title should be bindable
    # ----: placeholder text should be bindable
    # TODO: text color, font, etc. bindable

    def __init__(self) -> None:
        pass

    def __process_common_properties(self, d: typing.MutableMapping[str, typing.Any], **kwargs: typing.Any) -> None:
        common_properties = (
            "enabled",
            "visible",
            "width",
            "min_width",
            "max_width",
            "height",
            "min_height",
            "max_height",
            "size_policy_horizontal",
            "size_policy_vertical",
            "tool_tip",
            "color",
            "font",
            "background_color",
            "border_color",
            "widget_id",
            "style"
        )
        for k in common_properties:
            if k in kwargs and kwargs[k] is not None:
                d[k] = kwargs[k]

    def create_column(self, *children: UIDescription, name: typing.Optional[UIIdentifier] = None,
                      items: typing.Optional[UIIdentifier] = None, item_component_id: typing.Optional[str] = None,
                      spacing: typing.Optional[UIPoints] = None, margin: typing.Optional[UIPoints] = None,
                      **kwargs: typing.Any) -> UIDescriptionResult:
        """Create a column UI description with children or dynamic items, spacing, and margin.

        The children can be passed as parameters or constructed from an observable list specified by `items` and
        `item_component_id`.

        If the children are constructed from an observable list, a component instance will be created for each item
        in the list. Adding or removing items from the list will dynamically update the children. The associated
        handler must implement the `resources` property with a value for the key `item_component_id` describing the
        component UI. It must also implement `create_handler` to create a handler for each component. The
        `create_handler` call will receive two extra keyword arguments `container` and `item` in additional to the
        `component_id`.

        Args:
            children: children to put into the column

        Keyword Args:
            items: handler observable list property from which to build child components
            item_component_id: resource identifier of component ui description for child components
            spacing: spacing between items, in points
            margin: margin, in points

        Returns:
            a UI description of the column
        """
        d: UIDescriptionResult = {"type": "column"}
        if name is not None:
            d["name"] = name
        if items:
            d["items"] = items
        if item_component_id:
            d["item_component_id"] = item_component_id
        if spacing is not None:
            d["spacing"] = spacing
        if margin is not None:
            d["margin"] = margin
        if len(children) > 0:
            d_children = d.setdefault("children", list())
            for child in children:
                d_children.append(child)
        self.__process_common_properties(d, **kwargs)
        return d

    def create_row(self, *children: UIDescription, name: typing.Optional[UIIdentifier] = None,
                   items: typing.Optional[UIIdentifier] = None, item_component_id: typing.Optional[str] = None,
                   spacing: typing.Optional[UIPoints] = None, margin: typing.Optional[UIPoints] = None,
                   **kwargs: typing.Any) -> UIDescriptionResult:
        """Create a row UI description with children or dynamic items, spacing, and margin.

        The children can be passed as parameters or constructed from an observable list specified by `items` and
        `item_component_id`.

        If the children are constructed from an observable list, a component instance will be created for each item
        in the list. Adding or removing items from the list will dynamically update the children. The associated
        handler must implement the `resources` property with a value for the key `item_component_id` describing the
        component UI. It must also implement `create_handler` to create a handler for each component. The
        `create_handler` call will receive two extra keyword arguments `container` and `item` in additional to the
        `component_id`.

        Args:
            children: children to put into the row

        Keyword Args:
            items: handler observable list property from which to build child components
            item_component_id: resource identifier of component ui description for child components
            spacing: spacing between items, in points
            margin: margin, in points

        Returns:
            a UI description of the row
        """
        d: UIDescriptionResult = {"type": "row"}
        if name is not None:
            d["name"] = name
        if items:
            d["items"] = items
        if item_component_id:
            d["item_component_id"] = item_component_id
        if spacing is not None:
            d["spacing"] = spacing
        if margin is not None:
            d["margin"] = margin
        if len(children) > 0:
            d_children = d.setdefault("children", list())
            for child in children:
                d_children.append(child)
        self.__process_common_properties(d, **kwargs)
        return d

    def create_spacing(self, size: UIPoints) -> UIDescriptionResult:
        """Create a spacing UI description for a row or column.

        Keyword Args:
            size: spacing, in points

        Returns:
            a UI description of the spacing
        """
        return {"type": "spacing", "size": size}

    def create_stretch(self) -> UIDescriptionResult:
        """Create a stretch UI description for a row or column.

        Returns:
            a UI description of the stretch
        """
        return {"type": "stretch"}

    def create_section(self, content: UIDescription, name: typing.Optional[UIIdentifier] = None,
                       title: typing.Optional[UILabel] = None, expanded: typing.Optional[UILabel] = None,
                       **kwargs: typing.Any) -> UIDescriptionResult:
        """Create a section UI description with title, content.

        Args:
            content: UI description of the content

        Keyword Args:
            name: handler property in which to store widget (optional)
            title: title of the section
            margin: margin in points

        Returns:
            UI description of the section
        """
        d: UIDescriptionResult = {"type": "section", "content": content}
        if name is not None:
            d["name"] = name
        if title is not None:
            d["title"] = title
        if expanded is not None:
            d["expanded"] = expanded
        self.__process_common_properties(d, **kwargs)
        return d

    def create_tab(self, label: UILabel, content: UIDescription) -> UIDescriptionResult:
        """Create a tab UI description with a label and content.

        Args:
            label: label for the tab
            content: UI description of the content

        Returns:
            a UI description of the tab
        """
        return {"type": "tab", "label": label, "content": content}

    def create_tabs(self, *tabs: UIDescription, name: typing.Optional[UIIdentifier] = None,
                    current_index: typing.Optional[UIIdentifier] = None,
                    on_current_index_changed: typing.Optional[UICallableIdentifier] = None,
                    **kwargs: typing.Any) -> UIDescriptionResult:
        """Create a tabs UI description with children, the current index and optional changed event.

        The children must be tabs created by :py:meth:`create_tab`.

        The current_index controls which tab is displayed.

        The on_current_index_changed callback reference takes ``widget`` and ``current_index`` parameters. The type
        signature in the handler should be ``typing.Callable[[UIWidget, int], None]``.

        Args:
            children: child tabs

        Keyword Args:
            name: handler property in which to store widget (optional)
            current_index: current index handler reference (bindable, optional)
            on_current_index_changed: callback when current index changes (optional)

        Returns:
            a UI description of the tabs
        """
        d: UIDescriptionResult = {"type": "tabs"}
        if len(tabs) > 0:
            d_children = d.setdefault("tabs", list())
            for child in tabs:
                d_children.append(child)
        if name is not None:
            d["name"] = name
        if current_index is not None:
            d["current_index"] = current_index
        if on_current_index_changed is not None:
            d["on_current_index_changed"] = on_current_index_changed
        self.__process_common_properties(d, **kwargs)
        return d

    def create_stack(self, *children: UIDescription, items: typing.Optional[UIIdentifier] = None,
                     item_component_id: typing.Optional[str] = None, name: typing.Optional[UIIdentifier] = None,
                     current_index: typing.Optional[UIIdentifier] = None,
                     on_current_index_changed: typing.Optional[UICallableIdentifier] = None,
                     **kwargs: typing.Any) -> UIDescriptionResult:
        """Create a stack UI description with children or dynamic items, the current index and optional changed event.

        The children can be passed as parameters or constructed from an observable list specified by `items` and
        `item_component_id`.

        If the children are constructed from an observable list, a component instance will be created for each item
        in the list. Adding or removing items from the list will dynamically update the children. The associated
        handler must implement the `resources` property with a value for the key `item_component_id` describing the
        component UI. It must also implement `create_handler` to create a handler for each component. The
        `create_handler` call will receive two extra keyword arguments `container` and `item` in additional to the
        `component_id`.

        The current_index controls which child is displayed.

        The on_current_index_changed callback reference takes ``widget`` and ``current_index`` parameters. The type
        signature in the handler should be ``typing.Callable[[UIWidget, int], None]``.

        Args:
            children: stack items

        Keyword Args:
            items: handler observable list property from which to build child components
            item_component_id: resource identifier of component ui description for child components
            name: handler property in which to store widget (optional)
            current_index: current index handler reference (bindable, optional)
            on_current_index_changed: callback when current index changes (optional)

        Returns:
            a UI description of the stack
        """
        d: UIDescriptionResult = {"type": "stack"}
        if len(children) > 0:
            d_children = d.setdefault("children", list())
            for child in children:
                d_children.append(child)
        if items:
            d["items"] = items
        if item_component_id:
            d["item_component_id"] = item_component_id
        if name is not None:
            d["name"] = name
        if current_index is not None:
            d["current_index"] = current_index
        if on_current_index_changed is not None:
            d["on_current_index_changed"] = on_current_index_changed
        self.__process_common_properties(d, **kwargs)
        return d

    def create_scroll_area(self, content: UIDescription, name: typing.Optional[UIIdentifier] = None,
                           **kwargs: typing.Any) -> UIDescriptionResult:
        """Create a scroll area UI description with content and a name.

        Args:
            content: UI description of the content

        Keyword Args:
            name: handler property in which to store widget (optional)

        Returns:
            UI description of the scroll area
        """
        d: UIDescriptionResult = {"type": "scroll_area", "content": content}
        if name is not None:
            d["name"] = name
        self.__process_common_properties(d, **kwargs)
        return d

    def create_group(self, content: UIDescription, name: typing.Optional[UIIdentifier] = None,
                     title: typing.Optional[UILabel] = None, margin: typing.Optional[UIPoints] = None,
                     **kwargs: typing.Any) -> UIDescriptionResult:
        """Create a group UI description with content, a name, a title, and a margin.

        Args:
            content: UI description of the content

        Keyword Args:
            name: handler property in which to store widget (optional)
            title: title of the group
            margin: margin in points

        Returns:
            UI description of the group
        """
        d: UIDescriptionResult = {"type": "group", "content": content}
        if name is not None:
            d["name"] = name
        if title is not None:
            d["title"] = title
        if margin is not None:
            d["margin"] = margin
        self.__process_common_properties(d, **kwargs)
        return d

    def create_label(self, *, text: typing.Optional[UILabel] = None, name: typing.Optional[UIIdentifier] = None,
                     **kwargs: typing.Any) -> UIDescriptionResult:
        """Create a label UI description with text and an optional name.

        Keyword Args:
            text: text of the label (bindable)
            name: handler property in which to store widget (optional)
            width: width in points (optional, default None)

        Returns:
            UI description of the label
        """
        d: UIDescriptionResult = {"type": "text_label"}
        if text is not None:
            d["text"] = text
        if name is not None:
            d["name"] = name
        self.__process_common_properties(d, **kwargs)
        if "word_wrap" in kwargs:
            d["word_wrap"] = bool(kwargs["word_wrap"])
        return d

    def create_image(self, *, image: typing.Optional[UIIdentifier] = None, name: typing.Optional[UIIdentifier] = None,
                     on_clicked: typing.Optional[UICallableIdentifier] = None,
                     **kwargs: typing.Any) -> UIDescriptionResult:
        """Create an image UI description with image, name, an event.

        The ``on_clicked`` callback is invoked when the user clicks the image. The widget is passed to the callback.
        The type signature in the handler should be ``typing.Callable[[UIWidget], None]``.

        Keyword Args:
            image: image, bindable to numpy uint32 bgra array
            name: handler property in which to store widget (optional)
            width: width in points (optional, default None)
            on_clicked: callback when button clicked

        Returns:
            UI description of the push button
        """
        d: UIDescriptionResult = {"type": "image"}
        if image is not None:
            d["image"] = image
        if name is not None:
            d["name"] = name
        if on_clicked is not None:
            d["on_clicked"] = on_clicked
        self.__process_common_properties(d, **kwargs)
        return d

    def create_line_edit(self, *,
                         text: typing.Optional[UIIdentifier] = None,
                         name: typing.Optional[UIIdentifier] = None,
                         editable: typing.Optional[bool] = None,
                         placeholder_text: typing.Optional[UILabel] = None,
                         clear_button_enabled: typing.Optional[bool] = None,
                         on_editing_finished: typing.Optional[UICallableIdentifier] = None,
                         on_escape_pressed: typing.Optional[UICallableIdentifier] = None,
                         on_return_pressed: typing.Optional[UICallableIdentifier] = None,
                         on_key_pressed: typing.Optional[UICallableIdentifier] = None,
                         on_text_edited: typing.Optional[UICallableIdentifier] = None,
                         **kwargs: typing.Any) -> UIDescriptionResult:
        """Create a line edit UI description with text, name, placeholder, options, and events.

        The ``on_editing_finished`` callback is invoked when the user presses return or escape or when they change
        keyboard focus away from the line edit. The line edit widget and string are passed to the callback. The type
        signature in the handler should be ``typing.Callable[[UIWidget, str], None]``.

        The ``on_escape_pressed`` and ``on_return_pressed`` callbacks are invoked when the user presses escape or
        return. The line edit widget is passed and these methods must return ``True`` if they handle the key or
        ``False`` otherwise. Their type signatures in the handler should be ``typing.Callable[[UIWidget], bool]``.

        The ``on_key_pressed`` callback is invoked when the user types a key. The line edit widget and a key instance
        are passed. This method should return ``True`` if the key is handled (it will not go into the line edit field)
        and return ``False`` if not handled (it will be entered as regular text). The type signature in the handler
        should be ``typing.Callable[[UIWidget, UIKey], bool]``.

        The ``on_text_edited`` callback is invoked when the user changes the text. The line edit widget and the new text
        are passed to the callback. The type signature in the handler should be ``typing.Callable[[UIWidget, str],
        None]``.

        Keyword Args:
            text: handler reference to line edit text (bindable, required)
            name: handler property in which to store widget (optional)
            editable: whether the line edit text is editable (optional, default True)
            placeholder_text: text to display when line edit is empty (optional)
            clear_button_enabled: whether the clear button is enabled (optional, default False)
            width: width in points (optional, default None)
            on_editing_finished: callback when editing is finished (return or blur focus)
            on_escape_pressed: callback when escape is pressed, return true if handled
            on_return_pressed: callback when return is pressed, return true if handled
            on_key_pressed: callback when a key is pressed, return true if handled
            on_text_edited: callback when text is edited

        Returns:
            UI description of the line edit
        """
        d: UIDescriptionResult = {"type": "line_edit"}
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
        self.__process_common_properties(d, **kwargs)
        return d

    def create_text_edit(self, *,
                         text: typing.Optional[UIIdentifier] = None,
                         name: typing.Optional[UIIdentifier] = None,
                         editable: typing.Optional[bool] = None,
                         placeholder_text: typing.Optional[UILabel] = None,
                         clear_button_enabled: typing.Optional[bool] = None,
                         on_escape_pressed: typing.Optional[UICallableIdentifier] = None,
                         on_return_pressed: typing.Optional[UICallableIdentifier] = None,
                         on_text_edited: typing.Optional[UICallableIdentifier] = None,
                         **kwargs: typing.Any) -> UIDescriptionResult:
        """Create a multi-line text edit UI description with text, name, placeholder, options, and events.

        The ``on_escape_pressed`` and ``on_return_pressed`` callbacks are invoked when the user presses escape or
        return. The text edit widget is passed and these methods must return ``True`` if they handle the key or
        ``False`` otherwise. Their type signatures in the handler should be ``typing.Callable[[UIWidget], bool]``.

        The ``on_text_edited`` callback is invoked when the user changes the text. The text edit widget and the new text
        are passed to the callback. The type signature in the handler should be ``typing.Callable[[UIWidget, str],
        None]``.

        Keyword Args:
            text: handler reference to line edit text (bindable, required)
            name: handler property in which to store widget (optional)
            editable: whether the line edit text is editable (optional, default True)
            placeholder_text: text to display when line edit is empty (optional)
            clear_button_enabled: whether the clear button is enabled (optional, default False)
            width: width in points (optional, default None)
            height: width in points (optional, default None)
            on_escape_pressed: callback when escape is pressed, return true if handled
            on_return_pressed: callback when return is pressed, return true if handled
            on_text_edited: callback when text is edited

        Returns:
            UI description of the text edit
        """
        d: UIDescriptionResult = {"type": "text_edit"}
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
        if on_escape_pressed is not None:
            d["on_escape_pressed"] = on_escape_pressed
        if on_return_pressed is not None:
            d["on_return_pressed"] = on_return_pressed
        if on_text_edited is not None:
            d["on_text_edited"] = on_text_edited
        self.__process_common_properties(d, **kwargs)
        return d

    def create_push_button(self, *, text: typing.Optional[UILabel] = None, icon: typing.Optional[UIIdentifier] = None,
                           name: typing.Optional[UIIdentifier] = None,
                           on_clicked: typing.Optional[UICallableIdentifier] = None,
                           **kwargs: typing.Any) -> UIDescriptionResult:
        """Create a push button UI description with text, name, an event.

        The ``on_clicked`` callback is invoked when the user clicks the button. The widget is passed to the callback.
        The type signature in the handler should be ``typing.Callable[[UIWidget], None]``.

        Keyword Args:
            text: text of the label (bindable)
            icon: icon, bindable to numpy uint32 bgra array
            name: handler property in which to store widget (optional)
            width: width in points (optional, default None)
            on_clicked: callback when button clicked

        Returns:
            UI description of the push button
        """
        d: UIDescriptionResult = {"type": "push_button"}
        if text is not None:
            d["text"] = text
        if icon is not None:
            d["icon"] = icon
        if name is not None:
            d["name"] = name
        if on_clicked is not None:
            d["on_clicked"] = on_clicked
        self.__process_common_properties(d, **kwargs)
        return d

    def create_check_box(self, *,
                         text: typing.Optional[UILabel] = None,
                         icon: typing.Optional[UIIdentifier] = None,
                         name: typing.Optional[UIIdentifier] = None,
                         checked: typing.Optional[str] = None,
                         check_state: typing.Optional[str] = None,
                         tristate: typing.Optional[bool] = None,
                         on_checked_changed: typing.Optional[UICallableIdentifier] = None,
                         on_check_state_changed: typing.Optional[UICallableIdentifier] = None,
                         **kwargs: typing.Any) -> UIDescriptionResult:
        """Create a check box UI description with text, name, state information, and events.

        The ``checked`` and ``check_state`` both refer to the check state. Some callers may choose to use the simpler
        ``checked`` which is a simple boolean. ``check_state`` is a string and must be one of 'checked', 'unchecked', or
        'partial'. 'partial' is only valid if ``tristate`` is ``True``.

        The ``on_checked_changed`` callback is invoked when the user changes the state of the check box. The widget and
        the new state of the check box are passed to the callback. The type signature in the handler should be
        ``typing.Callable[[UIWidget, bool], None]``.

        The ``on_check_state_changed`` callback is invoked when the user changes the state of the check box, but it also
        includes the 'partial' state if enabled. The widget and the new state of the check box are passed to the
        callback. The type signature in the handler should be ``typing.Callable[[UIWidget, str], None]``.

        Keyword Args:
            text: text of the label (bindable)
            name: handler property in which to store widget (optional)
            checked: checked state (bool)
            check_state: checked state (string: checked, unchecked, or partial)
            tristate: whether the check box is tristate or not
            on_checked_changed: callback when checked changes (optional)
            on_check_state_changed: callback when check state changes (optional)

        Returns:
            UI description of the check box
        """
        d: UIDescriptionResult = {"type": "check_box"}
        if text is not None:
            d["text"] = text
        if icon is not None:
            d["icon"] = icon
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
        self.__process_common_properties(d, **kwargs)
        return d

    def create_combo_box(self, *,
                         name: typing.Optional[UIIdentifier] = None,
                         items: typing.Optional[typing.Sequence[UILabel]] = None,
                         items_ref: typing.Optional[UIIdentifier] = None,
                         current_index: typing.Optional[UIIdentifier] = None,
                         on_current_index_changed: typing.Optional[UICallableIdentifier] = None,
                         **kwargs: typing.Any) -> UIDescriptionResult:
        """Create a combo box UI description with name, items, current index, and events.

        The ``on_current_index_changed`` callback is invoked when the user changes the selected item in the combo box.
        The widget and the new index of the selected item are passed to the callback. The type signature in the handler
        should be ``typing.Callable[[UIWidget, int], None]``.

        Keyword Args:
            name: handler property in which to store widget (optional)
            items: list combo box items (strings, optional)
            items_ref: handler reference of combo box items (bindable, optional)
            current_index: current index handler reference (bindable, optional)
            on_current_index_changed: callback when current index changes (optional)

        Returns:
            UI description of the combo box
        """
        d: UIDescriptionResult = {"type": "combo_box"}
        if name is not None:
            d["name"] = name
        if items is not None:
            d["items"] = list(items)
        if items_ref is not None:
            d["items_ref"] = items_ref
        if current_index is not None:
            d["current_index"] = current_index
        if on_current_index_changed is not None:
            d["on_current_index_changed"] = on_current_index_changed
        self.__process_common_properties(d, **kwargs)
        return d

    def create_radio_button(self, *,
                            name: typing.Optional[UIIdentifier] = None,
                            text: typing.Optional[UILabel] = None,
                            icon: typing.Optional[UIIdentifier] = None,
                            value: typing.Any = None,
                            group_value: typing.Optional[UIIdentifier] = None,
                            **kwargs: typing.Any) -> UIDescriptionResult:
        """Create a radio button UI description with text, name, value, and group value.

        A set of radio buttons should be created such that each has a different ``value`` but shares a common
        ``group_value``. The type of ``value`` must match the type of ``group_value``.

        Keyword Args:
            name: handler property in which to store widget (optional)
            text: text of the label (bindable)
            value: unique value within its group (required)
            group_value: common value handler reference (bindable, required)

        Returns:
            UI description of the radio button
        """
        d: UIDescriptionResult = {"type": "radio_button"}
        if name is not None:
            d["name"] = name
        if text is not None:
            d["text"] = text
        if icon is not None:
            d["icon"] = icon
        if value is not None:
            d["value"] = value
        if group_value is not None:
            d["group_value"] = group_value
        self.__process_common_properties(d, **kwargs)
        return d

    def create_slider(self, *,
                      name: typing.Optional[UIIdentifier] = None,
                      value: typing.Optional[UIIdentifier] = None,
                      minimum: typing.Optional[int] = None,
                      maximum: typing.Optional[int] = None,
                      on_value_changed: typing.Optional[UICallableIdentifier] = None,
                      on_slider_pressed: typing.Optional[UICallableIdentifier] = None,
                      on_slider_released: typing.Optional[UICallableIdentifier] = None,
                      on_slider_moved: typing.Optional[UICallableIdentifier] = None,
                      **kwargs: typing.Any) -> UIDescriptionResult:
        """Create a slider UI description with name, value, limits, and events.

        The ``on_value_changed`` callback is invoked whenever the slider value changes, including if set
        programmatically. The widget and the new value are passed to the callback. The type signature in the handler
        should be ``typing.Callable[[UIWidget, int], None]``.

        The ``on_slider_pressed`` callback is invoked when the user begins dragging the slider. The widget is passed to
        the callback. The type signature in the handler should be ``typing.Callable[[UIWidget], None]``.

        The ``on_slider_released`` callback is invoked when the user stops dragging the slider. The widget is passed to
        the callback. The type signature in the handler should be ``typing.Callable[[UIWidget], None]``.

        The ``on_slider_moved`` callback is invoked whenever the slider value changes while the user is dragging. The
        widget and the new value are passed to the callback. The type signature in the handler should be
        ``typing.Callable[[UIWidget, int], None]``.

        Keyword Args:
            name: handler property in which to store widget (optional)
            value: handler reference to the current value (required, bindable)
            minimum: minimum value (default 0)
            maximum: maximum value (default 100)
            on_value_changed: callback when value changes, any source (optional)
            on_slider_pressed: callback when slider is pressed (optional)
            on_slider_released: callback when slider is released (optional)
            on_slider_moved: callback when slider moves, user initiated only (optional)

        Returns:
            UI description of the slider
        """
        d: UIDescriptionResult = {"type": "slider"}
        if name is not None:
            d["name"] = name
        if value is not None:
            d["value"] = value
        if minimum is not None:
            d["minimum"] = minimum
        if maximum is not None:
            d["maximum"] = maximum
        if on_value_changed is not None:
            d["on_value_changed"] = on_value_changed
        if on_slider_pressed is not None:
            d["on_slider_pressed"] = on_slider_pressed
        if on_slider_released is not None:
            d["on_slider_released"] = on_slider_released
        if on_slider_moved is not None:
            d["on_slider_moved"] = on_slider_moved
        self.__process_common_properties(d, **kwargs)
        return d

    def create_divider(self, *,
                       name: typing.Optional[UIIdentifier] = None,
                       orientation: typing.Optional[str] = None,
                       **kwargs: typing.Any) -> UIDescriptionResult:
        """Create a divider description with name and orientation.

        Keyword Args:
            name: handler property in which to store widget (optional)
            orientation: "horizontal" or "vertical" (default)
        """
        d: UIDescriptionResult = {"type": "divider"}
        if name is not None:
            d["name"] = name
        if orientation is not None:
            d["orientation"] = orientation
        self.__process_common_properties(d, **kwargs)
        return d

    def create_progress_bar(self, *,
                            name: typing.Optional[UIIdentifier] = None,
                            value: typing.Optional[UIIdentifier] = None,
                            minimum: typing.Optional[int] = None,
                            maximum: typing.Optional[int] = None,
                            **kwargs: typing.Any) -> UIDescriptionResult:
        """Create a progress bar UI description with name, value, and limits.

        Keyword Args:
            name: handler property in which to store widget (optional)
            value: handler reference to the current value (required, bindable)
            minimum: minimum value (default 0)
            maximum: maximum value (default 100)

        Returns:
            UI description of the progress bar
        """
        d: UIDescriptionResult = {"type": "progress_bar"}
        if name is not None:
            d["name"] = name
        if value is not None:
            d["value"] = value
        if minimum is not None:
            d["minimum"] = minimum
        if maximum is not None:
            d["maximum"] = maximum
        self.__process_common_properties(d, **kwargs)
        return d

    def create_list_box(self, *,
                        name: typing.Optional[UIIdentifier] = None,
                        items: typing.Optional[typing.Sequence[typing.Union[UILabel, typing.Any]]] = None,
                        items_ref: typing.Optional[UIIdentifier] = None,
                        current_index: typing.Optional[UIIdentifier] = None,
                        on_item_changed: typing.Optional[UICallableIdentifier] = None,
                        on_item_selected: typing.Optional[UICallableIdentifier] = None,
                        on_escape_pressed: typing.Optional[UICallableIdentifier] = None,
                        on_return_pressed: typing.Optional[UICallableIdentifier] = None,
                        on_item_handle_context_menu: typing.Optional[UICallableIdentifier] = None,
                        **kwargs: typing.Any) -> UIDescriptionResult:
        """Create a list box UI description with name, items, current index, and events.

        Keyword Args:
            name: handler property in which to store widget (optional)
            items: list list box items (strings or objects which have str conversion, optional)
            items_ref: handler reference of list box items (bindable, optional)
            current_index: current index handler reference (bindable, optional)
            on_item_changed: callback when current item changes (optional)
            on_item_selected: callback when current item changes (optional)
            on_escape_pressed: callback when escape is pressed, return true if handled
            on_return_pressed: callback when return is pressed, return true if handled
            on_item_handle_context_menu: callback to display context menu, passes gx, gy, index (optional).

        Returns:
            UI description of the list box

        The ``on_current_index_changed`` callback is invoked when the user changes the selected item in the list box.
        The widget and the new index of the selected item are passed to the callback. The type signature in the handler
        should be ``typing.Callable[[UIWidget, int], None]``.

        The items can be either strings or objects which implement a str conversion. The items can also include a
        `tool_tip` property which will be displayed when the user hovers over the item.
        """
        d: UIDescriptionResult = {"type": "list_box"}
        if name is not None:
            d["name"] = name
        if items is not None:
            d["items"] = list(items)
        if items_ref is not None:
            d["items_ref"] = items_ref
        if current_index is not None:
            d["current_index"] = current_index
        if on_item_changed is not None:
            d["on_item_changed"] = on_item_changed
        if on_item_selected is not None:
            d["on_item_selected"] = on_item_selected
        if on_escape_pressed is not None:
            d["on_escape_pressed"] = on_escape_pressed
        if on_return_pressed is not None:
            d["on_return_pressed"] = on_return_pressed
        if on_item_handle_context_menu is not None:
            d["on_item_handle_context_menu"] = on_item_handle_context_menu
        self.__process_common_properties(d, **kwargs)
        return d

    def create_modeless_dialog(self, content: UIDescription, *, title: typing.Optional[str] = None,
                               resources: typing.Optional[UIResources] = None,
                               margin: typing.Optional[UIPoints] = None) -> UIDescriptionResult:
        """Create a modeless dialog UI description with content, title, resources, and margin.

        Args:
            content: UI description of the content

        Keyword Args:
            title: title of the window
            resources: additional resources
            margin: margin in points

        Returns:
            a UI description of the dialog
        """
        d: UIDescriptionResult = {"type": "modeless_dialog", "content": content}
        if title is not None:
            d["title"] = title
        if margin is not None:
            d["margin"] = margin
        if resources is not None:
            d["resources"] = resources
        return d

    def create_window(self, content: UIDescription, *, title: typing.Optional[str] = None,
                      resources: typing.Optional[UIResources] = None, margin: typing.Optional[UIPoints] = None,
                      window_style: typing.Optional[str] = None) -> UIDescriptionResult:
        """Create a window UI description with content, title, resources, and margin.

        Args:
            content: UI description description of the content

        Keyword Args:
            title: title of the window
            resources: additional resources
            margin: margin in points

        Returns:
            a UI description of the window
        """
        d: UIDescriptionResult = {"type": "window", "content": content}
        if title is not None:
            d["title"] = title
        if margin is not None:
            d["margin"] = margin
        if resources is not None:
            d["resources"] = resources
        if window_style is not None:
            d["window_style"] = window_style
        return d

    def define_component(self, content: UIDescription, *, component_id: typing.Optional[str] = None,
                         events: typing.Optional[typing.Sequence[typing.Mapping[str, typing.Any]]] = None) -> UIDescriptionResult:
        d: UIDescriptionResult = {"type": "component", "content": content}
        if component_id is not None:
            d["component_id"] = component_id
        if events is not None:
            d["events"] = events
        return d

    def create_component_instance(self, identifier: str,
                                  properties: typing.Optional[typing.Mapping[str, typing.Any]] = None,
                                  **kwargs: typing.Any) -> UIDescriptionResult:
        properties = properties if properties is not None else dict()
        d: UIDescriptionResult = {"type": "component", "identifier": identifier, "properties": properties}
        for k, v in kwargs.items():
            d[k] = v
        return d


class HandlerLike(typing.Protocol):
    def close(self) -> None: ...


class Handler(Observable.Observable, HandlerLike):
    def __init__(self) -> None:
        super().__init__()

    def close(self) -> None:
        pass


def connect_name(widget: UserInterface.Widget, d: UIDescription, handler: HandlerLike) -> None:
    name = d.get("name", None)
    if name:
        setattr(handler, name, widget)


def parse_property_path(property_path: str, base: typing.Any) -> typing.Tuple[typing.Any, str, typing.Any]:
    handler_property_path = property_path.split('.')
    source = base
    for p in handler_property_path[:-1]:
        source = getattr(source, p.strip())
    last_property_path_component = handler_property_path[-1].strip()
    return source, last_property_path_component, getattr(source, last_property_path_component, None)


def connect_string_value(widget: UserInterface.Widget, d: UIDescription, handler: HandlerLike, property: str,
                         finishes: _FinishesListType) -> None:
    """Connects a value in the property, but also allows binding.

    A value means the value for the property is directly contained in the string.
    """
    v = d.get(property)
    m = re.match("^@binding\((.+)\)$", v if v else "")
    # print(f"{v}, {m}, {m.group(1) if m else 'NA'}")
    if m:
        b = m.group(1)
        parts = [p.strip() for p in b.split(',')]
        def finish_binding() -> None:
            source, last_property_path_component, value = parse_property_path(parts[0], handler)
            converter = None
            for part in parts:
                if part.startswith("converter="):
                    converter = getattr(handler, part[len("converter="):])
            if hasattr(source, "property_changed_event"):
                binding = None
                get_binding = getattr(handler, "get_binding", None)
                if callable(get_binding):
                    binding = get_binding(source, last_property_path_component, converter=converter)
                binding = binding or Binding.PropertyBinding(source, last_property_path_component, converter=converter)
                getattr(widget, "bind_" + property)(binding)
            else:
                setattr(widget, property, str(value))
        finishes.append(finish_binding)
    else:
        setattr(widget, property, v)


class Closer:
    """A helper class to facilitate closing handlers and associated closeable items.

    A closer is attached to each handler and used to close the handler, extra closeable items that the engine may
    created, and child component handlers.
    """
    def __init__(self) -> None:
        self.__handlers: typing.Set[HandlerLike] = set()

    def push_closeable(self, handler: HandlerLike) -> None:
        assert handler not in self.__handlers
        self.__handlers.add(handler)

    def pop_closeable(self, handler: HandlerLike) -> None:
        assert handler in self.__handlers
        if callable(getattr(handler, "close", None)):
            handler.close()
        if hasattr(handler, "_closer"):
            getattr(handler, "_closer").close()
        self.__handlers.remove(handler)

    def close(self) -> None:
        for handler in self.__handlers:
            if callable(getattr(handler, "close", None)):
                handler.close()
            if hasattr(handler, "_closer"):
                getattr(handler, "_closer").close()
        self.__handlers = typing.cast(typing.Any, None)


def connect_reference_value(bindable: typing.Any, d: UIDescription, handler: HandlerLike, property: str,
                            finishes: _FinishesListType, binding_name: typing.Optional[str] = None,
                            value_type: typing.Optional[typing.Any] = None) -> None:
    """Connects a reference to the property, but also allows binding.

    A reference means the property specifies a property in the handler.
    """
    binding_name_ = binding_name if binding_name else property
    v = d.get(property)
    m = re.match("^@binding\((.+)\)$", v if isinstance(v, str) else "")
    # print(f"{v}, {m}, {m.group(1) if m else 'NA'}")
    if m:
        b = m.group(1)
        parts = [p.strip() for p in b.split(',')]

        # finish binding is called after the window has been constructed using the 'finishes' list.
        def finish_binding() -> None:
            source, last_property_path_component, value = parse_property_path(parts[0], handler)
            converter = None
            # check if any of the parts has a converter.
            for part in parts:
                if part.startswith("converter="):
                    converter = getattr(handler, part[len("converter="):])
            # give the handler a chance to make object conversions. this is useful if the objects
            # in the handler are stored in a proxy format or something similar.
            if getattr(handler, "get_object_converter", None):
                converter = getattr(handler, "get_object_converter")(converter)
            # configure the binding if the source and widget meet the criteria.
            if hasattr(source, "property_changed_event") and hasattr(bindable, "bind_" + binding_name_):
                binding = None
                get_binding = getattr(handler, "get_binding", None)
                if callable(get_binding):
                    binding = get_binding(source, last_property_path_component, converter=converter)
                binding = binding or Binding.PropertyBinding(source, last_property_path_component, converter=converter)
                getattr(bindable, "bind_" + binding_name_)(binding)
            # otherwise as a fallback, set the value.
            else:
                setattr(bindable, binding_name_, value)

        finishes.append(finish_binding)
    elif v is not None:
        if value_type == str and hasattr(handler, v):
            # backwards compatible binding
            setattr(bindable, binding_name_, getattr(handler, v))
        elif value_type and isinstance(v, value_type):
            setattr(bindable, binding_name_, v)
        else:
            setattr(bindable, binding_name_, getattr(handler, v))


def connect_event(widget: UserInterface.Widget, source: typing.Any, d: UIDescription, handler: HandlerLike,
                  event_str: str, arg_names: typing.Sequence[str]) -> None:
    event_method_name = d.get(event_str, None)
    if event_method_name:
        event_fn = getattr(handler, event_method_name)
        if event_fn:
            def trampoline(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
                combined_args = dict()
                for arg_name, arg in zip(arg_names, args):
                    combined_args[arg_name] = arg
                combined_args.update(kwargs)
                return event_fn(widget, **combined_args)
            setattr(source, event_str, trampoline)
        else:
            print("WARNING: '" + event_str + "' method " + event_method_name + " not found in handler.")


def connect_attributes(widget: UserInterface.Widget, d: UIDescription, handler: HandlerLike, finishes: _FinishesListType) -> None:
    connect_reference_value(widget, d, handler, "enabled", finishes, value_type=bool)
    connect_reference_value(widget, d, handler, "visible", finishes, value_type=bool)
    connect_string_value(widget, d, handler, "tool_tip", finishes)
    connect_reference_value(widget, d, handler, "background_color", finishes, value_type=str)
    connect_reference_value(widget, d, handler, "border_color", finishes, value_type=str)
    connect_reference_value(widget, d, handler, "color", finishes, value_type=str)
    connect_reference_value(widget, d, handler, "font", finishes, value_type=str)
    widget.widget_id = d.get("widget_id", widget.widget_id)


class WindowHandler(Observable.Observable):
    """Base handler to run a declarative window inside the application.

    `close_window` can be called directly or used as a target for a button.
    """

    def __init__(self, *, completion_fn: typing.Optional[typing.Callable[[], None]] = None):
        super().__init__()
        self.window = typing.cast(Window.Window, None)
        self.__completion_fn = completion_fn
        self.__on_close: typing.Optional[typing.Callable[[], None]] = None

    def close(self) -> None:
        pass

    def close_window(self, widget: typing.Optional[UIWidget] = None) -> None:
        assert self.window
        self.window.request_close()

    def run(self, d: UIDescription, *, app: typing.Optional[Application.BaseApplication] = None,
            parent_window: typing.Optional[Window.Window] = None, window_style: typing.Optional[str] = None,
            persistent_id: typing.Optional[str] = None) -> None:
        self.window = run_window(d, self, app=app, parent_window=parent_window, window_style=window_style, persistent_id=persistent_id)
        self.__on_close = self.window.on_close

        def handle_close() -> None:
            if callable(self.__on_close):
                self.__on_close()
            if callable(self.__completion_fn):
                self.__completion_fn()

        self.window.on_close = handle_close


def run_window(d: UIDescription, handler: HandlerLike, *, app: typing.Optional[Application.BaseApplication] = None,
               parent_window: typing.Optional[Window.Window] = None, window_style: typing.Optional[str] = None,
               persistent_id: typing.Optional[str] = None) -> Window.Window:
    if app:
        ui = app.ui
    else:
        assert parent_window
        ui = parent_window.ui
    d_type = d.get("type")
    assert d_type == "window"
    title = d.get("title", _("Untitled"))
    margin = d.get("margin")
    persistent_id = d.get("persistent_id", persistent_id)
    window_style = d.get("window_style", window_style)
    content = typing.cast(UIDescription, d.get("content"))
    resources = d.get("resources", dict())
    for k, v in resources.items():
        resources[k] = v
    if not hasattr(handler, "resources"):
        setattr(handler, "resources", resources)
    else:
        getattr(handler, "resources").update(resources)
    closer = Closer()
    finishes: _FinishesListType = list()
    window = Window.Window(ui, app=app, parent_window=parent_window, persistent_id=persistent_id, window_style=window_style)
    window.title = title
    window.on_close = closer.close
    # make and attach closer for the handler; put handler into container closer
    setattr(handler, "_closer", Closer())
    closer.push_closeable(handler)
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
    window.attach_widget(outer_row)
    # window._create_menus()  # not needed; see pr#39.
    window.show()
    for finish in finishes:
        finish()
    setattr(handler, "_event_loop", window.event_loop)
    if callable(getattr(handler, "init_handler", None)):
        getattr(handler, "init_handler")()
    return window


def construct_margin(ui: UserInterface.UserInterface, content: UserInterface.BoxWidget, margin: typing.Optional[int]) -> UserInterface.BoxWidget:
    if margin:
        column = ui.create_column_widget()
        column.add_spacing(margin)
        column.add(content)
        column.add_spacing(margin)
        row = ui.create_row_widget()
        row.add_spacing(margin)
        row.add(column)
        row.add_spacing(margin)
        content = row
    return content


# to properly type the container widget needs more work. substitute typing.Any for now.
def connect_items(ui: UserInterface.UserInterface, window: Window.Window, container_widget: typing.Any,
                  handler: HandlerLike, items: str, item_component_id: str, spacing_h: typing.Optional[int] = None,
                  spacing_v: typing.Optional[int] = None) -> None:
    """Connect list of item components to container widget.

    Several declarative elements (columns, rows, stacks) take a list of item components. This method connects the item
    components to the element.

    When an item gets inserted, this method tries a few techniques to construct the content and handler.

    First it checks whether the current handler responds to `get_resource` and calls it with the `item_component_id` to
    establish a component. If not successful, it checks whether the `resources` map is defined on the current handler
    and looks up the `item_component_id`. If either of those succeed, it establishes the `component_id` and
    `component_content` from established component. Otherwise it uses the `item_component_id` as the `component_id`
    and continues.

    Next, it calls `create_handler` with the established `component_id` and `item`. If the handler defines a `ui_view`,
    that is used as the `component_content`; otherwise the `component_content` established earlier is used.

    The preferred technique for dynamic content is to define `create_handler` to return a handler for the given
    `item_component_id` and associated `item` with a defined `ui_view` and do not define `get_resource` or `resources`
    to respond to the `item_component_id`.
    """
    assert window is not None
    items_parts = items.split('.')
    container: typing.Any = handler
    for items_part in items_parts[:-1]:
        container = getattr(container, items_part.strip())
    items_key = items_parts[-1]

    # the _closer should have been set on the handler, even if no close method is present. insert_item makes this
    # assumption so that sub-components have a path by which to get closed.
    assert getattr(handler, "_closer")

    def adjust_spacing() -> None:
        spacing = max(spacing_h or 0, spacing_v or 0)
        if spacing and container_widget.children:
            last_child = container_widget.children[-1]
            for spacing_widget in container_widget.children:
                if spacing_widget != last_child:
                    if len(spacing_widget.children) == 1:
                        spacing_widget.add_spacing(spacing)
                else:
                    if len(spacing_widget.children) == 2:
                        spacing_widget.remove(spacing_widget.children[-1])

    def insert_item(index: int, item: typing.Any) -> None:
        item_widget = None
        component_id: typing.Optional[str]
        component_content: typing.Optional[UIDescription] = None
        component = None
        if callable(getattr(handler, "get_resource", None)):
            component = getattr(handler, "get_resource")(item_component_id, item=item, container=container)
        component = component or getattr(handler, "resources", dict()).get(item_component_id)
        if component:
            assert component.get("type") == "component"
            # the component will have a content portion, which is a widget description. component events are
            # ignored in this case.
            component_id = component.get("component_id", item_component_id)
            component_content = component.get("content")
        else:
            component_id = item_component_id
        if component_id:
            assert component_id == item_component_id
            assert callable(getattr(handler, "create_handler", None))
            # create the handler first, but don't initialize it.
            component_handler = getattr(handler, "create_handler")(component_id=component_id, item=item, container=container)
            # make and attach closer for the component handler and link it to the container handler.
            if component_handler:
                component_handler._closer = Closer()
                getattr(handler, "_closer").push_closeable(component_handler)
                component_content = getattr(component_handler, "ui_view", component_content)
            assert component_content
            item_finishes: _FinishesListType = list()
            # now construct the widget
            item_widget = construct(ui, window, component_content, component_handler, item_finishes)
            # since the handler is custom to the widget, make a way to retrieve it from the widget
            setattr(item_widget, "handler", component_handler)
            for finish in item_finishes:
                finish()
            component_handler._event_loop = window.event_loop
            if callable(getattr(component_handler, "init_handler", None)):
                component_handler.init_handler()
        if spacing_h:
            spacing_widget = ui.create_row_widget()
        else:
            spacing_widget = ui.create_column_widget()
        if item_widget:
            spacing_widget.add(item_widget)
        container_widget.insert(spacing_widget, index)
        adjust_spacing()

    def row_item_inserted(key: str, value: typing.Any, before_index: int) -> None:
        if key == items_key:
            insert_item(before_index, value)

    def row_item_removed(key: str, value: typing.Any, before_index: int) -> None:
         if key == items_key:
            item_widget = container_widget.children[before_index]
            getattr(handler, "_closer").pop_closeable(item_widget.children[0].handler)
            container_widget.remove(item_widget)
            adjust_spacing()

    for item in getattr(container, items_key):
        insert_item(len(container_widget.children), item)

    getattr(handler, "_closer").push_closeable(container.item_inserted_event.listen(row_item_inserted))
    getattr(handler, "_closer").push_closeable(container.item_removed_event.listen(row_item_removed))


def construct_sizing_properties(d: UIDescription) -> UIDescriptionResult:
    properties: UIDescriptionResult = dict()
    for k in ("width", "min_width", "max_width", "height", "min_height", "max_height"):
        v = d.get(k, None)
        if v is not None:
            properties[k.replace("_", "-")] = int(v)
    for k in ("size_policy_horizontal", "size_policy_vertical"):
        v = d.get(k, None)
        if v is not None:
            properties[k.replace("_", "-")] = str(v)
    return properties


class DeclarativeConstructor(typing.Protocol):
    def construct(self, d_type: str, ui: UserInterface.UserInterface, window: Window.Window, d: UIDescription,
                  handler: HandlerLike, finishes: typing.Optional[_FinishesListType] = None) -> UserInterface.Widget:
        ...


def construct(ui: UserInterface.UserInterface, window: Window.Window, d: UIDescription, handler: HandlerLike, finishes: typing.Optional[_FinishesListType] = None) -> UserInterface.Widget:
    finishes = finishes if finishes is not None else list()
    assert finishes is not None
    d_type = typing.cast(str, d.get("type"))
    if d_type == "modeless_dialog":
        # this seems like a type error. is this used anywhere?
        return typing.cast(UserInterface.Widget, construct_modeless_dialog(ui, window, d, handler))
    elif d_type == "column":
        properties = construct_sizing_properties(d)
        return construct_box(ui, window, ui.create_column_widget(properties=properties), d, handler, finishes)
    elif d_type == "row":
        properties = construct_sizing_properties(d)
        return construct_box(ui, window, ui.create_row_widget(properties=properties), d, handler, finishes)
    elif d_type == "text_label":
        return construct_text_label(ui, d, handler, finishes)
    elif d_type == "image":
        return construct_image(ui, d, handler, finishes)
    elif d_type == "line_edit":
        return construct_line_edit(ui, d, finishes, handler)
    elif d_type == "text_edit":
        return construct_text_edit(ui, d, finishes, handler)
    elif d_type == "push_button":
        return construct_push_button(ui, d, handler, finishes)
    elif d_type == "check_box":
        return construct_check_box(ui, d, handler, finishes)
    elif d_type == "combo_box":
        return construct_combo_box(ui, d, handler, finishes)
    elif d_type == "radio_button":
        return construct_radio_button(ui, d, handler, finishes)
    elif d_type == "slider":
        return construct_slider(ui, d, handler, finishes)
    if d_type == "divider":
        return construct_divider(ui, d, handler, finishes)
    elif d_type == "progress_bar":
        return construct_progress_bar(ui, d, handler, finishes)
    elif d_type == "section":
        return construct_section(ui, window, d, handler, finishes)
    elif d_type == "tabs":
        return construct_tabs(ui, window, d, handler, finishes)
    elif d_type == "stack":
        return construct_stack(ui, window, d, handler, finishes)
    elif d_type == "scroll_area":
        return construct_scroll_area(ui, window, d, handler, finishes)
    elif d_type == "group":
        return construct_group(ui, window, d, handler, finishes)
    elif d_type == "list_box":
        return construct_list_box(ui, d, handler, finishes)
    elif d_type == "component":
        return construct_component(ui, window, d, handler, finishes)
    else:
        # if the component is not handled yet, check with registered component handlers.
        constructors = typing.cast(typing.List[DeclarativeConstructor], Registry.get_components_by_type("declarative_constructor"))
        for constructor in constructors:
            widget = constructor.construct(d_type, ui, window, d, handler, finishes)
            if widget:
                return widget
    raise Exception(f"Widget type {d_type} cannot be constructed.")


def construct_component(ui: UserInterface.UserInterface, window: Window.Window, d: UIDescription, handler: HandlerLike,
                        finishes: _FinishesListType) -> ComponentWidget:
    # a component needs to be registered before it is instantiated.
    # look up the identifier in the handler resources.
    widget = ComponentWidget(ui, window, d, handler)
    connect_string_value(widget, d, handler, "identifier", finishes)
    return widget


def construct_list_box(ui: UserInterface.UserInterface, d: UIDescription, handler: HandlerLike,
                       finishes: _FinishesListType) -> Widgets.ListWidget:
    items = d.get("items", None)
    properties = construct_sizing_properties(d)

    class ListBoxDelegate(Widgets.StringListCanvasItemDelegate):
        def __init__(self) -> None:
            super().__init__()
            self.on_item_handle_context_menu: typing.Optional[typing.Callable[..., bool]] = None

        def item_tool_tip(self, index: int) -> typing.Optional[str]:
            return typing.cast(typing.Optional[str], getattr(self.items[index], "tool_tip", None))

        def context_menu_event(self, index: typing.Optional[int], x: int, y: int, gx: int, gy: int) -> bool:
            if callable(self.on_item_handle_context_menu):
                self.on_item_handle_context_menu(index=index, x=x, y=y, gx=gx, gy=gy)
            return False

    list_box_delegate = ListBoxDelegate()
    widget = Widgets.ListWidget(ui, list_box_delegate, items=items, selection_style=Selection.Style.single_or_none,
                                border_color="#888", properties=properties)
    widget.on_item_handle_context_menu = None

    def trampoline_handle_context_menu(*args: typing.Any, **kwargs: typing.Any) -> bool:
        # this will be called from the delegate when the delegate gets a context menu event.
        # the call is passed on to the widget on_item_handle_context_menu function.
        if callable(widget.on_item_handle_context_menu):
            return widget.on_item_handle_context_menu(*args, **kwargs)
        return False

    list_box_delegate.on_item_handle_context_menu = trampoline_handle_context_menu
    if handler:
        connect_name(widget, d, handler)
        # note: items_ref connects before current_index so that current_index can be valid
        connect_reference_value(widget, d, handler, "items_ref", finishes, binding_name="items", value_type=list)
        connect_reference_value(widget, d, handler, "current_index", finishes, value_type=int)
        connect_event(widget, widget, d, handler, "on_item_changed", ["current_index"])
        connect_event(widget, widget, d, handler, "on_item_selected", ["current_index"])
        connect_event(widget, widget, d, handler, "on_escape_pressed", [])
        connect_event(widget, widget, d, handler, "on_return_pressed", [])
        connect_event(widget, widget, d, handler, "on_item_handle_context_menu", ["x", "y", "gx", "gy", "index"])
        connect_attributes(widget, d, handler, finishes)
    return widget


def construct_group(ui: UserInterface.UserInterface, window: Window.Window, d: UIDescription, handler: HandlerLike,
                    finishes: _FinishesListType) -> UserInterface.Widget:
    properties = construct_sizing_properties(d)
    widget = ui.create_group_widget(properties)
    margin = d.get("margin")
    content = typing.cast(UIDescription, d.get("content"))
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
    widget.add(outer_row)
    if handler:
        connect_name(widget, d, handler)
        connect_string_value(widget, d, handler, "title", finishes)
        connect_attributes(widget, d, handler, finishes)
    return widget


def construct_scroll_area(ui: UserInterface.UserInterface, window: Window.Window, d: UIDescription,
                          handler: HandlerLike, finishes: _FinishesListType) -> UserInterface.ScrollAreaWidget:
    properties = construct_sizing_properties(d)
    widget = ui.create_scroll_area_widget(properties)
    widget.set_scrollbar_policies("needed", "needed")
    content = typing.cast(UIDescription, d.get("content"))
    widget.content = construct(ui, window, content, handler, finishes)
    if handler:
        connect_name(widget, d, handler)
        connect_attributes(widget, d, handler, finishes)
    return widget


def construct_stack(ui: UserInterface.UserInterface, window: Window.Window, d: UIDescription, handler: HandlerLike,
                    finishes: _FinishesListType) -> UserInterface.StackWidget:
    properties = construct_sizing_properties(d)
    widget = ui.create_stack_widget(properties)
    for child in d.get("children", list()):
        widget.add(construct(ui, window, child, handler, finishes))
    items = d.get("items")
    item_component_id = d.get("item_component_id")
    if items and item_component_id:
        connect_items(ui, window, widget, handler, items, item_component_id)
    if handler:
        connect_name(widget, d, handler)
        connect_reference_value(widget, d, handler, "current_index", finishes, value_type=int)
        connect_event(widget, widget, d, handler, "on_current_index_changed", ["current_index"])
        connect_attributes(widget, d, handler, finishes)
    return widget


def construct_section(ui: UserInterface.UserInterface, window: Window.Window, d: UIDescription, handler: HandlerLike,
                      finishes: _FinishesListType) -> UserInterface.Widget:
    # properties = construct_sizing_properties(d)
    content = typing.cast(UIDescription, d.get("content"))
    outer_column = ui.create_column_widget()
    inner_content = construct(ui, window, content, handler, finishes)
    outer_column.add(inner_content)
    widget = Widgets.SectionWidget(ui, d["title"], outer_column)
    if handler:
        connect_name(widget, d, handler)
        connect_string_value(widget, d, handler, "title", finishes)
        connect_reference_value(widget, d, handler, "expanded", finishes, value_type=bool)
        connect_event(widget, widget, d, handler, "on_expanded_changed", ["expanded"])
        connect_attributes(widget, d, handler, finishes)
    return widget


def construct_tabs(ui: UserInterface.UserInterface, window: Window.Window, d: UIDescription, handler: HandlerLike,
                   finishes: _FinishesListType) -> UserInterface.TabWidget:
    properties = construct_sizing_properties(d)
    if d.get("style", None) == "minimal":
        widget = UserInterface.TabWidget(Widgets.TabWidgetBehavior(ui))
    else:
        widget = ui.create_tab_widget(properties)
    for tab in d.get("tabs", list()):
        widget.add(construct(ui, window, tab["content"], handler, finishes), tab["label"])
    if handler:
        connect_name(widget, d, handler)
        connect_reference_value(widget, d, handler, "current_index", finishes, value_type=int)
        connect_event(widget, widget, d, handler, "on_current_index_changed", ["current_index"])
        connect_attributes(widget, d, handler, finishes)
    return widget


def construct_progress_bar(ui: UserInterface.UserInterface, d: UIDescription, handler: HandlerLike,
                           finishes: _FinishesListType) -> UserInterface.ProgressBarWidget:
    minimum = d.get("minimum", 0)
    maximum = d.get("maximum", 100)
    properties = construct_sizing_properties(d)
    properties.setdefault("height", 18)
    properties.setdefault("width", 64)
    widget = ui.create_progress_bar_widget(properties=properties)
    widget.minimum = minimum
    widget.maximum = maximum
    if handler:
        connect_name(widget, d, handler)
        connect_reference_value(widget, d, handler, "value", finishes, value_type=int)
        connect_attributes(widget, d, handler, finishes)
    return widget


def construct_divider(ui: UserInterface.UserInterface, d: UIDescription, handler: HandlerLike,
                      finishes: _FinishesListType) -> UserInterface.CanvasWidget:
    orientation = d.get("orientation", "vertical")
    properties = construct_sizing_properties(d)
    if orientation == "vertical":
        properties.setdefault("width", 2)
    else:
        properties.setdefault("height", 2)
    widget = ui.create_canvas_widget(properties=properties)
    widget.canvas_item.add_canvas_item(CanvasItem.DividerCanvasItem(orientation=orientation, color=d.get("border_color", None)))
    if handler:
        connect_name(widget, d, handler)
        connect_attributes(widget, d, handler, finishes)
    return widget


def construct_slider(ui: UserInterface.UserInterface, d: UIDescription, handler: HandlerLike,
                     finishes: _FinishesListType) -> UserInterface.SliderWidget:
    minimum = d.get("minimum", 0)
    maximum = d.get("maximum", 100)
    properties = construct_sizing_properties(d)
    widget = ui.create_slider_widget(properties)
    widget.minimum = minimum
    widget.maximum = maximum
    if handler:
        connect_name(widget, d, handler)
        connect_reference_value(widget, d, handler, "value", finishes, value_type=int)
        connect_event(widget, widget, d, handler, "on_value_changed", ["value"])
        connect_event(widget, widget, d, handler, "on_slider_pressed", [])
        connect_event(widget, widget, d, handler, "on_slider_released", [])
        connect_event(widget, widget, d, handler, "on_slider_moved", ["value"])
        connect_attributes(widget, d, handler, finishes)
    return widget


def construct_radio_button(ui: UserInterface.UserInterface, d: UIDescription, handler: HandlerLike,
                           finishes: _FinishesListType) -> UserInterface.Widget:
    properties = construct_sizing_properties(d)
    widget: typing.Optional[UserInterface.Widget] = None
    if d.get("text", None) or d.get("icon", None) is None:
        widget = ui.create_radio_button_widget(properties=properties)
        widget.value = d.get("value", None)
        if handler and d.get("text", None):
            connect_string_value(widget, d, handler, "text", finishes)
    if d.get("icon", None) is not None:
        widget = Widgets.IconRadioButtonWidget(ui, properties=properties)
        widget.value = d.get("value", None)
        if handler and d.get("icon", None):
            connect_reference_value(widget, d, handler, "icon", finishes)
    assert widget
    if handler:
        connect_name(widget, d, handler)
        connect_reference_value(widget, d, handler, "group_value", finishes, value_type=int)
        connect_attributes(widget, d, handler, finishes)
    return widget


def construct_combo_box(ui: UserInterface.UserInterface, d: UIDescription, handler: HandlerLike,
                        finishes: _FinishesListType) -> UserInterface.ComboBoxWidget:
    items = d.get("items", None)
    properties = construct_sizing_properties(d)
    widget = ui.create_combo_box_widget(items=items, properties=properties)
    if handler:
        connect_name(widget, d, handler)
        # note: items_ref connects before current_index so that current_index can be valid
        connect_reference_value(widget, d, handler, "items_ref", finishes, binding_name="items", value_type=list)
        connect_reference_value(widget, d, handler, "current_index", finishes, value_type=int)
        connect_event(widget, widget, d, handler, "on_current_index_changed", ["current_index"])
        connect_attributes(widget, d, handler, finishes)
    return widget


def construct_check_box(ui: UserInterface.UserInterface, d: UIDescription, handler: HandlerLike,
                        finishes: _FinishesListType) -> UserInterface.CheckBoxWidget:
    # TODO: 'checked' and 'check_state' are bindings, not values
    tristate = d.get("tristate", None)
    properties = construct_sizing_properties(d)
    widget = ui.create_check_box_widget(properties=properties)
    if tristate is not None:
        widget.tristate = tristate
    if handler:
        connect_name(widget, d, handler)
        if d.get("text", None):
            connect_string_value(widget, d, handler, "text", finishes)
        if d.get("icon", None):
            connect_reference_value(widget, d, handler, "icon", finishes)
        connect_reference_value(widget, d, handler, "checked", finishes, value_type=bool)
        connect_reference_value(widget, d, handler, "check_state", finishes, value_type=str)
        connect_event(widget, widget, d, handler, "on_checked_changed", ["checked"])
        connect_event(widget, widget, d, handler, "on_check_state_changed", ["check_state"])
        connect_attributes(widget, d, handler, finishes)
    return widget


def construct_push_button(ui: UserInterface.UserInterface, d: UIDescription, handler: HandlerLike,
                          finishes: _FinishesListType) -> UserInterface.PushButtonWidget:
    properties = construct_sizing_properties(d)
    widget = ui.create_push_button_widget(properties=properties)
    if handler:
        connect_name(widget, d, handler)
        if d.get("text", None):
            connect_string_value(widget, d, handler, "text", finishes)
        if d.get("icon", None):
            connect_reference_value(widget, d, handler, "icon", finishes)
        connect_event(widget, widget, d, handler, "on_clicked", [])
        connect_attributes(widget, d, handler, finishes)
    return widget


def construct_text_edit(ui: UserInterface.UserInterface, d: UIDescription, finishes: _FinishesListType,
                        handler: HandlerLike) -> UserInterface.TextEditWidget:
    editable = d.get("editable", None)
    properties = construct_sizing_properties(d)
    widget = ui.create_text_edit_widget(properties)
    if editable is not None:
        widget.editable = editable
    if handler:
        connect_name(widget, d, handler)
        connect_string_value(widget, d, handler, "placeholder_text", finishes)
        connect_reference_value(widget, d, handler, "text", finishes)
        connect_event(widget, widget, d, handler, "on_escape_pressed", [])
        connect_event(widget, widget, d, handler, "on_return_pressed", [])
        connect_event(widget, widget, d, handler, "on_text_edited", ["text"])
        connect_attributes(widget, d, handler, finishes)
    return widget


def construct_line_edit(ui: UserInterface.UserInterface, d: UIDescription, finishes: _FinishesListType,
                        handler: HandlerLike) -> UserInterface.LineEditWidget:
    editable = d.get("editable", None)
    clear_button_enabled = d.get("clear_button_enabled", None)
    properties = construct_sizing_properties(d)
    widget = ui.create_line_edit_widget(properties)
    if editable is not None:
        widget.editable = editable
    if clear_button_enabled is not None:
        widget.clear_button_enabled = clear_button_enabled
    if handler:
        connect_name(widget, d, handler)
        connect_string_value(widget, d, handler, "placeholder_text", finishes)
        connect_reference_value(widget, d, handler, "text", finishes)
        connect_event(widget, widget, d, handler, "on_editing_finished", ["text"])
        connect_event(widget, widget, d, handler, "on_escape_pressed", [])
        connect_event(widget, widget, d, handler, "on_return_pressed", [])
        connect_event(widget, widget, d, handler, "on_key_pressed", ["key"])
        connect_event(widget, widget, d, handler, "on_text_edited", ["text"])
        connect_attributes(widget, d, handler, finishes)
    return widget


def construct_image(ui: UserInterface.UserInterface, d: UIDescription, handler: HandlerLike,
                    finishes: _FinishesListType) -> Widgets.ImageWidget:
    properties = construct_sizing_properties(d)
    widget = Widgets.ImageWidget(ui, properties=properties)
    if handler:
        connect_name(widget, d, handler)
        connect_reference_value(widget, d, handler, "image", finishes)
        connect_event(widget, widget, d, handler, "on_clicked", [])
        connect_attributes(widget, d, handler, finishes)
    return widget


def construct_text_label(ui: UserInterface.UserInterface, d: UIDescription, handler: HandlerLike,
                         finishes: _FinishesListType) -> UserInterface.LabelWidget:
    properties = construct_sizing_properties(d)
    widget = ui.create_label_widget(None, properties)
    if handler:
        connect_string_value(widget, d, handler, "text", finishes)
        connect_name(widget, d, handler)
        connect_attributes(widget, d, handler, finishes)
        connect_reference_value(widget, d, handler, "color", finishes, binding_name="text_color", value_type=str)
        connect_reference_value(widget, d, handler, "font", finishes, binding_name="text_font", value_type=str)
        connect_reference_value(widget, d, handler, "word_wrap", finishes, value_type=bool)
    return widget


def construct_box(ui: UserInterface.UserInterface, window: Window.Window, box_widget: UserInterface.BoxWidget,
                  d: UIDescription, handler: HandlerLike, finishes: _FinishesListType) -> UserInterface.BoxWidget:
    spacing: typing.Optional[int] = d.get("spacing")
    margin: typing.Optional[int] = d.get("margin")
    items = d.get("items")
    item_component_id = d.get("item_component_id")
    children = d.get("children", list())
    assert not items or not children
    first = True
    for child in children:
        if not first and spacing is not None:
            box_widget.add_spacing(spacing)
        if child.get("type") == "spacing":
            box_widget.add_spacing(child.get("size", 0))
        elif child.get("type") == "stretch":
            box_widget.add_stretch()
        else:
            box_widget.add(construct(ui, window, child, handler, finishes))
        first = False
    if items and item_component_id:
        connect_items(ui, window, box_widget, handler, items, item_component_id, spacing_v=spacing)
    if handler:
        connect_name(box_widget, d, handler)
        connect_attributes(box_widget, d, handler, finishes)
    return construct_margin(ui, box_widget, margin)


def construct_modeless_dialog(ui: UserInterface.UserInterface, window: Window.Window, d: UIDescription, handler: HandlerLike) -> Dialog.ActionDialog:
    title = d.get("title", _("Untitled"))
    margin = d.get("margin")
    persistent_id = d.get("persistent_id")
    content = typing.cast(UIDescription, d.get("content"))
    resources = d.get("resources", dict())
    for k, v in resources.items():
        resources[k] = v
    if not hasattr(handler, "resources"):
        setattr(handler, "resources", resources)
    else:
        getattr(handler, "resources").update(resources)
    closer = Closer()
    finishes: _FinishesListType = list()
    dialog = Dialog.ActionDialog(ui, title, app=window.app, parent_window=window, persistent_id=persistent_id)
    dialog.on_close = closer.close
    # dialog._create_menus()  # not needed; see pr#39.
    # make and attach closer for the handler; put handler into container closer
    setattr(handler, "_closer", Closer())
    closer.push_closeable(handler)
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
    setattr(handler, "_event_loop", window.event_loop)
    if callable(getattr(handler, "init_handler", None)):
        getattr(handler, "init_handler")()
    return dialog


class ComponentWidget(Widgets.CompositeWidgetBase):
    def __init__(self, ui: UserInterface.UserInterface, window: Window.Window, d: UIDescription, handler: HandlerLike) -> None:
        self.__column_widget = ui.create_column_widget()
        super().__init__(self.__column_widget)
        self.ui = ui
        self.__window = window
        self.__handler = handler
        self.__d = d
        self.__component_handler = None

        def set_identifier(value: typing.Optional[str]) -> None:
            self.__update_identifier(value)

        self.__identifier_binding_helper = UserInterface.BindablePropertyHelper[typing.Optional[str]](None, set_identifier)

    def close(self) -> None:
        self.__identifier_binding_helper.close()
        self.__identifier_binding_helper = typing.cast(typing.Any, None)
        super().close()

    @property
    def identifier(self) -> typing.Optional[str]:
        return self.__identifier_binding_helper.value

    @identifier.setter
    def identifier(self, value: typing.Optional[str]) -> None:
        self.__identifier_binding_helper.value = value

    def __update_identifier(self, identifier: typing.Optional[str]) -> None:
        # see notes in connect_items
        if self.__component_handler:
            getattr(self.__handler, "_closer").pop_closeable(self.__component_handler)
        self.__component_handler = None
        self.__column_widget.remove_all()
        window = self.__window
        handler = self.__handler
        d = self.__d
        ui = self.ui
        component_id: typing.Optional[str]
        component_content: typing.Optional[UIDescription] = None
        events = list()
        component = None
        finishes: _FinishesListType = list()
        if callable(getattr(handler, "get_resource", None)):
            component = getattr(handler, "get_resource")(identifier)
        component = component or getattr(handler, "resources", dict()).get(identifier)
        if component:
            assert component.get("type") == "component"
            # the component will have a content portion, which is a widget description, and a list of events.
            component_id = component.get("component_id", identifier)
            component_content = component.get("content")
            events = component.get("events", list())
        else:
            component_id = identifier
        if component_id:
            # create the handler first, but don't initialize it.
            component_handler = getattr(handler, "create_handler")(component_id=component_id) if component_id and hasattr(handler, "create_handler") else None
            if component_handler:
                # make and attach closer for the component handler and link it to the container handler.
                component_handler._closer = Closer()
                getattr(handler, "_closer").push_closeable(component_handler)
                component_content = getattr(component_handler, "ui_view", component_content)
                # set properties in the component from the properties dict
                for k, v in d.get("properties", dict()).items():
                    # print(f"setting property {k} to {v}")
                    setattr(component_handler, k, v)
                self.__component_handler = component_handler
            assert component_content
            # now construct the widget
            widget = construct(ui, window, component_content, component_handler, finishes)
            # connect the name to the handler if desired
            connect_name(widget, d, handler)
            # since the handler is custom to the widget, make a way to retrieve it from the widget
            setattr(widget, "handler", component_handler)
            component_handler._event_loop = window.event_loop
            if callable(getattr(component_handler, "init_handler", None)):
                component_handler.init_handler()
            # connect events
            for event in events:
                # print(f"connecting {event['event']} ({event['parameters']})")
                connect_event(widget, component_handler, d, handler, event["event"], event["parameters"])
            if handler:
                connect_attributes(widget, d, handler, finishes)
            self.__column_widget.add(widget)
        for finish in finishes:
            finish()

    def bind_identifier(self, binding: Binding.Binding) -> None:
        self.__identifier_binding_helper.bind_value(binding)

    def unbind_identifier(self) -> None:
        self.__identifier_binding_helper.unbind_value()


class DeclarativeWidget(Widgets.CompositeWidgetBase):
    """A widget containing a declarative ui handler."""

    def __init__(self, ui: UserInterface.UserInterface, event_loop: asyncio.AbstractEventLoop, ui_handler: HandlerLike) -> None:
        stack_widget = ui.create_stack_widget()
        super().__init__(stack_widget)

        # create a top level closer. for each object added to a closer, the closer will
        # call close (if it exists) and then close the object's _closer (if it exists).
        self.__closer = Closer()

        # create a _closer and attach it to the ui_handler. this may be used for sub-components.
        # then add the ui_handler to itself to be closed by the top level closer.
        setattr(ui_handler, "_closer", Closer())
        self.__closer.push_closeable(ui_handler)

        class DummyWindow:
            # dummy Window to supply event loop
            def __init__(self) -> None:
                self.event_loop = event_loop

        finishes: _FinishesListType = list()
        widget = construct(ui, typing.cast(Window.Window, DummyWindow()), getattr(ui_handler, "ui_view"), ui_handler, finishes)
        stack_widget.add(widget)
        for finish in finishes:
            finish()
        setattr(ui_handler, "_event_loop", event_loop)
        if callable(getattr(ui_handler, "init_handler", None)):
            getattr(ui_handler, "init_handler")()

    def close(self) -> None:
        self.__closer.close()
        super().close()
