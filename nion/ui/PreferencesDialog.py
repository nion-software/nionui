"""
Preference dialog.
"""

from __future__ import annotations

# standard libraries
import asyncio
import gettext

# third party libraries
# None

# local libraries
import typing

from nion.ui import Declarative
from nion.ui import Dialog
from nion.ui import Widgets
from nion.utils import Event
from nion.utils import Selection

if typing.TYPE_CHECKING:
    from nion.ui import Application
    from nion.ui import UserInterface

_ = gettext.gettext


class Singleton(type):
    def __init__(cls, name: str, bases: typing.Tuple[typing.Type[typing.Any], ...], d: typing.Dict[str, typing.Any]) -> None:
        super(Singleton, cls).__init__(name, bases, d)
        cls.instance: typing.Any = None

    def __call__(cls, *args: typing.Any, **kw: typing.Any) -> typing.Any:
        if cls.instance is None:
            cls.instance = super(Singleton, cls).__call__(*args, **kw)
        return cls.instance


class PreferencePaneDelegate(typing.Protocol):
    identifier: str
    label: str
    def build(self, ui: UserInterface.UserInterface, event_loop: asyncio.AbstractEventLoop, **kwargs: typing.Any) -> Declarative.DeclarativeWidget: ...


class PreferencesManager(metaclass=Singleton):
    def __init__(self) -> None:
        self.preference_pane_delegates: typing.List[PreferencePaneDelegate] = list()
        self.preference_pane_delegates_changed_event = Event.Event()

    def register_preference_pane(self, preference_pane_delegate: PreferencePaneDelegate) -> None:
        assert preference_pane_delegate not in self.preference_pane_delegates
        self.preference_pane_delegates.append(preference_pane_delegate)
        self.preference_pane_delegates_changed_event.fire()

    def unregister_preference_pane(self, preference_pane_delegate: PreferencePaneDelegate) -> None:
        assert preference_pane_delegate in self.preference_pane_delegates
        self.preference_pane_delegates.remove(preference_pane_delegate)
        self.preference_pane_delegates_changed_event.fire()


class EmptyPreferencePanel:
    def __init__(self) -> None:
        self.identifier = "empty_preferences"
        self.label = _("Preferences")

    def build(self, ui: UserInterface.UserInterface, event_loop: asyncio.AbstractEventLoop,
              **kwargs: typing.Any) -> Declarative.DeclarativeWidget:
        u = Declarative.DeclarativeUI()

        class Handler(Declarative.HandlerLike):
            def __init__(self, ui_view: Declarative.UIDescription) -> None:
                self.ui_view = ui_view

            def close(self) -> None:
                pass

        no_content_row = u.create_row(u.create_stretch(), u.create_label(text=_("No Preferences Available")),
                                      u.create_stretch())
        content = u.create_column(no_content_row)
        return Declarative.DeclarativeWidget(ui, event_loop, Handler(content))


class PreferencesDialog(Dialog.ActionDialog):
    def __init__(self, ui: UserInterface.UserInterface, app: Application.BaseApplication) -> None:
        super().__init__(ui, _("Preferences"), app=app)

        self.ui = ui
        self.document_controller = self

        properties = dict()
        properties["min-height"] = 400
        properties["min-width"] = 800

        preference_pane_delegates: typing.List[PreferencePaneDelegate] = list()
        preference_pane_delegate_id_ref: typing.List[typing.Optional[str]] = [None]

        content_stack = ui.create_stack_widget()

        def change_selection(indexes: typing.AbstractSet[int]) -> None:
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

        def rebuild() -> None:
            content_stack.remove_all()
            preference_pane_delegates.clear()
            preference_pane_delegate_id = preference_pane_delegate_id_ref[0]
            items = list()
            selected_index = 0
            delegates = PreferencesManager().preference_pane_delegates
            if not delegates:
                delegates.append(EmptyPreferencePanel())
            for index, preference_pane_delegate in enumerate(delegates):
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

    def close(self) -> None:
        self.__preference_pane_delegates_changed_listener.close()
        self.__preference_pane_delegates_changed_listener = typing.cast(typing.Any, None)
        super().close()
