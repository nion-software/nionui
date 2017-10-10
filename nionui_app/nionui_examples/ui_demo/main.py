# standard libraries
import gettext

# third party libraries
# None

# local libraries
from nion.ui import Declarative

# ui imports
from . import Bindings
from . import CheckBoxes
from . import ComboBoxes
from . import Compositions
from . import Converters
from . import Groups
from . import LineEdits
from . import ProgressBars
from . import Sliders
from . import Stacks
from . import Tabs

_ = gettext.gettext


class Handler:
    page_stack = None

    def select_page(self, widget, current_index):
        self.page_stack.current_index = current_index


def main(args, bootstrap_args):
    ui = Declarative.DeclarativeUI()

    handler = Handler()

    resources = dict()

    l = [(CheckBoxes, "check_boxes", _("Check Boxes")),
         (ComboBoxes, "combo_boxes", _("Combo Boxes")),
         (Bindings, "bindings", _("Bindings")),
         (Compositions, "compositions", _("Compositions")),
         (Converters, "converters", _("Converters")),
         (Groups, "groups", _("Groups")),
         (LineEdits, "line_edits", _("Line Edits")),
         (ProgressBars, "progress_bars", _("Progress Bars")),
         (Sliders, "sliders", _("Sliders")),
         (Stacks, "stacks", _("Stacks")),
         (Tabs, "tabs", _("Tabs")),
         ]

    pages = list()
    items = list()

    for c, n, t in l:
        handler_name = "create_" + n + "_handler"
        component = ui.define_component(content=c.construct_ui(ui), create_handler_method_name=handler_name)
        setattr(handler, handler_name, lambda c=c: c.Handler())
        resources[n] = component
        instance = ui.create_component_instance(n)
        pages.append(ui.create_column(instance, ui.create_stretch()))
        items.append(t)

    chooser_combo_box = ui.create_combo_box(items=items, on_current_index_changed="select_page")

    page_stack = ui.create_stack(*pages, name="page_stack")

    page_group = ui.create_group(page_stack, margin=8)

    main_column = ui.create_column(chooser_combo_box, page_group, spacing=8)

    window = ui.create_window(main_column, title=_("UI Demo"), margin=12, resources=resources)

    return Declarative.run_ui(args, bootstrap_args, window, handler)
