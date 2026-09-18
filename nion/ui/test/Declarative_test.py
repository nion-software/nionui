# standard libraries
import asyncio
import contextlib
import threading
import typing
import unittest

# third party libraries
# None

# local libraries
from nion.ui import CanvasItem
from nion.ui import CanvasUserInterface
from nion.ui import Declarative
from nion.ui import GridFlowCanvasItem
from nion.ui import ListCanvasItem
from nion.ui import TestUI
from nion.ui import UserInterface
from nion.ui import Widgets
from nion.ui import Window
from nion.utils import Model
from nion.utils import Binding
from nion.utils import Geometry
from nion.utils import ListModel
from nion.utils import Selection


@contextlib.contextmanager
def event_loop_context() -> typing.Iterator[asyncio.AbstractEventLoop]:
    event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(event_loop)
    yield event_loop
    event_loop.stop()
    event_loop.run_forever()
    event_loop.close()


class DummyWindow:
    # dummy Window to supply the event loop to constructed components.
    def __init__(self, event_loop: asyncio.AbstractEventLoop) -> None:
        self.event_loop = event_loop


def dummy_window(event_loop: asyncio.AbstractEventLoop) -> Window.Window:
    # components use the window only for its event loop; matches what construct_widget does.
    return typing.cast(Window.Window, DummyWindow(event_loop))


class ItemHandler(Declarative.Handler):
    """An item component handler recording when it is initialized and closed."""

    def __init__(self, item: str) -> None:
        super().__init__()
        u = Declarative.DeclarativeUI()
        self.item = item
        self.initialized = False
        self.closed = False
        # the list view replaces this with a model tracking whether the item is selected.
        self.is_selected_model = Model.PropertyModel(False)
        self.ui_view = u.create_row(u.create_label(text=item), u.create_stretch())

    def init_handler(self) -> None:
        self.initialized = True

    def close(self) -> None:
        self.closed = True
        super().close()


class ItemsHandler(Declarative.Handler):
    """A container handler creating an item component handler for each item."""

    def __init__(self) -> None:
        super().__init__()
        self.item_handlers: typing.List[ItemHandler] = list()

    def create_handler(self, component_id: str, item: typing.Any = None,
                       container: typing.Any = None, **kwargs: typing.Any) -> typing.Optional[ItemHandler]:
        if component_id == "item":
            item_handler = ItemHandler(item)
            self.item_handlers.append(item_handler)
            return item_handler
        return None


class ListViewHandler(ItemsHandler):
    """A handler with an observable list of items displayed in a list view."""

    def __init__(self, items: typing.Sequence[str]) -> None:
        super().__init__()
        u = Declarative.DeclarativeUI()
        self.list_model = ListModel.ListModel[str]("items", items=list(items))
        self.list_view: typing.Optional[Widgets.ListViewWidget] = None
        self.ui_view = u.create_list_view(items="list_model.items", item_component_id="item", item_height=20,
                                          name="list_view")


class ListViewEventsHandler(ItemsHandler):
    """A handler with a list view whose current index is bound and whose callbacks are recorded."""

    def __init__(self, items: typing.Sequence[str]) -> None:
        super().__init__()
        u = Declarative.DeclarativeUI()
        self.list_model = ListModel.ListModel[str]("items", items=list(items))
        self.current_index_model = Model.PropertyModel(0)
        self.changed_indexes: typing.List[typing.Optional[int]] = list()
        self.selected_indexes: typing.List[int] = list()
        self.context_menu_indexes: typing.List[typing.Optional[int]] = list()
        self.escape_count = 0
        self.list_view: typing.Optional[Widgets.ListViewWidget] = None
        self.ui_view = u.create_list_view(items="list_model.items", item_component_id="item", item_height=20,
                                          name="list_view",
                                          current_index="@binding(current_index_model.value)",
                                          on_item_changed="item_changed",
                                          on_item_selected="item_selected",
                                          on_escape_pressed="escape_pressed",
                                          on_item_handle_context_menu="item_context_menu")

    def item_changed(self, widget: Declarative.UIWidget, current_index: typing.Optional[int]) -> None:
        self.changed_indexes.append(current_index)

    def item_selected(self, widget: Declarative.UIWidget, current_index: int) -> bool:
        self.selected_indexes.append(current_index)
        return True

    def escape_pressed(self, widget: Declarative.UIWidget) -> bool:
        self.escape_count += 1
        return True

    def item_context_menu(self, widget: Declarative.UIWidget, index: typing.Optional[int], x: int, y: int,
                          gx: int, gy: int) -> bool:
        self.context_menu_indexes.append(index)
        return True


class StackItemsHandler(ItemsHandler):
    """A handler with a stack whose children are built from an observable list of items."""

    def __init__(self, items: typing.Sequence[str], item_construction: typing.Optional[str] = None,
                 min_height: typing.Optional[int] = None) -> None:
        super().__init__()
        u = Declarative.DeclarativeUI()
        self.list_model = ListModel.ListModel[str]("items", items=list(items))
        self.current_index_model = Model.PropertyModel(0)
        self.stack: typing.Optional[UserInterface.StackWidget] = None
        self.ui_view = u.create_stack(items="list_model.items", item_component_id="item", name="stack",
                                      current_index="@binding(current_index_model.value)",
                                      item_construction=item_construction, min_height=min_height)


@contextlib.contextmanager
def closer_context(handler: Declarative.HandlerLike) -> typing.Iterator[None]:
    # a handler is given a closer when it is constructed by the declarative engine; tests using a handler directly
    # have to supply one.
    setattr(handler, "_closer", Declarative.Closer())
    yield
    getattr(handler, "_closer").close()


class TestCanvasItemClass(unittest.TestCase):

    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

    def test_splitter_constructs_children_and_orientation(self) -> None:
        # tests that a declarative splitter description constructs a splitter widget with its children in order.
        u = Declarative.DeclarativeUI()

        class Handler(Declarative.Handler):
            def __init__(self) -> None:
                super().__init__()
                self.splitter: typing.Optional[UserInterface.SplitterWidget] = None
                self.ui_view = u.create_splitter(u.create_label(text="LEFT"), u.create_label(text="RIGHT"),
                                                 name="splitter", orientation="horizontal")

        with event_loop_context() as event_loop:
            handler = Handler()
            widget = Declarative.construct_widget(TestUI.UserInterface(), event_loop, handler)
            with contextlib.closing(widget):
                splitter = typing.cast(UserInterface.SplitterWidget, widget)
                self.assertIsInstance(splitter, UserInterface.SplitterWidget)
                self.assertEqual(splitter, handler.splitter)
                self.assertEqual("horizontal", splitter.orientation)
                children = typing.cast(typing.Sequence[UserInterface.LabelWidget], splitter._contained_widgets)
                self.assertEqual(["LEFT", "RIGHT"], [child.text for child in children])

    def test_splitter_constructs_with_no_children(self) -> None:
        # tests that a splitter with no children constructs without error.
        u = Declarative.DeclarativeUI()

        class Handler(Declarative.Handler):
            def __init__(self) -> None:
                super().__init__()
                self.ui_view = u.create_splitter()

        with event_loop_context() as event_loop:
            widget = Declarative.construct_widget(TestUI.UserInterface(), event_loop, Handler())
            with contextlib.closing(widget):
                self.assertIsInstance(widget, UserInterface.SplitterWidget)

    def test_update_binding_from_thread(self) -> None:
        # tests that setting the source model on a thread updates the ui model properly using bindable property.
        with event_loop_context() as event_loop:
            source_model = Model.PropertyModel(0)
            ui_model = Model.PropertyModel(1)
            binding = Binding.PropertyBinding(source_model, "value")

            def update_ui(value: int) -> None:
                ui_model.value = value

            with contextlib.closing(UserInterface.BindablePropertyHelper[int](None, update_ui)) as binding_helper:
                binding_helper.bind_value(binding)

                def set_value_on_thread2(value: int) -> None:
                    source_model.value = value

                t = threading.Thread(target=set_value_on_thread2, args=(7,))
                t.start()
                t.join()

                # note: when binding_helper is finalized, it cancels any pending tasks. keep it around until finished.

                self.assertEqual(7, source_model.value)
                self.assertNotEqual(ui_model.value, source_model.value)
                # run the event loop twice. when the source model changes on a thread, it calls run_coroutine_threadsafe
                # which queues the call to make the call. the first run puts the correct call in the queue. the second
                # run executes the call.
                event_loop.stop()
                event_loop.run_forever()
                event_loop.stop()
                event_loop.run_forever()
                self.assertEqual(7, source_model.value)
                self.assertEqual(ui_model.value, source_model.value)

    def test_declarative_item_factory_creates_a_component_canvas_item_per_item(self) -> None:
        # tests that the item factory instantiates the item component for each item and returns a canvas item for it.
        with event_loop_context() as event_loop:
            handler = ItemsHandler()
            with closer_context(handler):
                factory = Declarative.DeclarativeItemFactory(TestUI.UserInterface(), dummy_window(event_loop), handler,
                                                             "item", handler)
                canvas_item_a = factory.create("a", Model.PropertyModel(False))
                canvas_item_b = factory.create("b", Model.PropertyModel(False))
                self.assertNotEqual(canvas_item_a, canvas_item_b)
                self.assertEqual(["a", "b"], [item_handler.item for item_handler in handler.item_handlers])
                self.assertEqual([True, True], [item_handler.initialized for item_handler in handler.item_handlers])
                factory.destroy(canvas_item_a)
                factory.destroy(canvas_item_b)

    def test_declarative_item_factory_destroy_closes_the_item_handler(self) -> None:
        # tests that destroying an item releases its handler, which is what keeps bindings and listeners alive.
        with event_loop_context() as event_loop:
            handler = ItemsHandler()
            with closer_context(handler):
                factory = Declarative.DeclarativeItemFactory(TestUI.UserInterface(), dummy_window(event_loop), handler,
                                                             "item", handler)
                canvas_item = factory.create("a", Model.PropertyModel(False))
                item_handler = handler.item_handlers[0]
                self.assertFalse(item_handler.closed)
                factory.destroy(canvas_item)
                self.assertTrue(item_handler.closed)

    def test_declarative_item_factory_tracks_list_canvas_item_contents(self) -> None:
        # tests the factory in its intended setting: an item handler exists for each item in the list model, removing
        # an item closes just that handler, and closing the list closes the remaining ones.
        with event_loop_context() as event_loop:
            handler = ItemsHandler()
            with closer_context(handler):
                factory = Declarative.DeclarativeItemFactory(TestUI.UserInterface(), dummy_window(event_loop), handler,
                                                             "item", handler)
                list_model = ListModel.ListModel[str]("items", items=["a", "b", "c"])
                list_canvas_item = ListCanvasItem.ListCanvasItem2(list_model, Selection.IndexedSelection(), factory,
                                                                  GridFlowCanvasItem.GridFlowCanvasItemDelegate(),
                                                                  item_height=20, key="items")
                self.assertEqual(["a", "b", "c"], [item_handler.item for item_handler in handler.item_handlers])
                list_model.remove_item(1)
                self.assertEqual(["b"], [item_handler.item for item_handler in handler.item_handlers if item_handler.closed])
                list_canvas_item.close()
                self.assertEqual(["a", "b", "c"], sorted(item_handler.item for item_handler in handler.item_handlers if item_handler.closed))

    def test_list_view_constructs_an_item_component_for_each_item(self) -> None:
        # tests that a declarative list view description constructs the item component for each item of the list.
        with event_loop_context() as event_loop:
            handler = ListViewHandler(["a", "b", "c"])
            widget = Declarative.construct_widget(TestUI.UserInterface(), event_loop, handler)
            with contextlib.closing(widget):
                self.assertIsInstance(handler.list_view, Widgets.ListViewWidget)
                self.assertEqual(["a", "b", "c"], [item_handler.item for item_handler in handler.item_handlers])

    def test_list_view_follows_inserts_and_removes(self) -> None:
        # tests that changing the observable list adds and removes item components rather than rebuilding the list.
        with event_loop_context() as event_loop:
            handler = ListViewHandler(["a", "b", "c"])
            widget = Declarative.construct_widget(TestUI.UserInterface(), event_loop, handler)
            with contextlib.closing(widget):
                first_item_handler = handler.item_handlers[0]
                handler.list_model.insert_item(1, "b2")
                self.assertEqual(["a", "b", "c", "b2"], [item_handler.item for item_handler in handler.item_handlers])
                handler.list_model.remove_item(2)
                self.assertEqual(["b"], [item_handler.item for item_handler in handler.item_handlers if item_handler.closed])
                # the surviving items keep their original handlers; only the removed item is torn down.
                self.assertEqual(first_item_handler, handler.item_handlers[0])
                self.assertFalse(first_item_handler.closed)

    def test_list_view_closes_item_handlers_when_closed(self) -> None:
        # tests that closing the widget releases the item handlers, following the canvas item hierarchy.
        with event_loop_context() as event_loop:
            handler = ListViewHandler(["a", "b", "c"])
            widget = Declarative.construct_widget(TestUI.UserInterface(), event_loop, handler)
            widget.close()
            self.assertEqual(["a", "b", "c"], sorted(item_handler.item for item_handler in handler.item_handlers if item_handler.closed))

    def test_list_view_lays_out_one_row_per_item(self) -> None:
        # tests that the constructed list actually lays out its items, one row of item_height for each item.
        with event_loop_context() as event_loop:
            handler = ListViewHandler(["a", "b", "c"])
            widget = Declarative.construct_widget(TestUI.UserInterface(), event_loop, handler)
            with contextlib.closing(widget):
                list_view = typing.cast(Widgets.ListViewWidget, handler.list_view)
                list_canvas_item = list_view._list_canvas_item
                list_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=200, height=100))
                self.assertEqual(Geometry.IntSize(width=200, height=60), list_canvas_item.canvas_size)
                handler.list_model.remove_item(0)
                list_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=200, height=100))
                self.assertEqual(Geometry.IntSize(width=200, height=40), list_canvas_item.canvas_size)

    def test_list_view_current_index_binding_follows_the_selection(self) -> None:
        # tests that clicking an item updates the bound current index, and that setting it updates the selection.
        with event_loop_context() as event_loop:
            handler = ListViewEventsHandler(["a", "b", "c"])
            widget = Declarative.construct_widget(TestUI.UserInterface(), event_loop, handler)
            with contextlib.closing(widget):
                list_view = typing.cast(Widgets.ListViewWidget, handler.list_view)
                list_canvas_item = list_view._list_canvas_item
                list_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=200, height=100))
                list_canvas_item.simulate_click(Geometry.IntPoint(y=30, x=10))
                self.assertEqual(1, handler.current_index_model.value)
                self.assertEqual(1, handler.changed_indexes[-1])
                handler.current_index_model.value = 2
                self.assertEqual({2}, list_view.selection.indexes)

    def test_list_view_reports_an_item_chosen_by_double_click_or_return(self) -> None:
        # tests that choosing an item reports it exactly once, whether by double click or by pressing return.
        with event_loop_context() as event_loop:
            ui = TestUI.UserInterface()
            handler = ListViewEventsHandler(["a", "b", "c"])
            widget = Declarative.construct_widget(ui, event_loop, handler)
            with contextlib.closing(widget):
                list_view = typing.cast(Widgets.ListViewWidget, handler.list_view)
                list_canvas_item = list_view._list_canvas_item
                list_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=200, height=100))
                list_canvas_item.mouse_double_clicked(10, 30, CanvasItem.KeyboardModifiers())
                self.assertEqual([1], handler.selected_indexes)
                list_canvas_item.key_pressed(ui.create_key_by_id("return"))
                self.assertEqual([1, 1], handler.selected_indexes)

    def test_list_view_reports_escape_and_context_menu(self) -> None:
        # tests the remaining callbacks: escape is passed to the handler, and the context menu reports the item index.
        with event_loop_context() as event_loop:
            ui = TestUI.UserInterface()
            handler = ListViewEventsHandler(["a", "b", "c"])
            widget = Declarative.construct_widget(ui, event_loop, handler)
            with contextlib.closing(widget):
                list_view = typing.cast(Widgets.ListViewWidget, handler.list_view)
                list_canvas_item = list_view._list_canvas_item
                list_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=200, height=100))
                list_canvas_item.key_pressed(ui.create_key_by_id("escape"))
                self.assertEqual(1, handler.escape_count)
                list_canvas_item._grid_flow_item_canvas_items[2].context_menu_event(5, 5, 105, 205)
                self.assertEqual([2], handler.context_menu_indexes)

    def test_list_view_exposes_the_item_selection_to_the_item_component(self) -> None:
        # tests that each item component can see whether its item is selected, so that it can display it differently.
        with event_loop_context() as event_loop:
            handler = ListViewEventsHandler(["a", "b", "c"])
            widget = Declarative.construct_widget(TestUI.UserInterface(), event_loop, handler)
            with contextlib.closing(widget):
                list_view = typing.cast(Widgets.ListViewWidget, handler.list_view)
                list_canvas_item = list_view._list_canvas_item
                list_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=200, height=100))
                # the current index binding selects the first item.
                self.assertEqual([True, False, False], [item_handler.is_selected_model.value for item_handler in handler.item_handlers])
                list_canvas_item.simulate_click(Geometry.IntPoint(y=50, x=10))
                self.assertEqual([False, False, True], [item_handler.is_selected_model.value for item_handler in handler.item_handlers])

    def test_list_view_uses_the_component_from_the_handler_resources(self) -> None:
        # tests the resources path: the item component content comes from the handler resources and there is no item
        # handler at all, which is the case when the items need no behavior of their own.
        u = Declarative.DeclarativeUI()

        class Handler(Declarative.Handler):
            def __init__(self) -> None:
                super().__init__()
                self.list_model = ListModel.ListModel[str]("items", items=["a", "b"])
                self.list_view: typing.Optional[Widgets.ListViewWidget] = None
                self.resources = {"item": u.define_component(content=u.create_label(text="item"))}
                self.ui_view = u.create_list_view(items="list_model.items", item_component_id="item",
                                                  item_height=20, name="list_view")

            def create_handler(self, component_id: str, **kwargs: typing.Any) -> typing.Optional[Declarative.Handler]:
                return None

        with event_loop_context() as event_loop:
            handler = Handler()
            widget = Declarative.construct_widget(TestUI.UserInterface(), event_loop, handler)
            with contextlib.closing(widget):
                list_view = typing.cast(Widgets.ListViewWidget, handler.list_view)
                list_canvas_item = list_view._list_canvas_item
                list_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=200, height=100))
                self.assertEqual(Geometry.IntSize(width=200, height=40), list_canvas_item.canvas_size)
                handler.list_model.remove_item(0)
                list_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=200, height=100))
                self.assertEqual(Geometry.IntSize(width=200, height=20), list_canvas_item.canvas_size)

    def test_list_view_allows_a_different_component_per_item(self) -> None:
        # tests that the item handler chooses the ui view, so items of different kinds can be displayed differently.
        u = Declarative.DeclarativeUI()

        class RowHandler(Declarative.Handler):
            def __init__(self, item: str) -> None:
                super().__init__()
                self.item = item
                self.ui_view = u.create_label(text=item) if item.startswith("label") else u.create_push_button(text=item)

        class Handler(Declarative.Handler):
            def __init__(self) -> None:
                super().__init__()
                self.list_model = ListModel.ListModel[str]("items", items=["label-a", "button-b"])
                self.row_handlers: typing.List[RowHandler] = list()
                self.list_view: typing.Optional[Widgets.ListViewWidget] = None
                self.ui_view = u.create_list_view(items="list_model.items", item_component_id="item",
                                                  item_height=20, name="list_view")

            def create_handler(self, component_id: str, item: typing.Any = None,
                               container: typing.Any = None, **kwargs: typing.Any) -> typing.Optional[RowHandler]:
                row_handler = RowHandler(item)
                self.row_handlers.append(row_handler)
                return row_handler

        with event_loop_context() as event_loop:
            handler = Handler()
            widget = Declarative.construct_widget(TestUI.UserInterface(), event_loop, handler)
            with contextlib.closing(widget):
                self.assertEqual(["label-a", "button-b"], [row_handler.item for row_handler in handler.row_handlers])
                list_view = typing.cast(Widgets.ListViewWidget, handler.list_view)
                list_view._list_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=200, height=100))
                self.assertEqual(Geometry.IntSize(width=200, height=40), list_view._list_canvas_item.canvas_size)

    def test_list_view_selection_style_allows_multiple_selection(self) -> None:
        # tests that the selection style reaches the selection; the default style allows only one item at a time.
        u = Declarative.DeclarativeUI()

        class Handler(ItemsHandler):
            def __init__(self, selection_style: typing.Optional[str]) -> None:
                super().__init__()
                self.list_model = ListModel.ListModel[str]("items", items=["a", "b", "c"])
                self.list_view: typing.Optional[Widgets.ListViewWidget] = None
                self.ui_view = u.create_list_view(items="list_model.items", item_component_id="item", item_height=20,
                                                  name="list_view", selection_style=selection_style)

        with event_loop_context() as event_loop:
            for selection_style, expected_indexes in (("multiple", {0, 1}), (None, {1})):
                handler = Handler(selection_style)
                widget = Declarative.construct_widget(TestUI.UserInterface(), event_loop, handler)
                with contextlib.closing(widget):
                    list_view = typing.cast(Widgets.ListViewWidget, handler.list_view)
                    list_canvas_item = list_view._list_canvas_item
                    list_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=200, height=100))
                    list_canvas_item.simulate_click(Geometry.IntPoint(y=10, x=10))
                    list_canvas_item.simulate_click(Geometry.IntPoint(y=30, x=10), CanvasItem.KeyboardModifiers(shift=True))
                    self.assertEqual(expected_indexes, list_view.selection.indexes)

    def test_list_box_displays_its_items_as_text(self) -> None:
        # tests that a list box displays one row of text per item, which is what a list box is.
        u = Declarative.DeclarativeUI()

        class Handler(Declarative.Handler):
            def __init__(self) -> None:
                super().__init__()
                self.list_box: typing.Optional[Widgets.StringListViewWidget] = None
                self.ui_view = u.create_list_box(items=["Alpha", "Beta", "Gamma"], name="list_box")

        with event_loop_context() as event_loop:
            handler = Handler()
            widget = Declarative.construct_widget(TestUI.UserInterface(), event_loop, handler)
            with contextlib.closing(widget):
                list_box = typing.cast(Widgets.StringListViewWidget, handler.list_box)
                self.assertEqual(["Alpha", "Beta", "Gamma"], list(list_box.items))
                list_canvas_item = list_box._list_canvas_item
                list_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=200, height=200))
                self.assertEqual(Geometry.IntSize(width=200, height=60), list_canvas_item.canvas_size)
                row_canvas_items = [typing.cast(CanvasItem.TextCanvasItem, row._canvas_item) for row in list_canvas_item._grid_flow_item_canvas_items]
                self.assertEqual(["Alpha", "Beta", "Gamma"], [row_canvas_item.text for row_canvas_item in row_canvas_items])

    def test_list_box_items_ref_updates_only_the_rows_that_changed(self) -> None:
        # tests that assigning the items updates the list in place, so that unchanged rows are left alone.
        u = Declarative.DeclarativeUI()

        class Handler(Declarative.Handler):
            def __init__(self) -> None:
                super().__init__()
                self.items_model = Model.PropertyModel[typing.List[str]](["Alpha", "Beta"])
                self.list_box: typing.Optional[Widgets.StringListViewWidget] = None
                self.ui_view = u.create_list_box(items_ref="@binding(items_model.value)", name="list_box")

        with event_loop_context() as event_loop:
            handler = Handler()
            widget = Declarative.construct_widget(TestUI.UserInterface(), event_loop, handler)
            with contextlib.closing(widget):
                list_box = typing.cast(Widgets.StringListViewWidget, handler.list_box)
                list_canvas_item = list_box._list_canvas_item
                first_row = list_canvas_item._grid_flow_item_canvas_items[0]
                handler.items_model.value = ["Alpha", "Beta", "Gamma"]
                rows = list_canvas_item._grid_flow_item_canvas_items
                self.assertEqual(3, len(rows))
                self.assertEqual(first_row, rows[0])
                self.assertEqual("Gamma", typing.cast(CanvasItem.TextCanvasItem, rows[2]._canvas_item).text)
                handler.items_model.value = ["Alpha"]
                self.assertEqual(1, len(list_canvas_item._grid_flow_item_canvas_items))

    def test_list_box_current_index_and_item_selected(self) -> None:
        # tests that a list box still reports the current index and the chosen item to its handler.
        u = Declarative.DeclarativeUI()

        class Handler(Declarative.Handler):
            def __init__(self) -> None:
                super().__init__()
                self.current_index_model = Model.PropertyModel(0)
                self.selected_indexes: typing.List[int] = list()
                self.escape_count = 0
                self.list_box: typing.Optional[Widgets.StringListViewWidget] = None
                self.ui_view = u.create_list_box(items=["Alpha", "Beta", "Gamma"], name="list_box",
                                                 current_index="@binding(current_index_model.value)",
                                                 on_item_selected="item_selected",
                                                 on_escape_pressed="escape_pressed")

            def item_selected(self, widget: Declarative.UIWidget, current_index: int) -> bool:
                self.selected_indexes.append(current_index)
                return True

            def escape_pressed(self, widget: Declarative.UIWidget) -> bool:
                self.escape_count += 1
                return True

        with event_loop_context() as event_loop:
            ui = TestUI.UserInterface()
            handler = Handler()
            widget = Declarative.construct_widget(ui, event_loop, handler)
            with contextlib.closing(widget):
                list_box = typing.cast(Widgets.StringListViewWidget, handler.list_box)
                list_canvas_item = list_box._list_canvas_item
                list_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=200, height=200))
                list_canvas_item.simulate_click(Geometry.IntPoint(y=30, x=10))
                self.assertEqual(1, handler.current_index_model.value)
                list_canvas_item.key_pressed(ui.create_key_by_id("return"))
                self.assertEqual([1], handler.selected_indexes)
                list_canvas_item.key_pressed(ui.create_key_by_id("escape"))
                self.assertEqual(1, handler.escape_count)

    def test_list_box_item_tool_tips(self) -> None:
        # tests that an item carrying a tool tip still supplies it to its row.
        u = Declarative.DeclarativeUI()

        class Item:
            def __init__(self, text: str, tool_tip: str) -> None:
                self.text = text
                self.tool_tip = tool_tip

            def __str__(self) -> str:
                return self.text

        class Handler(Declarative.Handler):
            def __init__(self) -> None:
                super().__init__()
                self.list_box: typing.Optional[Widgets.StringListViewWidget] = None
                self.ui_view = u.create_list_box(items=[Item("Alpha", "the first one")], name="list_box")

        with event_loop_context() as event_loop:
            handler = Handler()
            widget = Declarative.construct_widget(TestUI.UserInterface(), event_loop, handler)
            with contextlib.closing(widget):
                list_box = typing.cast(Widgets.StringListViewWidget, handler.list_box)
                row = list_box._list_canvas_item._grid_flow_item_canvas_items[0]
                self.assertEqual("Alpha", typing.cast(CanvasItem.TextCanvasItem, row._canvas_item).text)
                self.assertEqual("the first one", row.tool_tip)

    def test_list_view_current_index_follows_a_removal_before_the_selected_item(self) -> None:
        # tests that removing an item ahead of the selected one keeps the same item selected, with the index moved to
        # where that item now is. the selection is adjusted by the list, so the bound index has to follow it.
        with event_loop_context() as event_loop:
            handler = ListViewEventsHandler(["a", "b", "c"])
            widget = Declarative.construct_widget(TestUI.UserInterface(), event_loop, handler)
            with contextlib.closing(widget):
                list_view = typing.cast(Widgets.ListViewWidget, handler.list_view)
                handler.current_index_model.value = 2
                handler.list_model.remove_item(0)
                self.assertEqual(1, handler.current_index_model.value)
                self.assertEqual({1}, list_view.selection.indexes)

    def test_list_view_current_index_is_cleared_when_the_selected_item_is_removed(self) -> None:
        # tests that removing the selected item leaves nothing selected and reports it, rather than leaving the bound
        # index pointing at an item which is no longer there.
        with event_loop_context() as event_loop:
            handler = ListViewEventsHandler(["a", "b", "c"])
            widget = Declarative.construct_widget(TestUI.UserInterface(), event_loop, handler)
            with contextlib.closing(widget):
                list_view = typing.cast(Widgets.ListViewWidget, handler.list_view)
                handler.current_index_model.value = 2
                handler.list_model.remove_item(2)
                self.assertIsNone(handler.current_index_model.value)
                self.assertEqual(set(), list_view.selection.indexes)
                self.assertIsNone(handler.changed_indexes[-1])

    def test_list_view_current_index_is_cleared_when_the_last_item_is_removed(self) -> None:
        # tests the empty list: nothing can be selected, so the bound index is nothing.
        with event_loop_context() as event_loop:
            handler = ListViewEventsHandler(["a"])
            widget = Declarative.construct_widget(TestUI.UserInterface(), event_loop, handler)
            with contextlib.closing(widget):
                self.assertEqual(0, handler.current_index_model.value)
                handler.list_model.remove_item(0)
                self.assertIsNone(handler.current_index_model.value)

    def test_stack_constructs_every_child_by_default(self) -> None:
        # tests the default: a stack constructs all of its children, whether or not they are displayed.
        with event_loop_context() as event_loop:
            handler = StackItemsHandler(["a", "b", "c"], item_construction=None)
            widget = Declarative.construct_widget(TestUI.UserInterface(), event_loop, handler)
            with contextlib.closing(widget):
                self.assertEqual(["a", "b", "c"], [item_handler.item for item_handler in handler.item_handlers])

    def test_stack_builds_deferred_children_when_displayed(self) -> None:
        # tests that deferred construction builds the child being displayed and no others, and keeps what it builds.
        with event_loop_context() as event_loop:
            handler = StackItemsHandler(["a", "b", "c"], item_construction="deferred")
            widget = Declarative.construct_widget(TestUI.UserInterface(), event_loop, handler)
            with contextlib.closing(widget):
                # the child being displayed is built, so the stack is never an empty shell.
                self.assertEqual(["a"], [item_handler.item for item_handler in handler.item_handlers])
                handler.current_index_model.value = 2
                self.assertEqual(["a", "c"], [item_handler.item for item_handler in handler.item_handlers])
                handler.current_index_model.value = 0
                # returning to a child which was already built does not build it again.
                self.assertEqual(["a", "c"], [item_handler.item for item_handler in handler.item_handlers])
                self.assertFalse(any(item_handler.closed for item_handler in handler.item_handlers))

    def test_stack_removing_an_unbuilt_child_closes_nothing(self) -> None:
        # tests that removing an item whose child was never built is not an error and closes no handler.
        with event_loop_context() as event_loop:
            handler = StackItemsHandler(["a", "b", "c"], item_construction="deferred")
            widget = Declarative.construct_widget(TestUI.UserInterface(), event_loop, handler)
            with contextlib.closing(widget):
                self.assertEqual(["a"], [item_handler.item for item_handler in handler.item_handlers])
                handler.list_model.remove_item(1)  # never built
                self.assertEqual([], [item_handler.item for item_handler in handler.item_handlers if item_handler.closed])
                handler.current_index_model.value = 0
                handler.list_model.remove_item(0)  # built
                self.assertEqual(["a"], [item_handler.item for item_handler in handler.item_handlers if item_handler.closed])

    def test_stack_with_deferred_children_takes_its_size_from_its_properties(self) -> None:
        # tests the sizing rule for deferred construction: a stack given its own size does not depend on measuring
        # children which have not been built.
        with event_loop_context() as event_loop:
            handler = StackItemsHandler(["a", "b", "c"], item_construction="deferred", min_height=60)
            # construct against the canvas ui so that the sizing of the stack can be measured.
            canvas_ui = CanvasUserInterface.CanvasUserInterface(TestUI.UserInterface())
            widget = Declarative.construct_widget(canvas_ui, event_loop, handler)
            with contextlib.closing(widget):
                stack_canvas_item = CanvasUserInterface.extract_canvas_item(typing.cast(UserInterface.Widget, handler.stack))
                assert stack_canvas_item
                self.assertEqual(60, stack_canvas_item.layout_sizing.preferred_height_int)
                handler.current_index_model.value = 2
                self.assertEqual(60, stack_canvas_item.layout_sizing.preferred_height_int)

    def test_stack_builds_deferred_static_children_when_displayed(self) -> None:
        # tests deferred construction for children given directly rather than from a list of items, which is how a
        # stack of pages is usually described.
        u = Declarative.DeclarativeUI()

        class Handler(ItemsHandler):
            def __init__(self) -> None:
                super().__init__()
                self.current_index_model = Model.PropertyModel(0)
                self.ui_view = u.create_stack(u.create_component_instance("item"),
                                              u.create_component_instance("item"),
                                              u.create_component_instance("item"),
                                              current_index="@binding(current_index_model.value)",
                                              item_construction="deferred")

        with event_loop_context() as event_loop:
            handler = Handler()
            widget = Declarative.construct_widget(TestUI.UserInterface(), event_loop, handler)
            with contextlib.closing(widget):
                self.assertEqual(1, len(handler.item_handlers))
                handler.current_index_model.value = 2
                self.assertEqual(2, len(handler.item_handlers))
                handler.current_index_model.value = 0
                self.assertEqual(2, len(handler.item_handlers))

    def test_stack_with_deferred_children_reports_the_largest_child_built(self) -> None:
        # tests that a child which has not been built contributes a known nothing to the size of the stack. a child of
        # unknown size would make the size of the whole stack unknown, leaving it with no size at all until every
        # child had been built.
        u = Declarative.DeclarativeUI()

        class PageHandler(Declarative.Handler):
            def __init__(self, height: int) -> None:
                super().__init__()
                self.ui_view = u.create_column(u.create_label(text="x", height=height, width=50))

        class Handler(Declarative.Handler):
            def __init__(self) -> None:
                super().__init__()
                self.page_stack: typing.Optional[UserInterface.StackWidget] = None
                self.ui_view = u.create_stack(u.create_component_instance("short"),
                                              u.create_component_instance("tall"),
                                              name="page_stack", item_construction="deferred")

            def create_handler(self, component_id: str, **kwargs: typing.Any) -> typing.Optional[PageHandler]:
                return PageHandler(20 if component_id == "short" else 90)

        with event_loop_context() as event_loop:
            canvas_ui = CanvasUserInterface.CanvasUserInterface(TestUI.UserInterface())
            handler = Handler()
            widget = Declarative.construct_widget(canvas_ui, event_loop, handler)
            with contextlib.closing(widget):
                page_stack = typing.cast(UserInterface.StackWidget, handler.page_stack)
                stack_canvas_item = CanvasUserInterface.extract_canvas_item(page_stack)
                assert stack_canvas_item
                # only the first child has been built, so the stack is the size of that child.
                self.assertEqual(20, stack_canvas_item.layout_sizing.preferred_height_int)
                page_stack.current_index = 1
                self.assertEqual(90, stack_canvas_item.layout_sizing.preferred_height_int)
                page_stack.current_index = 0
                # the stack does not shrink back: the taller child is built and still contributes its size.
                self.assertEqual(90, stack_canvas_item.layout_sizing.preferred_height_int)

    def test_declarative_widget_with_item_components_closes_cleanly(self) -> None:
        # a declarative widget closes the handler's closer before the widgets it holds, so the item components are
        # already closed by the time their canvas items are. releasing them a second time must not be an error.
        u = Declarative.DeclarativeUI()

        class Handler(ItemsHandler):
            def __init__(self) -> None:
                super().__init__()
                self.list_model = ListModel.ListModel[str]("items", items=["a", "b"])
                self.ui_view = u.create_list_view(items="list_model.items", item_component_id="item", item_height=20)

        with event_loop_context() as event_loop:
            handler = Handler()
            widget = Declarative.DeclarativeWidget(TestUI.UserInterface(), event_loop, handler)
            widget.close()
            self.assertEqual(["a", "b"], sorted(item_handler.item for item_handler in handler.item_handlers if item_handler.closed))

    def test_item_component_resource_may_not_rename_the_component(self) -> None:
        # tests that a resource supplying the content for an item may not declare a different component id, which
        # would leave the component the handler is asked to create and the content being used disagreeing.
        u = Declarative.DeclarativeUI()

        class Handler(Declarative.Handler):
            def __init__(self) -> None:
                super().__init__()
                self.list_model = ListModel.ListModel[str]("items", items=["a"])
                self.resources = {"item": u.define_component(content=u.create_label(text="item"), component_id="other")}
                self.ui_view = u.create_stack(items="list_model.items", item_component_id="item")

            def create_handler(self, component_id: str, **kwargs: typing.Any) -> typing.Optional[Declarative.Handler]:
                return None

        with event_loop_context() as event_loop:
            with self.assertRaises(AssertionError):
                Declarative.construct_widget(TestUI.UserInterface(), event_loop, Handler())
