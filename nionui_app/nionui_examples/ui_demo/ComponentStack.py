import typing

from nion.ui import Declarative
from nion.utils import Converter
from nion.utils import StructuredModel
from nion.utils import Model

if typing.TYPE_CHECKING:
    import asyncio
    from nion.ui import UserInterface


class Mode:

    def __init__(self, title: str) -> None:
        self.title = title
        self.count = 0


class Handler(Declarative.Handler):

    def __init__(self) -> None:
        super().__init__()

        self._event_loop: typing.Optional[asyncio.AbstractEventLoop] = None  # this will be injected by declarative UI engine

        # create a structured model by building a schema and then using the schema to create a structured model object.

        mode_title_field = StructuredModel.define_field("title", StructuredModel.STRING)

        mode_balance_field = StructuredModel.define_field("balance", StructuredModel.INT, default=0)

        mode_schema = StructuredModel.define_record("Mode", [mode_title_field, mode_balance_field])

        mode_index_field = StructuredModel.define_field("mode_index", StructuredModel.INT, default=1)

        modes_field = StructuredModel.define_field("modes", StructuredModel.define_array(mode_schema))

        schema = StructuredModel.define_record("Configuration", [mode_index_field, modes_field])

        # import pprint
        # print(pprint.pformat(schema))

        self.model = typing.cast(typing.Any, StructuredModel.build_model(schema))

        # the title model is used for adding new modes. it is not part of the structured model.

        self.title_model = Model.PropertyModel[str]()

        # the mode titles model is a property containing a list of mode titles. it is not part of the structured
        # model, but needs to be rebuilt when the list of modes in the model changes. add a listener for items
        # inserted/removed events and rebuild the mode titles model when those events are fired.

        self.mode_titles_model = Model.PropertyModel([mode.title for mode in self.model.modes])

        def modes_changed(k: str, v: typing.Any, i: int) -> None:
            if k == "modes":
                self.mode_titles_model.value = [mode.title for mode in self.model.modes]

        self.__modes_item_inserted_listener = self.model.item_inserted_event.listen(modes_changed)
        self.__modes_item_removed_listener = self.model.item_removed_event.listen(modes_changed)

        # add some initial modes

        self.model.modes.append(StructuredModel.build_model(mode_schema, value={"title": "One"}))
        self.model.modes.append(StructuredModel.build_model(mode_schema, value={"title": "Two"}))

    def close(self) -> None:
        self.__modes_item_inserted_listener.close()
        self.__modes_item_inserted_listener = typing.cast(typing.Any, None)
        self.__modes_item_removed_listener.close()
        self.__modes_item_removed_listener = typing.cast(typing.Any, None)
        super().close()

    def add_mode(self, widget: Declarative.UIWidget) -> None:
        # when the user clicks to add a mode, grab the title and insert a new mode into the model. then queue an update
        # to the mode index (needs to be queued so that the combo box UI can update from the model before the mode_index
        # on the combo box is set).
        title = self.title_model.value
        if title:
            mode_schema = self.model.modes_model.schema["items"]
            self.model.modes.append(StructuredModel.RecordModel(mode_schema, values={"title": title}))

            async def update_index() -> None:
                self.model.mode_index = len(self.model.modes) - 1

            # delay this for one cycle until combo box gets updated
            assert self._event_loop
            self._event_loop.create_task(update_index())

    def remove(self, mode: Mode) -> None:
        # when the user clicks to delete a mode, just delete it from the model. everything else will update
        # automatically.
        index = self.model.modes.index(mode)
        del self.model.modes[index]

    def create_handler(self, component_id: str, container: typing.Any = None, item: typing.Any = None, **kwargs: typing.Any) -> typing.Optional[Declarative.HandlerLike]:
        # when a new mode is added to the model.modes structured array, the stack will create a new child to
        # display/edit the new mode. the handler for the new child is returned here.
        # the container will be the structured record in which "modes" is contained.

        class ModeHandler(Declarative.Handler):
            def __init__(self, container: typing.Any, mode: Mode) -> None:
                super().__init__()
                self.__model = container
                self.mode = mode
                self.title_label_widget: typing.Optional[UserInterface.LabelWidget] = None
                self.count_label_widget: typing.Optional[UserInterface.LabelWidget] = None
                self.balance_converter = Converter.IntegerToStringConverter()

            def init_handler(self) -> None:
                assert self.title_label_widget
                # when this is called, all fields will be populated
                self.title_label_widget.text = self.mode.title

            def remove(self, widget: Declarative.UIWidget) -> None:
                self.__model.modes.remove(self.mode)

        if component_id == "mode":
            return ModeHandler(container, item)

        return None

    @property
    def resources(self) -> typing.Mapping[str, typing.Any]:
        # when a new mode is added to the model.modes structured array, the stack will create a new child to
        # display/edit the new mode. the declarative UI for the new child is returned here under the "mode" key which is
        # the same as the "item_component_id" passed to "create_stack". the handler for the new child is returned in
        # "create_handler".
        u = Declarative.DeclarativeUI()
        title_label = u.create_label(name="title_label_widget")
        balance_field = u.create_line_edit(text="@binding(mode.balance, converter=balance_converter)")
        remove_button = u.create_push_button(text="X", on_clicked="remove")
        row = u.create_row(title_label, balance_field, remove_button, u.create_stretch(), spacing=8)
        component = u.define_component(content=row)
        return {"mode": component}


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    title_field = u.create_line_edit(text="@binding(title_model.value)")
    add_button = u.create_push_button(text="Add", on_clicked="add_mode")
    modes_menu = u.create_combo_box(name="modes_menu", items_ref="@binding(mode_titles_model.value)", current_index="@binding(model.mode_index)")
    modes_stack = u.create_stack(items="model.modes", item_component_id="mode", current_index="@binding(model.mode_index)")
    modes_group = u.create_group(modes_stack)
    return u.create_column(title_field, add_button, modes_menu, modes_group, spacing=8, margin=12)
