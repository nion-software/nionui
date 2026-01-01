# standard libraries
import functools
import gettext

import numpy
import random
import typing

# third party libraries
# None

# local libraries
from nion.ui import Application
from nion.ui import Bitmap
from nion.ui import CanvasItem
from nion.ui import Declarative
from nion.ui import DrawingContext
from nion.ui import GridCanvasItem
from nion.ui import GridFlowCanvasItem
from nion.ui import ListCanvasItem
from nion.ui import UserInterface
from nion.ui import Window
from nion.utils import Geometry
from nion.utils import ListModel
from nion.utils import Model
from nion.utils import ReferenceCounting
from nion.utils import Selection

_ = gettext.gettext


class Handler(Declarative.Handler):

    def __init__(self, page_list: typing.List[typing.Tuple[typing.Any, str, str]]) -> None:
        super().__init__()
        self.page_stack: typing.Optional[UserInterface.StackWidget] = None
        self.page_list = page_list

    def select_page(self, widget: UserInterface.ComboBoxWidget, current_index: int) -> None:
        assert self.page_stack
        self.page_stack.current_index = current_index

    def create_handler(self, component_id: str, **kwargs: typing.Any) -> typing.Optional[Declarative.HandlerLike]:
        if self.page_list and component_id:
            for page_cls, page_id, page_title in self.page_list:
                if page_id == component_id:
                    return typing.cast(Declarative.HandlerLike, page_cls.Handler())
        return None


def make_bitmap(shape: Geometry.IntSize) -> Bitmap.Bitmap:
    # make bitmap_data (random static) for icon push button
    bitmap = numpy.zeros((shape.height, shape.width, 4), numpy.uint8)
    bitmap[..., 0] = random.randint(0,255)  # blue
    bitmap[..., 1] = random.randint(0,255)  # green
    bitmap[..., 2] = random.randint(0,255)  # red
    bitmap[..., 3] = 255
    return Bitmap.Bitmap(rgba_bitmap_data=bitmap.view(numpy.uint32).reshape(bitmap.shape[:-1]))


BITMAP_SIZE: typing.Final[int] = 48
SCROLLBAR_SIZE: typing.Final[int] = 20
BITMAP_SPACING = 8
BITMAP_COUNT = 20


class GridCanvasItemDelegate(GridCanvasItem.GridCanvasItemDelegate):
    def __init__(self, item_count:typing.Optional[int]=None)->None:
        self.__item_count = item_count if item_count is not None else 4

    @property
    def items(self) -> typing.Sequence[typing.Any]:
        return [1, 2, 3, 4]

    @items.setter
    def items(self, value: typing.Sequence[typing.Any]) -> None:
        raise NotImplementedError()

    @property
    def item_count(self) -> int:
        return self.__item_count

    def paint_item(self, drawing_context: DrawingContext.DrawingContext, item: typing.Any, rect: Geometry.IntRect, is_selected: bool) -> None:
        color = "yellow" if is_selected else "green"
        with drawing_context.saver():
            drawing_context.begin_path()
            drawing_context.move_to(rect.left, rect.top)
            drawing_context.line_to(rect.right, rect.bottom)
            drawing_context.move_to(rect.right, rect.top)
            drawing_context.line_to(rect.left, rect.bottom)
            if not is_selected:
                drawing_context.rect(rect.left, rect.top, rect.width, rect.height)
            drawing_context.stroke_style = color
            drawing_context.stroke()

            drawing_context.font = "12px"
            drawing_context.text_baseline = "middle"
            drawing_context.text_align = "center"
            drawing_context.fill_style = color
            drawing_context.fill_text(str(random.randint(100,999)), rect.center.x, rect.center.y)

    def drag_started(self, index: int, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> None:
        pass


class ListItemCanvasItemComposer(CanvasItem.BaseComposer):
    def __init__(self, canvas_item: CanvasItem.AbstractCanvasItem, layout_sizing: CanvasItem.Sizing, composer_cache: CanvasItem.ComposerCache, is_selected: bool) -> None:
        super().__init__(canvas_item, layout_sizing, composer_cache)
        self.__is_selected = is_selected

    def _repaint(self, drawing_context: DrawingContext.DrawingContext, canvas_rect: Geometry.IntRect, composer_cache: CanvasItem.ComposerCache) -> None:
        is_selected = self.__is_selected
        rect = canvas_rect - canvas_rect.origin
        with drawing_context.saver():
            drawing_context.translate(canvas_rect.left, canvas_rect.top)
            color = "yellow" if is_selected else "green"
            with drawing_context.saver():
                drawing_context.begin_path()
                drawing_context.move_to(rect.left, rect.top)
                drawing_context.line_to(rect.right, rect.bottom)
                drawing_context.move_to(rect.right, rect.top)
                drawing_context.line_to(rect.left, rect.bottom)
                if not is_selected:
                    drawing_context.rect(rect.left, rect.top, rect.width, rect.height)
                drawing_context.stroke_style = color
                drawing_context.stroke()

                drawing_context.font = "12px"
                drawing_context.text_baseline = "middle"
                drawing_context.text_align = "center"
                drawing_context.fill_style = color
                drawing_context.fill_text(str(random.randint(100, 999)), rect.center.x, rect.center.y)


class ListItemCanvasItem(CanvasItem.AbstractCanvasItem):
    def __init__(self, item: typing.Any, is_selected_model: Model.PropertyModel[bool]) -> None:
        super().__init__()
        self.__item = item
        self.__is_selected_model = is_selected_model
        self.__is_selected_model_property_changed_event_listener = is_selected_model.property_changed_event.listen(ReferenceCounting.weak_partial(ListItemCanvasItem.__is_selected_changed, self))

    def __is_selected_changed(self, key: str) -> None:
        if key == "value":
            self.update()

    def _get_composer(self, composer_cache: CanvasItem.ComposerCache) -> typing.Optional[CanvasItem.BaseComposer]:
        return ListItemCanvasItemComposer(self, self.layout_sizing, composer_cache, self.__is_selected_model.value or False)


app: typing.Optional[Application.BaseApplication] = None


def start(ui: UserInterface.UserInterface) -> bool:
    CanvasItem._g_draw_unique_marker = True

    window = Window.Window(ui, app)
    root_widget = ui.create_column_widget(properties={"min-width": 640, "min-height": 480})
    content_column = ui.create_column_widget()

    canvas_item = CanvasItem.CanvasItemComposition()
    canvas_item.layout = CanvasItem.CanvasItemColumnLayout(margins=Geometry.Margins(20, 20, 20, 20), spacing=20)
    canvas_item.border_color = "red"

    text_canvas_item = CanvasItem.StaticTextCanvasItem("Hello, world!")
    text_canvas_item.border_color = "green"
    text_canvas_item.size_to_content(ui.get_font_metrics)
    text_canvas_item2 = CanvasItem.StaticTextCanvasItem("Hello-er, world-er!")
    text_canvas_item2.border_color = "blue"
    text_canvas_item2.size_to_content(ui.get_font_metrics)
    text_canvas_item3 = CanvasItem.StaticTextCanvasItem("Hello-est, world-est!")
    text_canvas_item3.border_color = "orange"
    text_canvas_item3.size_to_content(ui.get_font_metrics)
    text_row = CanvasItem.CanvasItemComposition()
    text_row.layout = CanvasItem.CanvasItemRowLayout(spacing=12)
    text_row.add_canvas_item(text_canvas_item)
    text_row.add_canvas_item(text_canvas_item2)
    text_row.add_stretch()
    text_row.add_canvas_item(text_canvas_item3)

    cb_canvas_item = CanvasItem.CheckBoxCanvasItem("Check me!")
    cb_canvas_item.checked = True
    cb_canvas_item.size_to_content(ui.get_font_metrics)
    slider_canvas_item = CanvasItem.SliderCanvasItem()
    slider_canvas_item.update_sizing(slider_canvas_item.sizing.with_fixed_width(80))
    divider_canvas_item = CanvasItem.DividerCanvasItem()
    divider_canvas_item.update_sizing(divider_canvas_item.sizing.with_maximum_height(32))
    button_canvas_item = CanvasItem.TextButtonCanvasItem("Push")
    button_canvas_item.size_to_content(ui.get_font_metrics)
    progress_bar_canvas_item = CanvasItem.ProgressBarCanvasItem()
    progress_bar_canvas_item.update_sizing(progress_bar_canvas_item.sizing.with_fixed_width(100))
    progress_bar_canvas_item.progress = 0.75
    control_row = CanvasItem.CanvasItemComposition()
    control_row.layout = CanvasItem.CanvasItemRowLayout(spacing=12)
    control_row.add_canvas_item(cb_canvas_item)
    control_row.add_canvas_item(slider_canvas_item)
    control_row.add_canvas_item(divider_canvas_item)
    control_row.add_canvas_item(button_canvas_item)
    control_row.add_canvas_item(progress_bar_canvas_item)
    control_row.add_stretch()

    splitter = CanvasItem.SplitterCanvasItem()
    splitter.update_sizing(splitter.sizing.with_fixed_height(60))
    splitter_left = CanvasItem.SplitterCanvasItem(orientation="horizontal")
    splitter_right = CanvasItem.SplitterCanvasItem(orientation="horizontal")
    layer_left_top = CanvasItem.LayerCanvasItem()
    # layer_left_top.is_root_opaque = True
    layer_left_top.add_canvas_item(CanvasItem.StaticTextCanvasItem("Splitter Left Top"))
    layer_left_bottom = CanvasItem.LayerCanvasItem()
    layer_left_bottom.add_canvas_item(CanvasItem.StaticTextCanvasItem("Splitter Left Bottom"))
    layer_right_top = CanvasItem.LayerCanvasItem()
    layer_right_top.add_canvas_item(CanvasItem.StaticTextCanvasItem("Splitter Right Top"))
    layer_right_bottom = CanvasItem.LayerCanvasItem()
    # layer_right_bottom.is_root_opaque = True
    layer_right_bottom.add_canvas_item(CanvasItem.StaticTextCanvasItem("Splitter Right Bottom"))
    splitter_left.add_canvas_item(layer_left_top)
    splitter_left.add_canvas_item(layer_left_bottom)
    splitter_right.add_canvas_item(layer_right_top)
    splitter_right.add_canvas_item(layer_right_bottom)
    splitter.add_canvas_item(splitter_left)
    splitter.add_canvas_item(splitter_right)
    splitter_row = CanvasItem.CanvasItemComposition()
    splitter_row.layout = CanvasItem.CanvasItemRowLayout()
    splitter_row.add_canvas_item(splitter)

    scroll_area_content = CanvasItem.CanvasItemComposition()
    scroll_area_content.layout = CanvasItem.CanvasItemRowLayout(spacing=BITMAP_SPACING)
    for _ in range(BITMAP_COUNT):
        bitmap_canvas_item = CanvasItem.BitmapCanvasItem(bitmap=make_bitmap(Geometry.IntSize(BITMAP_SIZE, BITMAP_SIZE)))
        bitmap_canvas_item.size_to_content(ui.get_font_metrics)
        scroll_area_content.add_canvas_item(bitmap_canvas_item)
    # create scroll area with fixed height since it cannot know its height purely from its contents (it's meant to
    # be scrollable and will typically be smaller than its contents)
    scroll_area_canvas_item = CanvasItem.ScrollAreaCanvasItem(scroll_area_content)
    scroll_area_canvas_item.update_sizing(scroll_area_canvas_item.sizing.with_fixed_height(BITMAP_SIZE))
    vertical_scroll_bar_canvas_item = CanvasItem.ScrollBarCanvasItem(scroll_area_canvas_item)
    horizontal_scroll_bar_canvas_item = CanvasItem.ScrollBarCanvasItem(scroll_area_canvas_item,
                                                                       CanvasItem.Orientation.Horizontal)
    scroll_group_canvas_item = CanvasItem.CanvasItemComposition()
    scroll_group_canvas_item.layout = CanvasItem.CanvasItemGridLayout(Geometry.IntSize(width=2, height=2))
    scroll_group_canvas_item.add_canvas_item(scroll_area_canvas_item, Geometry.IntPoint(x=0, y=0))
    scroll_group_canvas_item.add_canvas_item(vertical_scroll_bar_canvas_item, Geometry.IntPoint(x=1, y=0))
    scroll_group_canvas_item.add_canvas_item(horizontal_scroll_bar_canvas_item, Geometry.IntPoint(x=0, y=1))

    selection = Selection.IndexedSelection()

    # grid_canvas_item_delegate = GridCanvasItemDelegate()
    # grid_canvas_item = GridCanvasItem.GridCanvasItem(grid_canvas_item_delegate, selection)
    # grid_canvas_item.update_sizing(grid_canvas_item.sizing.with_fixed_height(200))

    list_model = ListModel.ListModel[int]()
    list_model.items = [1, 2, 3, 4]
    list_canvas_item = ListCanvasItem.ListCanvasItem2(list_model, selection, ListItemCanvasItem, ListCanvasItem.ListCanvasItem2Delegate(), item_height=48)
    list_canvas_item.update_sizing(list_canvas_item.sizing.with_fixed_height(200))

    grid_canvas_item = GridCanvasItem.GridCanvasItem2(list_model, selection, ListItemCanvasItem, GridFlowCanvasItem.GridFlowCanvasItemDelegate(), item_size=Geometry.IntSize(100, 100))
    grid_canvas_item.update_sizing(grid_canvas_item.sizing.with_fixed_height(200))

    grid_list_row = CanvasItem.CanvasItemComposition()
    grid_list_row.layout = CanvasItem.CanvasItemRowLayout(spacing=8)
    grid_list_row.add_canvas_item(grid_canvas_item)
    grid_list_row.add_canvas_item(list_canvas_item)

    canvas_item.add_canvas_item(text_row)
    canvas_item.add_canvas_item(control_row)
    canvas_item.add_canvas_item(splitter_row)
    canvas_item.add_canvas_item(scroll_group_canvas_item)
    canvas_item.add_canvas_item(grid_list_row)
    canvas_item.add_stretch()
    canvas_widget = ui.create_canvas_widget()
    canvas_widget.canvas_item.add_canvas_item(canvas_item)
    content_column.add(canvas_widget)

    root_widget.add(content_column)
    window.attach_widget(root_widget)
    window.show()

    def do_something() -> None:
        pass  # useful for debugging layout.
        # splitter.canvas_items[1].update()
        # splitter.canvas_items[1].canvas_items[0].text = "X"

    button_canvas_item.on_clicked = do_something

    return True


def main(args: typing.Sequence[typing.Any], bootstrap_args: typing.Mapping[str, typing.Any]) -> Application.BaseApplication:
    ui = Application.make_ui(bootstrap_args)
    global app
    app = Application.BaseApplication(ui, on_start=functools.partial(start, ui))
    app.initialize()
    return app
