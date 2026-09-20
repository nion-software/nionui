# standard libraries
import gettext
import typing

# third party libraries
# None

# local libraries
from nion.ui import Application
from nion.ui import Declarative
from nion.ui import UserInterface

# ui imports
from . import Bindings
from . import Buttons
from . import CheckBoxes
from . import Clipboard
from . import ComboBoxes
from . import Compositions
from . import ComponentContent
from . import ComponentLayout
from . import ComponentPolymorphic
from . import ComponentStack
from . import ContextMenus
from . import Converters
from . import Dialogs
from . import FocusKeyboard
from . import Groups
from . import Layout
from . import LineEdits
from . import ListDetail
from . import ListBoxes
from . import ListViews
from . import Popups
from . import ProgressBars
from . import RadioButtons
from . import ScrollAreas
from . import Sections
from . import Sliders
from . import Splitters
from . import Stacks
from . import StatusBar
from . import Tabs
from . import ToolTips
from . import TextAreas

_ = gettext.gettext


class Handler(Declarative.WindowHandler):

    def __init__(self, page_list: typing.List[typing.Tuple[typing.Any, str, str]]) -> None:
        super().__init__()
        self.page_stack: typing.Optional[UserInterface.StackWidget] = None
        self.page_list = page_list

    def select_page(self, widget: UserInterface.ComboBoxWidget, current_index: int) -> None:
        assert self.page_stack
        self.page_stack.current_index = current_index

    def create_handler(self, component_id: str, **kwargs: typing.Any) -> typing.Optional[Declarative.HandlerLike]:
        if self.page_list and component_id:
            for page_cls, page_id, page_title in self.page_list:
                if page_id == component_id:
                    page_handler = page_cls.Handler()
                    # a page which poses a popup needs the window, which it reaches through this handler.
                    setattr(page_handler, "container_handler", self)
                    return typing.cast(Declarative.HandlerLike, page_handler)
        return None


def main(args: typing.Sequence[typing.Any], bootstrap_args: typing.Mapping[str, typing.Any]) -> Application.BaseApplication:
    u = Declarative.DeclarativeUI()

    page_list = [
        (Buttons, "buttons", _("Buttons")),
        (Layout, "layout", _("Layout")),
        (CheckBoxes, "check_boxes", _("Check Boxes")),
        (Clipboard, "clipboard", _("Clipboard")),
        (ComboBoxes, "combo_boxes", _("Combo Boxes")),
        (Bindings, "bindings", _("Bindings")),
        (Compositions, "compositions", _("Compositions")),
        (ContextMenus, "context_menus", _("Context Menus")),
        (Converters, "converters", _("Converters")),
        (Dialogs, "dialogs", _("Dialogs")),
        (FocusKeyboard, "focus_keyboard", _("Focus and Keyboard")),
        (Groups, "groups", _("Groups")),
        (LineEdits, "line_edits", _("Line Edits")),
        (ListBoxes, "list_boxes", _("List Boxes")),
        (ListDetail, "list_detail", _("List Detail")),
        (ListViews, "list_views", _("List Views")),
        (Popups, "popups", _("Popups")),
        (ProgressBars, "progress_bars", _("Progress Bars")),
        (RadioButtons, "radio_buttons", _("Radio Buttons")),
        (ScrollAreas, "scroll_areas", _("Scroll Areas")),
        (Sections, "sections", _("Sections")),
        (Sliders, "sliders", _("Sliders")),
        (Splitters, "splitters", _("Splitters")),
        (Stacks, "stacks", _("Stacks")),
        (StatusBar, "status_bar", _("Status Bar")),
        (Tabs, "tabs", _("Tabs")),
        (ToolTips, "tool_tips", _("Tool Tips")),
        (TextAreas, "text_areas", _("Text Areas")),
        (ComponentLayout, "component_layout", _("Component Layout")),
        (ComponentStack, "component_stack", _("Component Stack")),
        (ComponentContent, "component_content", _("Component Content")),
        (ComponentPolymorphic, "component_polymorphic", _("Component Polymorphic")),
        ]

    handler = Handler(page_list)

    resources = dict()

    pages = list()
    items = list()

    for page_cls, page_id, page_title in page_list:
        resources[page_id] = u.define_component(content=typing.cast(typing.Any, page_cls).construct_ui(u))
        instance = u.create_component_instance(page_id)
        pages.append(u.create_column(instance, u.create_stretch()))
        items.append(page_title)

    chooser_combo_box = u.create_row(u.create_combo_box(items=items, on_current_index_changed="select_page"), u.create_stretch())

    # the pages are constructed as they are first displayed rather than all of them at startup. the page group
    # supplies the height; the width settles once the widest page visited has been built.
    page_stack = u.create_stack(*pages, name="page_stack", item_construction="deferred")

    page_group = u.create_group(page_stack, margin=8, size_policy_vertical="expanding")

    main_column = u.create_column(chooser_combo_box, page_group, spacing=8)

    window = u.create_window(main_column, title=_("UI Demo"), margin=12, resources=resources)

    # run the window through the handler so that the handler, and the pages it creates, can reach the window.
    def start() -> bool:
        handler.run(window, app=app)
        return True

    app = Application.BaseApplication(Application.make_ui(bootstrap_args), on_start=start)
    app.initialize()

    return app
