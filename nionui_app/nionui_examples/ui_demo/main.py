# standard libraries
import gettext

# third party libraries
# None

# local libraries
from nion.ui import Declarative

# ui imports
from . import Bindings
from . import Buttons
from . import CheckBoxes
from . import ComboBoxes
from . import Compositions
from . import ComponentLayout
from . import ComponentStack
from . import Converters
from . import Groups
from . import LineEdits
from . import ProgressBars
from . import RadioButtons
from . import Sliders
from . import Stacks
from . import StatusBar
from . import Tabs

_ = gettext.gettext


class Handler:

    def __init__(self):
        self.page_stack = None
        self.page_list = None

    def select_page(self, widget, current_index):
        self.page_stack.current_index = current_index

    def create_handler(self, component_id: str=None, **kwargs):
        if self.page_list and component_id:
            for page_cls, page_id, page_title in self.page_list:
                if page_id == component_id:
                    return page_cls.Handler()
        return None


def main(args, bootstrap_args):
    ui = Declarative.DeclarativeUI()

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
        (Sliders, "sliders", _("Sliders")),
        (Stacks, "stacks", _("Stacks")),
        (StatusBar, "status_bar", _("Status Bar")),
        (Tabs, "tabs", _("Tabs")),
        (ComponentLayout, "component_layout", _("Component Layout")),
        (ComponentStack, "component_stack", _("Component Stack")),
        ]

    handler = Handler()
    handler.page_list = page_list

    resources = dict()

    pages = list()
    items = list()

    for page_cls, page_id, page_title in page_list:
        resources[page_id] = ui.define_component(content=page_cls.construct_ui(ui), component_id=page_id)
        instance = ui.create_component_instance(page_id)
        pages.append(ui.create_column(instance, ui.create_stretch()))
        items.append(page_title)

    chooser_combo_box = ui.create_combo_box(items=items, on_current_index_changed="select_page")

    page_stack = ui.create_stack(*pages, name="page_stack")

    page_group = ui.create_group(page_stack, margin=8)

    main_column = ui.create_column(chooser_combo_box, page_group, spacing=8)

    window = ui.create_window(main_column, title=_("UI Demo"), margin=12, resources=resources)

    return Declarative.run_ui(args, bootstrap_args, window, handler)
