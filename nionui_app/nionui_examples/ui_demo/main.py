# standard libraries
import gettext
import typing

# third party libraries
# None

# local libraries
from nion.ui import Application
from nion.ui import Declarative

# ui imports
from . import Bindings
from . import Buttons
from . import CheckBoxes
from . import ComboBoxes
from . import Compositions
from . import ComponentContent
from . import ComponentLayout
from . import ComponentPolymorphic
from . import ComponentStack
from . import Converters
from . import Groups
from . import LineEdits
from . import ProgressBars
from . import RadioButtons
from . import Sections
from . import Sliders
from . import Stacks
from . import StatusBar
from . import Tabs

if typing.TYPE_CHECKING:
    from nion.ui import UserInterface

_ = gettext.gettext


class Handler(Declarative.Handler):

    def __init__(self, page_list: typing.List[typing.Tuple[typing.Any, str, str]]) -> None:
        super().__init__()
        self.page_stack: typing.Optional[UserInterface.StackWidget] = None
        self.page_list = page_list

    def select_page(self, widget: Declarative.UIWidget, current_index: int) -> None:
        assert self.page_stack
        self.page_stack.current_index = current_index

    def create_handler(self, component_id: str, **kwargs: typing.Any) -> typing.Optional[Declarative.HandlerLike]:
        if self.page_list and component_id:
            for page_cls, page_id, page_title in self.page_list:
                if page_id == component_id:
                    return typing.cast(Declarative.HandlerLike, page_cls.Handler())
        return None


def main(args: typing.Sequence[typing.Any], bootstrap_args: typing.Mapping[str, typing.Any]) -> Application.BaseApplication:
    u = Declarative.DeclarativeUI()

    page_list = [
        (Buttons, "buttons", _("Buttons")),
        (CheckBoxes, "check_boxes", _("Check Boxes")),
        (ComboBoxes, "combo_boxes", _("Combo Boxes")),
        (Bindings, "bindings", _("Bindings")),
        (Compositions, "compositions", _("Compositions")),
        (Converters, "converters", _("Converters")),
        (Groups, "groups", _("Groups")),
        (LineEdits, "line_edits", _("Line Edits")),
        (ProgressBars, "progress_bars", _("Progress Bars")),
        (RadioButtons, "radio_buttons", _("Radio Buttons")),
        (Sections, "sections", _("Sections")),
        (Sliders, "sliders", _("Sliders")),
        (Stacks, "stacks", _("Stacks")),
        (StatusBar, "status_bar", _("Status Bar")),
        (Tabs, "tabs", _("Tabs")),
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

    chooser_combo_box = u.create_combo_box(items=items, on_current_index_changed="select_page")

    page_stack = u.create_stack(*pages, name="page_stack")

    page_group = u.create_group(page_stack, margin=8)

    main_column = u.create_column(chooser_combo_box, page_group, spacing=8)

    window = u.create_window(main_column, title=_("UI Demo"), margin=12, resources=resources)

    return Application.run_window(args, bootstrap_args, window, handler)
