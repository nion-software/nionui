import typing

from nion.ui import Declarative
from nion.utils import Event
from nion.utils import Model

if typing.TYPE_CHECKING:
    from nion.ui import UserInterface


class Section(Declarative.Handler):

    def __init__(self, title: str) -> None:
        super().__init__()
        self.title = title
        self.count = 0


class Handler(Declarative.Handler):

    def __init__(self) -> None:
        super().__init__()
        self.sections = list()
        self.item_inserted_event = Event.Event()
        self.item_removed_event = Event.Event()
        self.sections.append(Section("Apples"))
        self.sections.append(Section("Oranges"))
        self.title_model = Model.PropertyModel[str]()

    def add(self, widget: Declarative.UIWidget) -> None:
        title = self.title_model.value
        if title:
            section = Section(title)
            index = len(self.sections)
            self.sections.append(section)
            self.item_inserted_event.fire("sections", section, index)

    def remove(self, section: Section) -> None:
        index = self.sections.index(section)
        del self.sections[index]
        self.item_removed_event.fire("sections", section, index)

    def create_handler(self, component_id: str, container: typing.Any = None, item: typing.Any = None, **kwargs: typing.Any) -> typing.Optional[Declarative.HandlerLike]:

        class SectionHandler(Declarative.Handler):

            def __init__(self, container: typing.List[Section], section: Section) -> None:
                super().__init__()
                self.container = container
                self.section = section
                self.title_label_widget: typing.Optional[UserInterface.LabelWidget] = None
                self.count_label_widget: typing.Optional[UserInterface.LabelWidget] = None

            def init_handler(self) -> None:
                assert self.title_label_widget
                assert self.count_label_widget
                # when this is called, all fields will be populated
                self.title_label_widget.text = self.section.title
                self.count_label_widget.text = str(self.section.count)

            def increase_count(self, widget: Declarative.UIWidget) -> None:
                assert self.count_label_widget
                self.section.count += 1
                self.count_label_widget.text = str(self.section.count)

            def decrease_count(self, widget: Declarative.UIWidget) -> None:
                assert self.count_label_widget
                self.section.count -= 1
                self.count_label_widget.text = str(self.section.count)

            def remove(self, widget: Declarative.UIWidget) -> None:
                self.container.remove(self.section)

        if component_id == "section":
            return SectionHandler(container, item)

        return None

    @property
    def resources(self) -> typing.Mapping[str, typing.Any]:
        ui = Declarative.DeclarativeUI()
        title_label = ui.create_label(name="title_label_widget")
        count_label = ui.create_label(name="count_label_widget")
        increase_button = ui.create_push_button(text="++", on_clicked="increase_count")
        decrease_button = ui.create_push_button(text="--", on_clicked="decrease_count")
        remove_button = ui.create_push_button(text="X", on_clicked="remove")
        row = ui.create_row(title_label, count_label, increase_button, decrease_button, remove_button, ui.create_stretch(), spacing=8)
        component = ui.define_component(content=row)
        return {"section": component}


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    title_field = u.create_line_edit(text="@binding(title_model.value)")
    add_button = u.create_push_button(text="Add", on_clicked="add")
    sections_column = u.create_column(items="sections", item_component_id="section", spacing=8)
    return u.create_column(title_field, add_button, sections_column, spacing=8, margin=12)
