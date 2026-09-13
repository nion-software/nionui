from nion.ui import Declarative


class Handler(Declarative.Handler):
    pass


def construct_ui(u: Declarative.DeclarativeUI) -> Declarative.UIDescription:
    def create_pane(text: str, background_color: str) -> Declarative.UIDescription:
        # the background color makes the effect of dragging a divider visible. the trailing stretch keeps the
        # content at the top of the pane as the pane is resized.
        label_row = u.create_row(u.create_label(text=text), u.create_stretch())
        check_box_row = u.create_row(u.create_check_box(text="Check " + text), u.create_stretch())
        return u.create_column(label_row, check_box_row, u.create_stretch(), spacing=8, margin=8,
                               background_color=background_color)

    # a horizontal splitter arranges its children side by side and its divider moves left and right, so it only
    # needs enough height to show the pane content.
    horizontal = u.create_splitter(create_pane("LEFT", "#e8eef5"), create_pane("RIGHT", "#f5eee8"),
                                   orientation="horizontal", height=80)

    # a vertical splitter stacks its children and its divider moves up and down, so it needs enough height for
    # both panes to stay usable across the range of the divider.
    vertical = u.create_splitter(create_pane("TOP", "#e8eef5"), create_pane("BOTTOM", "#f5eee8"),
                                 orientation="vertical", height=180)

    return u.create_column(u.create_label(text="Horizontal (drag the divider left and right)"), horizontal,
                           u.create_label(text="Vertical (drag the divider up and down)"), vertical,
                           spacing=8)
