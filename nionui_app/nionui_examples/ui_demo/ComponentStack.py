from nion.ui import Declarative
from nion.utils import Converter
from nion.utils import StructuredModel
from nion.utils import Model

class Mode:

    def __init__(self, title: str):
        self.title = title
        self.count = 0


class Handler:

    def __init__(self):
        self._event_loop = None  # this will be injected by declarative UI engine

        # create a structured model by building a schema and then using the schema to create a structured model object.

        mode_title_field = StructuredModel.define_field("title", StructuredModel.STRING)

        mode_balance_field = StructuredModel.define_field("balance", StructuredModel.INT, default=0)

        mode_schema = StructuredModel.define_record("Mode", [mode_title_field, mode_balance_field])

        mode_index_field = StructuredModel.define_field("mode_index", StructuredModel.INT, default=1)

        modes_field = StructuredModel.define_field("modes", StructuredModel.define_array(mode_schema))

        schema = StructuredModel.define_record("Configuration", [mode_index_field, modes_field])

        # import pprint
        # print(pprint.pformat(schema))

        self.model = StructuredModel.build_model(schema)

        # the title model is used for adding new modes. it is not part of the structured model.

        self.title_model = Model.PropertyModel()

        # the mode titles model is a property containing a list of mode titles. it is not part of the structured
        # model, but needs to be rebuilt when the list of modes in the model changes. add a listener for items
        # inserted/removed events and rebuild the mode titles model when those events are fired.

        self.mode_titles_model = Model.PropertyModel([mode.title for mode in self.model.modes])

        def modes_changed(k, v, i):
            if k == "modes":
                self.mode_titles_model.value = [mode.title for mode in self.model.modes]

        self.__modes_item_inserted_listener = self.model.item_inserted_event.listen(modes_changed)
        self.__modes_item_removed_listener = self.model.item_removed_event.listen(modes_changed)

        # add some initial modes

        self.model.modes.append(StructuredModel.build_model(mode_schema, value={"title": "One"}))
        self.model.modes.append(StructuredModel.build_model(mode_schema, value={"title": "Two"}))

    def close(self):
        self.__modes_item_inserted_listener.close()
        self.__modes_item_inserted_listener = None
        self.__modes_item_removed_listener.close()
        self.__modes_item_removed_listener = None

    def add_mode(self, widget) -> None:
        # when the user clicks to add a mode, grab the title and insert a new mode into the model. then queue an update
        # to the mode index (needs to be queued so that the combo box UI can update from the model before the mode_index
        # on the combo box is set).
        title = self.title_model.value
        if title:
            mode_schema = self.model.modes_model.schema["items"]
            self.model.modes.append(StructuredModel.RecordModel(mode_schema, values={"title": title}))

            async def update_index():
                self.model.mode_index = len(self.model.modes) - 1

            # delay this for one cycle until combo box gets updated
            self._event_loop.create_task(update_index())

    def remove(self, mode: Mode) -> None:
        # when the user clicks to delete a mode, just delete it from the model. everything else will update
        # automatically.
        index = self.model.modes.index(mode)
        del self.model.modes[index]

    def create_handler(self, component_id: str, container=None, item=None, **kwargs):
        # when a new mode is added to the model.modes structured array, the stack will create a new child to
        # display/edit the new mode. the handler for the new child is returned here.
        # the container will be the structured record in which "modes" is contained.

        class ModeHandler:
            def __init__(self, container, mode):
                self.__model = container
                self.mode = mode
                self.title_label_widget = None
                self.count_label_widget = None
                self.balance_converter = Converter.IntegerToStringConverter()

            def init_handler(self):
                # when this is called, all fields will be populated
                self.title_label_widget.text = self.mode.title

            def remove(self, widget):
                self.__model.modes.remove(self.mode)

        if component_id == "mode":
            return ModeHandler(container, item)

    @property
    def resources(self):
        # when a new mode is added to the model.modes structured array, the stack will create a new child to
        # display/edit the new mode. the declarative UI for the new child is returned here under the "mode" key which is
        # the same as the "item_component_id" passed to "create_stack". the handler for the new child is returned in
        # "create_handler".
        ui = Declarative.DeclarativeUI()
        title_label = ui.create_label(name="title_label_widget")
        balance_field = ui.create_line_edit(text="@binding(mode.balance, converter=balance_converter)")
        remove_button = ui.create_push_button(text="X", on_clicked="remove")
        row = ui.create_row(title_label, balance_field, remove_button, ui.create_stretch(), spacing=8)
        component = ui.define_component(content=row, component_id="mode")
        return {"mode": component}


def construct_ui(ui: Declarative.DeclarativeUI):
    title_field = ui.create_line_edit(text="@binding(title_model.value)")
    add_button = ui.create_push_button(text="Add", on_clicked="add_mode")
    modes_menu = ui.create_combo_box(name="modes_menu", items_ref="@binding(mode_titles_model.value)", current_index="@binding(model.mode_index)")
    modes_stack = ui.create_stack(items="model.modes", item_component_id="mode", current_index="@binding(model.mode_index)")
    modes_group = ui.create_group(modes_stack)
    return ui.create_column(title_field, add_button, modes_menu, modes_group, spacing=8, margin=12)
