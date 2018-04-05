from nion.ui import Declarative
from nion.utils import ListModel
from nion.utils import Model

class Mode:

    def __init__(self, title: str):
        self.title = title
        self.count = 0


class Handler:

    def __init__(self):
        self._event_loop = None  # this will be injected by declarative UI engine
        self.modes = ListModel.ListModel()
        self.modes.append_item(Mode("One"))
        self.modes.append_item(Mode("Two"))
        self.modes_model = Model.PropertyModel([mode.title for mode in self.modes.items])
        self.title_model = Model.PropertyModel()
        self.mode_index_model = Model.PropertyModel(0)

        def modes_changed(k, v, i):
            self.modes_model.value = [mode.title for mode in self.modes.items]

        self.__modes_item_inserted_listener = self.modes.item_inserted_event.listen(modes_changed)
        self.__modes_item_removed_listener = self.modes.item_removed_event.listen(modes_changed)

    def close(self):
        self.__modes_item_inserted_listener.close()
        self.__modes_item_inserted_listener = None
        self.__modes_item_removed_listener.close()
        self.__modes_item_removed_listener = None

    def add_mode(self, widget) -> None:
        title = self.title_model.value
        if title:
            self.modes.append_item(Mode(title))

            async def update_index():
                self.mode_index_model.value = len(self.modes.items) - 1

            # delay this for one cycle until combo box gets updated
            self._event_loop.create_task(update_index())

    def remove(self, mode: Mode) -> None:
        index = self.modes.items.index(mode)
        self.modes.remove_item(index)

    def create_handler(self, component_id: str, container=None, item=None, **kwargs):

        class ModeHandler:

            def __init__(self, container, mode: Mode):
                self.container = container
                self.mode = mode
                self.title_label_widget = None
                self.count_label_widget = None

            def init_handler(self):
                # when this is called, all fields will be populated
                self.title_label_widget.text = self.mode.title

            def remove(self, widget):
                self.container.remove_item(self.container.items.index(self.mode))

        if component_id == "mode":
            return ModeHandler(container, item)

    @property
    def resources(self):
        ui = Declarative.DeclarativeUI()
        title_label = ui.create_label(name="title_label_widget")
        remove_button = ui.create_push_button(text="X", on_clicked="remove")
        row = ui.create_row(title_label, remove_button, ui.create_stretch(), spacing=8)
        component = ui.define_component(content=row, component_id="mode")
        return {"mode": component}


def construct_ui(ui: Declarative.DeclarativeUI):
    title_field = ui.create_line_edit(text="@binding(title_model.value)")
    add_button = ui.create_push_button(text="Add", on_clicked="add_mode")
    modes_menu = ui.create_combo_box(name="modes_menu", items_ref="@binding(modes_model.value)", current_index="@binding(mode_index_model.value)")
    modes_stack = ui.create_stack(items="modes.items", item_component_id="mode", current_index="@binding(mode_index_model.value)")
    modes_group = ui.create_group(modes_stack)
    return ui.create_column(title_field, add_button, modes_menu, modes_group, spacing=8, margin=12)
