# standard libraries
import asyncio
import contextlib
import threading
import typing
import unittest

# third party libraries
# None

# local libraries
from nion.ui import UserInterface
from nion.utils import Model
from nion.utils import Binding


@contextlib.contextmanager
def event_loop_context() -> typing.Iterator[asyncio.AbstractEventLoop]:
    old_event_loop = asyncio.get_event_loop_policy().get_event_loop()
    event_loop = asyncio.new_event_loop()
    asyncio.get_event_loop_policy().set_event_loop(event_loop)
    yield event_loop
    event_loop.stop()
    event_loop.run_forever()
    event_loop.close()
    asyncio.get_event_loop_policy().set_event_loop(old_event_loop)


class TestCanvasItemClass(unittest.TestCase):

    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

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
