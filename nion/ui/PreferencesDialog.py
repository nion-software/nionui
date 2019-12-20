"""
Preference dialog.
"""

# standard libraries
import gettext

# types
from typing import AbstractSet

# third party libraries
# None

# local libraries
from nion.ui import Dialog
from nion.ui import Widgets
from nion.utils import Event
from nion.utils import Selection

_ = gettext.gettext


class Singleton(type):
    def __init__(cls, name, bases, dict):
        super(Singleton, cls).__init__(name, bases, dict)
        cls.instance = None

    def __call__(cls, *args, **kw):
        if cls.instance is None:
            cls.instance = super(Singleton, cls).__call__(*args, **kw)
        return cls.instance


class PreferencesManager(metaclass=Singleton):
    def __init__(self):
        self.preference_pane_delegates = list()
        self.preference_pane_delegates_changed_event = Event.Event()

    def register_preference_pane(self, preference_pane_delegate):
        assert not preference_pane_delegate in self.preference_pane_delegates
        self.preference_pane_delegates.append(preference_pane_delegate)
        self.preference_pane_delegates_changed_event.fire()

    def unregister_preference_pane(self, preference_pane_delegate):
        assert preference_pane_delegate in self.preference_pane_delegates
        self.preference_pane_delegates.remove(preference_pane_delegate)
        self.preference_pane_delegates_changed_event.fire()


class PreferencesDialog(Dialog.ActionDialog):
    def __init__(self, ui, app):
        super().__init__(ui, _("Preferences"), app)

        self.ui = ui
        self.document_controller = self

        self._create_menus()

        properties = dict()
        properties["min-height"] = 400
        properties["min-width"] = 800

        preference_pane_delegates = list()
        preference_pane_delegate_id_ref = [None]

        content_stack = ui.create_stack_widget()

        def change_selection(indexes):
            index = list(indexes)[0]
            assert 0 <= index < len(preference_pane_delegates)
            content_stack.current_index = index
            preference_pane_delegate_id_ref[0] = preference_pane_delegates[index].identifier

        selector_list_widget = Widgets.StringListWidget(ui, selection_style=Selection.Style.single_or_none)
        selector_list_widget.on_selection_changed = change_selection

        row = self.ui.create_row_widget(properties={"min-width": 640, "min-height": 320})
        selector_column = self.ui.create_column_widget(properties={"width": 200})
        selector_row = ui.create_row_widget()
        selector_row.add_spacing(8)
        selector_row.add(selector_list_widget)
        selector_row.add_spacing(8)
        selector_column.add_spacing(8)
        selector_column.add(selector_row)
        selector_column.add_spacing(8)
        content_column = self.ui.create_column_widget()
        content_column.add(content_stack)
        row.add(selector_column)
        row.add(content_column)
        self.content.add(row)

        self.add_button(_("Done"), lambda: True)

        def rebuild():
            content_stack.remove_all()
            preference_pane_delegates.clear()
            preference_pane_delegate_id = preference_pane_delegate_id_ref[0]
            items = list()
            selected_index = 0
            for index, preference_pane_delegate in enumerate(PreferencesManager().preference_pane_delegates):
                preference_pane_delegates.append(preference_pane_delegate)
                content_column_widget = ui.create_column_widget()
                content_column_widget.add_spacing(12)
                content_column_widget.add(preference_pane_delegate.build(ui, event_loop=self.event_loop))
                content_column_widget.add_spacing(12)
                content_row_widget = ui.create_row_widget()
                content_row_widget.add_spacing(12)
                content_row_widget.add(content_column_widget)
                content_row_widget.add_spacing(12)
                content_stack.add(content_row_widget)
                items.append(preference_pane_delegate.label)
                if preference_pane_delegate.identifier == preference_pane_delegate_id:
                    selected_index = index
            change_selection({selected_index})
            selector_list_widget.items = items

        self.__preference_pane_delegates_changed_listener = PreferencesManager().preference_pane_delegates_changed_event.listen(rebuild)

        rebuild()

    def close(self):
        self.__preference_pane_delegates_changed_listener.close()
        self.__preference_pane_delegates_changed_listener = None
        super().close()
