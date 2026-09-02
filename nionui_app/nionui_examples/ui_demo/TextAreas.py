import typing

from nion.ui import Declarative
from nion.ui import UserInterface
from nion.utils import Model


class Handler(Declarative.Handler):

    def __init__(self) -> None:
        super().__init__()
        self.text_edit: typing.Optional[UserInterface.TextEditWidget] = None
        self.text_model = Model.PropertyModel("Edit this text.\nIt spans multiple lines.")
        self.editable_model = Model.PropertyModel(True)
        self.status_model = Model.PropertyModel("")
        self.browser_markdown_model = Model.PropertyModel("# Text Browser\n\nThis is **read-only**, formatted text.")

    def text_edited(self, widget: UserInterface.TextEditWidget, text: str) -> None:
        self.status_model.value = f"Text edited ({len(text)} characters)"

    def editable_changed(self, widget: UserInterface.CheckBoxWidget, checked: bool) -> None:
        assert self.text_edit
        self.editable_model.value = checked
        self.text_edit.editable = checked

    def anchor_clicked(self, widget: UserInterface.Widget, anchor: str) -> bool:
        self.status_model.value = f"Anchor clicked: {anchor}"
        return True


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    text_edit = u.create_text_edit(name="text_edit", text="@binding(text_model.value)",
                                    placeholder_text="Type here...", on_text_edited="text_edited", height=80)
    editable_check_box = u.create_check_box(text="Editable", checked="@binding(editable_model.value)",
                                             on_checked_changed="editable_changed")
    status_label = u.create_label(text="@binding(status_model.value)")

    text_browser = u.create_text_browser(markdown="@binding(browser_markdown_model.value)",
                                          on_anchor_clicked="anchor_clicked", height=80)

    return u.create_column(
        u.create_row(text_edit, u.create_stretch()),
        u.create_row(editable_check_box, u.create_stretch(), spacing=8),
        status_label,
        u.create_divider(orientation="horizontal"),
        text_browser,
        u.create_stretch(),
        spacing=8,
    )
