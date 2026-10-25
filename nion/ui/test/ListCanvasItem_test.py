# standard libraries
import typing
import unittest

# third party libraries
# None

# local libraries
from nion.ui import Application
from nion.ui import CanvasItem
from nion.ui import DrawingContext
from nion.ui import GridFlowCanvasItem
from nion.ui import ListCanvasItem
from nion.ui import TestUI
from nion.ui import UserInterface
from nion.ui import Widgets
from nion.ui import Window
from nion.utils import Geometry
from nion.utils import ListModel
from nion.utils import Selection


class ListCanvasItemDelegate(ListCanvasItem.ListCanvasItemDelegate):
    def __init__(self) -> None:
        self.on_item_selected: typing.Optional[typing.Callable[[int], None]] = None
        self.on_cancel: typing.Optional[typing.Callable[[], None]] = None

    @property
    def items(self) -> typing.Sequence[typing.Any]:
        return [1, 2, 3, 4]

    @items.setter
    def items(self, value: typing.Sequence[typing.Any]) -> None:
        raise NotImplementedError()

    @property
    def item_count(self) -> int:
        return 4

    def drag_started(self, index: int, x: int, y: int, modifiers: UserInterface.KeyboardModifiers) -> None:
        pass


def make_list_canvas_item(*, item_width: typing.Optional[int] = None, item_height: typing.Optional[int] = None) -> ListCanvasItem.ListCanvasItem2:
    list_model = ListModel.ListModel[int]("items", items=list(range(100)))
    selection = Selection.IndexedSelection()

    def item_factory(item: typing.Any, is_selected_model: typing.Any) -> CanvasItem.AbstractCanvasItem:
        return CanvasItem.EmptyCanvasItem()

    return ListCanvasItem.ListCanvasItem2(list_model, selection, item_factory, GridFlowCanvasItem.GridFlowCanvasItemDelegate(), item_width=item_width, item_height=item_height, key="items")


class PaintCountingListCanvasItemDelegate(ListCanvasItem.ListCanvasItemDelegate):
    """A delegate whose items are their own indexes and which records each item it is asked to paint."""

    def __init__(self, item_count: int) -> None:
        self.on_item_selected: typing.Optional[typing.Callable[[int], None]] = None
        self.on_cancel: typing.Optional[typing.Callable[[], None]] = None
        self.__item_count = item_count
        self.painted_indexes = list[int]()

    @property
    def items(self) -> typing.Sequence[typing.Any]:
        return list(range(self.__item_count))

    @items.setter
    def items(self, value: typing.Sequence[typing.Any]) -> None:
        raise NotImplementedError()

    @property
    def item_count(self) -> int:
        return self.__item_count

    def set_item_count(self, item_count: int) -> None:
        self.__item_count = item_count

    def paint_item(self, drawing_context: DrawingContext.DrawingContext, display_item: typing.Any, rect: Geometry.IntRect, is_selected: bool) -> None:
        self.painted_indexes.append(display_item)


class TrackingItemFactory(GridFlowCanvasItem.GridFlowItemFactoryLike):
    """An item factory that records which items have been created and destroyed."""

    def __init__(self) -> None:
        self.created_items = list[typing.Any]()
        self.destroyed_items = list[typing.Any]()
        self.__items_by_canvas_item = dict[CanvasItem.AbstractCanvasItem, typing.Any]()

    @property
    def live_items(self) -> typing.List[typing.Any]:
        return list(self.__items_by_canvas_item.values())

    def create(self, item: typing.Any, is_selected_model: typing.Any) -> CanvasItem.AbstractCanvasItem:
        canvas_item = CanvasItem.EmptyCanvasItem()
        self.created_items.append(item)
        self.__items_by_canvas_item[canvas_item] = item
        return canvas_item

    def destroy(self, item_canvas_item: CanvasItem.AbstractCanvasItem) -> None:
        self.destroyed_items.append(self.__items_by_canvas_item.pop(item_canvas_item))


class TestListCanvasItemClass(unittest.TestCase):

    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

    def test_shift_click_extends_selection(self) -> None:
        selection = Selection.IndexedSelection()
        delegate = ListCanvasItemDelegate()
        canvas_item = ListCanvasItem.ListCanvasItem(delegate, selection)
        canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize.make((320, 100)))
        self.assertEqual(selection.indexes, set())
        canvas_item.simulate_click(Geometry.IntPoint(y=120, x=50))
        self.assertEqual(selection.indexes, {1})
        modifiers = CanvasItem.KeyboardModifiers(shift=True)
        canvas_item.simulate_click(Geometry.IntPoint(y=200, x=50), modifiers)
        self.assertEqual(selection.indexes, {1, 2})

    def test_start_drag_does_not_change_selection(self) -> None:
        selection = Selection.IndexedSelection()
        delegate = ListCanvasItemDelegate()
        canvas_item = ListCanvasItem.ListCanvasItem(delegate, selection)
        canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize.make((320, 100)))
        self.assertEqual(selection.indexes, set())
        canvas_item.simulate_drag(Geometry.IntPoint(y=120, x=50), Geometry.IntPoint(y=120, x=500))
        self.assertEqual(selection.indexes, set())

    def test_select_all_edit_command_is_disabled_and_keeps_the_selection_of_a_focused_list_which_allows_one_selected_item(self) -> None:
        # the list's selection allows one item, and giving it every item clears it.
        app = Application.BaseApplication(TestUI.UserInterface())
        app.initialize()
        self.addCleanup(app.deinitialize)
        window = Window.Window(app.ui, app=app)
        self.addCleanup(window.close)
        window.build_menu(None, [{"type": "menu", "menu_id": "edit", "title": "Edit", "items": [{"type": "edit_command", "edit_command_id": "select_all"}]}])
        selection = Selection.IndexedSelection(Selection.Style.single_or_none)
        list_canvas_item = ListCanvasItem.ListCanvasItem(ListCanvasItemDelegate(), selection)
        canvas_widget = app.ui.create_canvas_widget()
        canvas_widget.canvas_item.add_canvas_item(list_canvas_item)
        window.attach_widget(canvas_widget)
        canvas_widget.canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=320, height=400))
        list_canvas_item.request_focus()
        selection.set(2)
        # build_menu publishes each top level menu as an attribute named after its menu id.
        menu = typing.cast(UserInterface.Menu, getattr(window, "_edit_menu"))
        menu.about_to_show()
        menu_action = menu.items[0].action
        assert menu_action
        self.assertFalse(menu_action.enabled, "Select All is enabled for a list which allows one selected item")
        menu_action.trigger()
        self.assertEqual({2}, selection.indexes, "Select All changes the selection of a list which allows one selected item")

    def test_select_all_action_is_disabled_and_keeps_the_selection_of_a_focused_list_which_allows_one_selected_item(self) -> None:
        # a menu, such as nionswift's Edit menu, can run Select All through the window.select_all action.
        app = Application.BaseApplication(TestUI.UserInterface())
        app.initialize()
        self.addCleanup(app.deinitialize)
        window = Window.Window(app.ui, app=app)
        self.addCleanup(window.close)
        window.build_menu(None, [{"type": "menu", "menu_id": "edit", "title": "Edit", "items": [{"type": "item", "action_id": "window.select_all"}]}])
        selection = Selection.IndexedSelection(Selection.Style.single_or_none)
        list_canvas_item = ListCanvasItem.ListCanvasItem(ListCanvasItemDelegate(), selection)
        canvas_widget = app.ui.create_canvas_widget()
        canvas_widget.canvas_item.add_canvas_item(list_canvas_item)
        window.attach_widget(canvas_widget)
        canvas_widget.canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=320, height=400))
        list_canvas_item.request_focus()
        selection.set(2)
        # build_menu publishes each top level menu as an attribute named after its menu id.
        menu = typing.cast(UserInterface.Menu, getattr(window, "_edit_menu"))
        menu.about_to_show()
        menu_action = menu.items[0].action
        assert menu_action
        self.assertFalse(menu_action.enabled, "Select All is enabled for a list which allows one selected item")
        window.perform_action("window.select_all", invoked_from=Window.ActionOrigin.MENU)
        self.assertEqual({2}, selection.indexes, "Select All changes the selection of a list which allows one selected item")

    def test_select_all_edit_command_selects_every_item_of_a_focused_list_which_allows_several_selected_items(self) -> None:
        app = Application.BaseApplication(TestUI.UserInterface())
        app.initialize()
        self.addCleanup(app.deinitialize)
        window = Window.Window(app.ui, app=app)
        self.addCleanup(window.close)
        window.build_menu(None, [{"type": "menu", "menu_id": "edit", "title": "Edit", "items": [{"type": "edit_command", "edit_command_id": "select_all"}]}])
        selection = Selection.IndexedSelection(Selection.Style.multiple)
        list_canvas_item = ListCanvasItem.ListCanvasItem(ListCanvasItemDelegate(), selection)
        canvas_widget = app.ui.create_canvas_widget()
        canvas_widget.canvas_item.add_canvas_item(list_canvas_item)
        window.attach_widget(canvas_widget)
        canvas_widget.canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=320, height=400))
        list_canvas_item.request_focus()
        selection.set(2)
        # build_menu publishes each top level menu as an attribute named after its menu id.
        menu = typing.cast(UserInterface.Menu, getattr(window, "_edit_menu"))
        menu.about_to_show()
        menu_action = menu.items[0].action
        assert menu_action
        menu_action.trigger()
        self.assertEqual({0, 1, 2, 3}, selection.indexes, "Select All does not select every item of a list which allows several selected items")

    def test_list_canvas_item_paints_only_the_rows_within_the_viewport(self) -> None:
        # the canvas rect of a list inside a scroll area spans every row of the model, so the rows to paint can only
        # be determined from the visible rect. painting them all makes each scroll step cost the whole model.
        item_height = 20
        viewport_height = 400
        visible_row_count = viewport_height // item_height
        delegate = PaintCountingListCanvasItemDelegate(10000)
        list_canvas_item = ListCanvasItem.ListCanvasItem(delegate, Selection.IndexedSelection(), item_height=item_height)
        scroll_area_canvas_item = CanvasItem.ScrollAreaCanvasItem(list_canvas_item)
        canvas_size = Geometry.IntSize(width=300, height=viewport_height)
        scroll_area_canvas_item.repaint_immediate(DrawingContext.DrawingContext(), canvas_size)
        # a partially visible row at the bottom edge may be painted too.
        self.assertGreaterEqual(len(delegate.painted_indexes), visible_row_count)
        self.assertLessEqual(len(delegate.painted_indexes), visible_row_count + 1)
        # growing the model without growing the viewport must not paint any more rows.
        painted_count = len(delegate.painted_indexes)
        delegate.painted_indexes.clear()
        delegate.set_item_count(20000)
        list_canvas_item.update()
        scroll_area_canvas_item.repaint_immediate(DrawingContext.DrawingContext(), canvas_size)
        self.assertEqual(painted_count, len(delegate.painted_indexes))

    def test_scrolled_list_canvas_item_paints_the_rows_at_the_scroll_position(self) -> None:
        # the rows painted follow the viewport as it scrolls; only the rows under it are painted.
        item_height = 20
        viewport_height = 400
        visible_row_count = viewport_height // item_height
        delegate = PaintCountingListCanvasItemDelegate(10000)
        list_canvas_item = ListCanvasItem.ListCanvasItem(delegate, Selection.IndexedSelection(), item_height=item_height)
        scroll_area_canvas_item = CanvasItem.ScrollAreaCanvasItem(list_canvas_item)
        canvas_size = Geometry.IntSize(width=300, height=viewport_height)
        scroll_area_canvas_item.repaint_immediate(DrawingContext.DrawingContext(), canvas_size)
        delegate.painted_indexes.clear()
        scroll_area_canvas_item.update_content_origin(Geometry.IntPoint(y=-4000))
        scroll_area_canvas_item.repaint_immediate(DrawingContext.DrawingContext(), canvas_size)
        first_visible_row = 4000 // item_height
        self.assertEqual(first_visible_row, delegate.painted_indexes[0])
        self.assertGreaterEqual(len(delegate.painted_indexes), visible_row_count)
        self.assertLessEqual(len(delegate.painted_indexes), visible_row_count + 1)

    def test_list_canvas_item_2_column_layout_tracks_width_and_preserves_scrollable_height(self) -> None:
        # a scroll area with auto_resize_contents enabled should stretch the content to its own width on every
        # layout (so rows always span the full available width), without collapsing the content's height down to
        # the viewport height (which would make the scroll area think there is nothing left to scroll).
        item_height = 20
        list_canvas_item = make_list_canvas_item(item_height=item_height)
        scroll_area_canvas_item = CanvasItem.ScrollAreaCanvasItem(list_canvas_item)
        scroll_area_canvas_item.auto_resize_contents = True
        scroll_area_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=300, height=400))
        self.assertEqual(list_canvas_item.canvas_size, Geometry.IntSize(width=300, height=2000))
        scroll_area_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=500, height=400))
        self.assertEqual(list_canvas_item.canvas_size, Geometry.IntSize(width=500, height=2000))

    def test_list_canvas_item_2_row_layout_tracks_height_and_preserves_scrollable_width(self) -> None:
        # same as above, but for a row of fixed-width columns: height should track the scroll area, while width
        # (the scrollable axis) must remain the full content extent.
        item_width = 20
        list_canvas_item = make_list_canvas_item(item_width=item_width)
        scroll_area_canvas_item = CanvasItem.ScrollAreaCanvasItem(list_canvas_item)
        scroll_area_canvas_item.auto_resize_contents = True
        scroll_area_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=400, height=300))
        self.assertEqual(list_canvas_item.canvas_size, Geometry.IntSize(width=2000, height=300))
        scroll_area_canvas_item.update_layout(Geometry.IntPoint(), Geometry.IntSize(width=400, height=500))
        self.assertEqual(list_canvas_item.canvas_size, Geometry.IntSize(width=2000, height=500))

    def test_item_factory_destroy_is_called_when_item_is_removed(self) -> None:
        # the factory may associate resources with the canvas item (a handler, listeners) that are not part of the
        # canvas item hierarchy; removing an item from the list model must give the factory a chance to release them.
        factory = TrackingItemFactory()
        list_model = ListModel.ListModel[int]("items", items=[0, 1, 2])
        list_canvas_item = ListCanvasItem.ListCanvasItem2(list_model, Selection.IndexedSelection(), factory,
                                                          GridFlowCanvasItem.GridFlowCanvasItemDelegate(),
                                                          item_height=20, key="items")
        self.assertEqual([0, 1, 2], factory.created_items)
        self.assertEqual([], factory.destroyed_items)
        list_model.remove_item(1)
        self.assertEqual([1], factory.destroyed_items)
        self.assertEqual([0, 2], factory.live_items)
        list_canvas_item.close()

    def test_item_factory_destroy_is_called_for_remaining_items_when_closed(self) -> None:
        factory = TrackingItemFactory()
        list_model = ListModel.ListModel[int]("items", items=[0, 1, 2])
        list_canvas_item = ListCanvasItem.ListCanvasItem2(list_model, Selection.IndexedSelection(), factory,
                                                          GridFlowCanvasItem.GridFlowCanvasItemDelegate(),
                                                          item_height=20, key="items")
        list_canvas_item.close()
        self.assertEqual([0, 1, 2], sorted(factory.destroyed_items))
        self.assertEqual([], factory.live_items)

    def test_plain_callable_item_factory_still_works(self) -> None:
        # a factory supplied as a plain create-callable remains valid; it simply has no destroy behavior.
        created_items = list[int]()

        def item_factory(item: typing.Any, is_selected_model: typing.Any) -> CanvasItem.AbstractCanvasItem:
            created_items.append(item)
            return CanvasItem.EmptyCanvasItem()

        list_model = ListModel.ListModel[int]("items", items=[0, 1, 2])
        list_canvas_item = ListCanvasItem.ListCanvasItem2(list_model, Selection.IndexedSelection(), item_factory,
                                                          GridFlowCanvasItem.GridFlowCanvasItemDelegate(),
                                                          item_height=20, key="items")
        self.assertEqual([0, 1, 2], created_items)
        list_model.remove_item(1)
        list_canvas_item.close()

    def test_item_inserted_while_focused_is_focused(self) -> None:
        # an item inserted into a focused list must be focused like the items already there; otherwise selecting the
        # new item draws it with the unfocused selection color even though the list has focus.
        list_model = ListModel.ListModel[int]("items", items=[0, 1])
        list_canvas_item = ListCanvasItem.ListCanvasItem2(list_model, Selection.IndexedSelection(),
                                                          TrackingItemFactory(),
                                                          GridFlowCanvasItem.GridFlowCanvasItemDelegate(),
                                                          item_height=20, key="items")
        list_canvas_item._set_focused(True)
        list_model.append_item(2)
        self.assertEqual([True, True, True], [item_canvas_item.is_focused for item_canvas_item in list_canvas_item._grid_flow_item_canvas_items])
        list_canvas_item.close()

    def test_delete_edit_command_runs_the_action_the_delegate_of_a_focused_list_provides(self) -> None:
        # delete_pressed must not run as well, or the item is removed twice.
        calls = list[str]()

        class DeleteItemsTestAction(Window.Action):
            action_id = "list_canvas_item_test.delete_items"
            action_name = "Delete Items Test"

            def execute(self, context: Window.ActionContext) -> Window.ActionResult:
                calls.append("action")
                return Window.ActionResult(Window.ActionStatus.FINISHED)

        class ActionProvidingDelegate(Widgets.ListCanvasItemDelegate):
            def __init__(self, window: Window.Window) -> None:
                super().__init__()
                self.__window = window

            def delete_pressed(self) -> None:
                calls.append("delete_pressed")

            def get_delete_action(self) -> Window.BoundAction | None:
                return Window.BoundAction(DeleteItemsTestAction(), self.__window._get_action_context())

        app = Application.BaseApplication(TestUI.UserInterface())
        app.initialize()
        self.addCleanup(app.deinitialize)
        window = Window.Window(app.ui, app=app)
        self.addCleanup(window.close)
        list_widget = Widgets.ListWidget(app.ui, ActionProvidingDelegate(window), items=["a", "b", "c"], selection_style=Selection.Style.single_or_none)
        window.attach_widget(list_widget)
        list_widget.focused = True
        list_widget.set_selected_index(1)
        window.perform_edit_command("delete", invoked_from=Window.ActionOrigin.MENU)
        self.assertEqual(["action"], calls, "Delete does not run the action the list's delegate provides once, in place of delete_pressed")

    def test_delete_edit_command_calls_delete_pressed_of_the_delegate_of_a_focused_list(self) -> None:
        delete_pressed_selections = list[set[int]]()

        class RecordingDelegate(Widgets.ListCanvasItemDelegate):
            def delete_pressed(self) -> None:
                delete_pressed_selections.append(set(list_widget.selected_items))

        app = Application.BaseApplication(TestUI.UserInterface())
        app.initialize()
        self.addCleanup(app.deinitialize)
        window = Window.Window(app.ui, app=app)
        self.addCleanup(window.close)
        list_widget = Widgets.ListWidget(app.ui, RecordingDelegate(), items=["a", "b", "c"], selection_style=Selection.Style.single_or_none)
        window.attach_widget(list_widget)
        list_widget.focused = True
        list_widget.set_selected_index(1)
        window.perform_edit_command("delete", invoked_from=Window.ActionOrigin.MENU)
        self.assertEqual([{1}], delete_pressed_selections, "Delete does not call the list's delete_pressed once, with the item selected")
