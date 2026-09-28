from __future__ import annotations

# standard libraries
import typing
import unittest

# third party libraries
# None

# local libraries
from nion.ui import CanvasItem
from nion.ui import GridCanvasItem
from nion.ui import GridFlowCanvasItem
from nion.ui import ListCanvasItem
from nion.utils import Geometry
from nion.utils import ListModel
from nion.utils import Selection


def make_list_canvas_item(list_model: ListModel.ListModel[int], selection: Selection.IndexedSelection, *, is_shared_selection: bool = False) -> ListCanvasItem.ListCanvasItem2:
    def item_factory(item: typing.Any, is_selected_model: typing.Any) -> CanvasItem.AbstractCanvasItem:
        return CanvasItem.EmptyCanvasItem()

    return ListCanvasItem.ListCanvasItem2(list_model, selection, item_factory, GridFlowCanvasItem.GridFlowCanvasItemDelegate(), item_height=20, key="items", is_shared_selection=is_shared_selection)


def drawn_selected_items(grid_flow_canvas_item: GridFlowCanvasItem.GridFlowCanvasItem) -> set[int]:
    # the items whose canvas items are drawn as selected.
    return {canvas_item.item for canvas_item in grid_flow_canvas_item._grid_flow_item_canvas_items if canvas_item.is_selected}


def selected_items(list_model: ListModel.ListModel[int], selection: Selection.IndexedSelection) -> set[int]:
    # the items the selection refers to.
    return {list_model.items[index] for index in selection.indexes}


class TestGridFlowCanvasItemClass(unittest.TestCase):

    def test_removing_selected_item_draws_remaining_selected_items_as_selected(self) -> None:
        list_model = ListModel.ListModel[int]("items", items=list(range(10)))
        selection = Selection.IndexedSelection()
        list_canvas_item = make_list_canvas_item(list_model, selection)
        selection.set_multiple({2, 5})
        list_model.remove_item(2)
        self.assertEqual({5}, selected_items(list_model, selection))
        self.assertEqual({5}, drawn_selected_items(list_canvas_item))
        list_canvas_item.close()

    def test_removing_unselected_item_before_selected_item_keeps_drawing_the_same_item_as_selected(self) -> None:
        list_model = ListModel.ListModel[int]("items", items=list(range(10)))
        selection = Selection.IndexedSelection()
        list_canvas_item = make_list_canvas_item(list_model, selection)
        selection.set(5)
        list_model.remove_item(1)
        self.assertEqual({4}, selection.indexes)
        self.assertEqual({5}, drawn_selected_items(list_canvas_item))
        list_canvas_item.close()

    def test_removing_several_items_in_one_batch_update_draws_remaining_selected_items_as_selected(self) -> None:
        list_model = ListModel.ListModel[int]("items", items=list(range(10)))
        selection = Selection.IndexedSelection()
        list_canvas_item = make_list_canvas_item(list_model, selection)
        selection.set_multiple({2, 5, 8})
        with list_canvas_item.batch_update():
            list_model.remove_item(5)
            list_model.remove_item(0)
            list_model.remove_item(0)
        self.assertEqual({2, 8}, selected_items(list_model, selection))
        self.assertEqual({2, 8}, drawn_selected_items(list_canvas_item))
        list_canvas_item.close()

    def test_removing_items_from_a_grid_draws_remaining_selected_items_as_selected(self) -> None:
        list_model = ListModel.ListModel[int]("items", items=list(range(10)))
        selection = Selection.IndexedSelection()

        def item_factory(item: typing.Any, is_selected_model: typing.Any) -> CanvasItem.AbstractCanvasItem:
            return CanvasItem.EmptyCanvasItem()

        grid_canvas_item = GridCanvasItem.GridCanvasItem2(list_model, selection, item_factory, GridFlowCanvasItem.GridFlowCanvasItemDelegate(), Geometry.IntSize(40, 40), key="items")
        selection.set_multiple({3, 6})
        list_model.remove_item(3)
        list_model.remove_item(0)
        self.assertEqual({6}, selected_items(list_model, selection))
        self.assertEqual({6}, drawn_selected_items(grid_canvas_item))
        grid_canvas_item.close()

    def test_inserting_item_before_selected_items_keeps_drawing_the_same_items_as_selected(self) -> None:
        list_model = ListModel.ListModel[int]("items", items=list(range(10)))
        selection = Selection.IndexedSelection()
        list_canvas_item = make_list_canvas_item(list_model, selection)
        selection.set_multiple({3, 4})
        list_model.insert_item(0, 100)
        self.assertEqual({4, 5}, selection.indexes)
        self.assertEqual({3, 4}, drawn_selected_items(list_canvas_item))
        list_canvas_item.close()

    def test_inserting_item_after_selected_items_keeps_drawing_the_same_items_as_selected(self) -> None:
        list_model = ListModel.ListModel[int]("items", items=list(range(10)))
        selection = Selection.IndexedSelection()
        list_canvas_item = make_list_canvas_item(list_model, selection)
        selection.set_multiple({3, 4})
        list_model.insert_item(8, 100)
        self.assertEqual({3, 4}, selection.indexes)
        self.assertEqual({3, 4}, drawn_selected_items(list_canvas_item))
        list_canvas_item.close()

    def test_inserting_item_among_selected_items_draws_the_new_item_as_unselected(self) -> None:
        list_model = ListModel.ListModel[int]("items", items=list(range(10)))
        selection = Selection.IndexedSelection()
        list_canvas_item = make_list_canvas_item(list_model, selection)
        selection.set_multiple({3, 4})
        list_model.insert_item(4, 100)
        self.assertEqual({3, 5}, selection.indexes)
        self.assertEqual({3, 4}, drawn_selected_items(list_canvas_item))
        list_canvas_item.close()

    def test_inserting_items_with_expanded_changed_event_keeps_drawing_the_same_items_as_selected(self) -> None:
        # a selection with expanded_changed_event fires its changed event while the insert is being handled.
        list_model = ListModel.ListModel[int]("items", items=list(range(10)))
        selection = Selection.IndexedSelection(expanded_changed_event=True)
        list_canvas_item = make_list_canvas_item(list_model, selection)
        selection.set_multiple({3, 4})
        list_model.insert_item(0, 100)
        list_model.insert_item(5, 101)
        list_model.remove_item(4)
        self.assertEqual({4}, drawn_selected_items(list_canvas_item))
        self.assertEqual(selected_items(list_model, selection), drawn_selected_items(list_canvas_item))
        list_canvas_item.close()

    def test_selection_set_draws_only_the_set_item_as_selected(self) -> None:
        list_model = ListModel.ListModel[int]("items", items=list(range(10)))
        selection = Selection.IndexedSelection()
        list_canvas_item = make_list_canvas_item(list_model, selection)
        selection.set_multiple({1, 2})
        selection.set(7)
        self.assertEqual({7}, drawn_selected_items(list_canvas_item))
        list_canvas_item.close()

    def test_selection_add_draws_the_added_item_as_selected(self) -> None:
        list_model = ListModel.ListModel[int]("items", items=list(range(10)))
        selection = Selection.IndexedSelection()
        list_canvas_item = make_list_canvas_item(list_model, selection)
        selection.set(1)
        selection.add(7)
        self.assertEqual({1, 7}, drawn_selected_items(list_canvas_item))
        list_canvas_item.close()

    def test_selection_extend_draws_the_extended_range_as_selected(self) -> None:
        list_model = ListModel.ListModel[int]("items", items=list(range(10)))
        selection = Selection.IndexedSelection()
        list_canvas_item = make_list_canvas_item(list_model, selection)
        selection.set(2)
        selection.extend(5)
        self.assertEqual({2, 3, 4, 5}, drawn_selected_items(list_canvas_item))
        list_canvas_item.close()

    def test_selection_toggle_draws_the_toggled_item_with_its_new_state(self) -> None:
        list_model = ListModel.ListModel[int]("items", items=list(range(10)))
        selection = Selection.IndexedSelection()
        list_canvas_item = make_list_canvas_item(list_model, selection)
        selection.set_multiple({2, 5})
        selection.toggle(5)
        self.assertEqual({2}, drawn_selected_items(list_canvas_item))
        selection.toggle(8)
        self.assertEqual({2, 8}, drawn_selected_items(list_canvas_item))
        list_canvas_item.close()

    def test_selection_clear_draws_no_item_as_selected(self) -> None:
        list_model = ListModel.ListModel[int]("items", items=list(range(10)))
        selection = Selection.IndexedSelection()
        list_canvas_item = make_list_canvas_item(list_model, selection)
        selection.set_multiple({2, 5})
        selection.clear()
        self.assertEqual(set(), drawn_selected_items(list_canvas_item))
        list_canvas_item.close()

    def test_selection_set_multiple_draws_only_the_new_items_as_selected(self) -> None:
        list_model = ListModel.ListModel[int]("items", items=list(range(10)))
        selection = Selection.IndexedSelection()
        list_canvas_item = make_list_canvas_item(list_model, selection)
        selection.set_multiple({1, 2, 3})
        selection.set_multiple({3, 4})
        self.assertEqual({3, 4}, drawn_selected_items(list_canvas_item))
        list_canvas_item.close()

    def test_shared_selection_made_before_creation_is_drawn_as_selected(self) -> None:
        list_model = ListModel.ListModel[int]("items", items=list(range(10)))
        selection = Selection.IndexedSelection()
        selection.set_multiple({2, 5})
        list_canvas_item = make_list_canvas_item(list_model, selection, is_shared_selection=True)
        self.assertEqual({2, 5}, drawn_selected_items(list_canvas_item))
        list_canvas_item.close()

    def test_shared_selection_adjusted_before_removal_is_handled_draws_remaining_selected_items_as_selected(self) -> None:
        # the owner of a shared selection may adjust it before the canvas item handles the removal, so for a moment the
        # selection indexes refer to the list after the removal while the canvas items still match the list before it.
        list_model = ListModel.ListModel[int]("items", items=list(range(10)))
        selection = Selection.IndexedSelection(expanded_changed_event=True)
        item_removed_listener = list_model.item_removed_event.listen(lambda key, item, index: selection.remove_index(index))
        list_canvas_item = make_list_canvas_item(list_model, selection, is_shared_selection=True)
        selection.set_multiple({2, 5, 8})
        list_model.remove_item(5)
        list_model.remove_item(0)
        self.assertEqual({2, 8}, selected_items(list_model, selection))
        self.assertEqual({2, 8}, drawn_selected_items(list_canvas_item))
        list_canvas_item.close()
        del item_removed_listener

    def test_shared_selection_adjusted_after_removal_is_handled_draws_remaining_selected_items_as_selected(self) -> None:
        list_model = ListModel.ListModel[int]("items", items=list(range(10)))
        selection = Selection.IndexedSelection(expanded_changed_event=True)
        list_canvas_item = make_list_canvas_item(list_model, selection, is_shared_selection=True)
        item_removed_listener = list_model.item_removed_event.listen(lambda key, item, index: selection.remove_index(index))
        selection.set_multiple({2, 5, 8})
        list_model.remove_item(5)
        list_model.remove_item(0)
        self.assertEqual({2, 8}, selected_items(list_model, selection))
        self.assertEqual({2, 8}, drawn_selected_items(list_canvas_item))
        list_canvas_item.close()
        del item_removed_listener

    def test_shared_selection_adjusted_before_insertion_is_handled_keeps_drawing_the_same_items_as_selected(self) -> None:
        list_model = ListModel.ListModel[int]("items", items=list(range(10)))
        selection = Selection.IndexedSelection(expanded_changed_event=True)
        item_inserted_listener = list_model.item_inserted_event.listen(lambda key, item, index: selection.insert_index(index))
        list_canvas_item = make_list_canvas_item(list_model, selection, is_shared_selection=True)
        selection.set_multiple({3, 4})
        list_model.insert_item(0, 100)
        list_model.insert_item(5, 101)
        self.assertEqual({3, 4}, selected_items(list_model, selection))
        self.assertEqual({3, 4}, drawn_selected_items(list_canvas_item))
        list_canvas_item.close()
        del item_inserted_listener

    def test_shared_selection_changed_by_its_owner_is_drawn_by_every_canvas_item_sharing_it(self) -> None:
        list_model = ListModel.ListModel[int]("items", items=list(range(10)))
        selection = Selection.IndexedSelection(expanded_changed_event=True)
        list_canvas_item = make_list_canvas_item(list_model, selection, is_shared_selection=True)
        other_list_canvas_item = make_list_canvas_item(list_model, selection, is_shared_selection=True)
        selection.set_multiple({1, 2})
        selection.toggle(1)
        selection.add(6)
        self.assertEqual({2, 6}, drawn_selected_items(list_canvas_item))
        self.assertEqual({2, 6}, drawn_selected_items(other_list_canvas_item))
        list_canvas_item.close()
        other_list_canvas_item.close()


if __name__ == '__main__':
    unittest.main()
