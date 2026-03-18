from nion.ui import Declarative


class Handler(Declarative.Handler):

    def __init__(self) -> None:
        super().__init__()


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    row1 = u.create_row(u.create_label(text="L"), u.create_label(text="M", width=30), u.create_label(text="M"),
                        u.create_label(text="M", width=50), u.create_label(text="M"), u.create_stretch(),
                        u.create_label(text="R"))
    container = u.create_column(row1, min_width=150, spacing=0)
    return container
