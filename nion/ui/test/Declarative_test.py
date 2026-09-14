# standard libraries
import asyncio
import contextlib
import threading
import typing
import unittest

# third party libraries
# None

# local libraries
from nion.ui import Declarative
from nion.ui import GridFlowCanvasItem
from nion.ui import ListCanvasItem
from nion.ui import TestUI
from nion.ui import UserInterface
from nion.ui import Window
from nion.utils import Model
from nion.utils import Binding
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
