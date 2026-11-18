# standard libraries
import asyncio
import contextlib
import dataclasses
import datetime
import typing
import unittest

# third party libraries
# None

# local libraries
from nion.ui import TestUI
from nion.ui import UserInterface
from nion.ui import Widgets
from nion.utils import Binding
from nion.utils import Model


class PeriodicCountingWidget(UserInterface.Widget):
    """A widget which counts the calls to its periodic, standing in for a subclass which overrides periodic."""

    def __init__(self, *, is_registered: bool = True) -> None:
        super().__init__(TestUI.WidgetBehavior("periodic_counting", None))
        self.periodic_count = 0
        if is_registered:
            self.register_periodic()

    def periodic(self) -> None:
        super().periodic()
        self.periodic_count += 1


class EqualPeriodicCountingWidget(PeriodicCountingWidget):
    """A periodic counting widget which compares equal to every other and so cannot be hashed."""

    def __eq__(self, other: object) -> bool:
        return isinstance(other, EqualPeriodicCountingWidget)

    __hash__ = None  # type: ignore[assignment]


class TestUserInterfacePeriodicClass(unittest.TestCase):

    def test_canvas_widget_nested_within_containers_receives_window_periodic(self) -> None:
        ui = TestUI.UserInterface()
        window = TestUI.DocumentWindow()
        with contextlib.closing(window):
            column = ui.create_column_widget()
            row = ui.create_row_widget()
            canvas_widget = ui.create_canvas_widget()
            periodic_calls = list[bool]()
            canvas_widget.on_periodic = lambda: periodic_calls.append(True)
            row.add(canvas_widget)
            column.add(row)
            window.attach(column)
            window._handle_periodic()
            self.assertEqual(1, len(periodic_calls))

    def test_canvas_widget_added_after_attaching_receives_window_periodic(self) -> None:
        ui = TestUI.UserInterface()
        window = TestUI.DocumentWindow()
        with contextlib.closing(window):
            column = ui.create_column_widget()
            window.attach(column)
            row = ui.create_row_widget()
            column.add(row)
            canvas_widget = ui.create_canvas_widget()
            periodic_calls = list[bool]()
            canvas_widget.on_periodic = lambda: periodic_calls.append(True)
            row.add(canvas_widget)
            window._handle_periodic()
            self.assertEqual(1, len(periodic_calls))

    def test_canvas_widget_in_dock_widget_receives_dock_widget_periodic(self) -> None:
        ui = TestUI.UserInterface()
        window = TestUI.DocumentWindow()
        with contextlib.closing(window):
            column = ui.create_column_widget()
            canvas_widget = ui.create_canvas_widget()
            periodic_calls = list[bool]()
            canvas_widget.on_periodic = lambda: periodic_calls.append(True)
            column.add(canvas_widget)
            dock_widget = window.create_dock_widget(column, "panel", "Panel", ["left"], "left")
            with contextlib.closing(dock_widget):
                dock_widget.periodic()
                self.assertEqual(1, len(periodic_calls))
                # the window does not deliver periodic to what is in its dock widgets; the dock widget does.
                window._handle_periodic()
                self.assertEqual(1, len(periodic_calls))

    def test_canvas_widget_removed_from_its_container_no_longer_receives_periodic(self) -> None:
        ui = TestUI.UserInterface()
        window = TestUI.DocumentWindow()
        with contextlib.closing(window):
            stack = ui.create_stack_widget()
            canvas_widget = ui.create_canvas_widget()
            with contextlib.closing(canvas_widget):
                periodic_calls = list[bool]()
                canvas_widget.on_periodic = lambda: periodic_calls.append(True)
                stack.add(canvas_widget)
                window.attach(stack)
                window._handle_periodic()
                # removing from a stack widget does not close the removed widget, so it is closed here instead.
                stack.remove(canvas_widget)
                window._handle_periodic()
                self.assertEqual(1, len(periodic_calls))

    def test_canvas_widget_closed_by_the_periodic_of_another_is_skipped(self) -> None:
        ui = TestUI.UserInterface()
        window = TestUI.DocumentWindow()
        with contextlib.closing(window):
            column = ui.create_column_widget()
            first_canvas_widget = ui.create_canvas_widget()
            second_canvas_widget = ui.create_canvas_widget()
            second_periodic_calls = list[bool]()
            first_canvas_widget.on_periodic = lambda: column.remove(second_canvas_widget)
            second_canvas_widget.on_periodic = lambda: second_periodic_calls.append(True)
            column.add(first_canvas_widget)
            column.add(second_canvas_widget)
            # a dock widget does not catch exceptions, so calling periodic on the closed widget would raise here.
            dock_widget = window.create_dock_widget(column, "panel", "Panel", ["left"], "left")
            with contextlib.closing(dock_widget):
                dock_widget.periodic()
                self.assertEqual(0, len(second_periodic_calls))

    def test_dock_widget_reports_each_close_and_reopen_once(self) -> None:
        ui = TestUI.UserInterface()
        window = TestUI.DocumentWindow()
        with contextlib.closing(window):
            dock_widget = window.create_dock_widget(ui.create_column_widget(), "panel", "Panel", ["left"], "left")
            with contextlib.closing(dock_widget):
                dock_widget.show()
                is_open_values = list[bool]()
                is_open_changed_listener = dock_widget.is_open_changed_event.listen(is_open_values.append)
                dock_widget.hide()
                self.assertEqual([False], is_open_values)
                dock_widget.show()
                self.assertEqual([False, True], is_open_values)

    def test_hiding_a_hidden_dock_widget_reports_no_change(self) -> None:
        ui = TestUI.UserInterface()
        window = TestUI.DocumentWindow()
        with contextlib.closing(window):
            dock_widget = window.create_dock_widget(ui.create_column_widget(), "panel", "Panel", ["left"], "left")
            with contextlib.closing(dock_widget):
                is_open_values = list[bool]()
                is_open_changed_listener = dock_widget.is_open_changed_event.listen(is_open_values.append)
                dock_widget.hide()
                self.assertEqual([], is_open_values)

    def test_widget_registered_for_periodic_follows_it_to_another_window(self) -> None:
        ui = TestUI.UserInterface()
        first_window = TestUI.DocumentWindow()
        second_window = TestUI.DocumentWindow()
        with contextlib.closing(first_window), contextlib.closing(second_window):
            first_stack = ui.create_stack_widget()
            second_stack = ui.create_stack_widget()
            first_window.attach(first_stack)
            second_window.attach(second_stack)
            widget = PeriodicCountingWidget()
            first_stack.add(widget)
            first_window._handle_periodic()
            self.assertEqual(1, widget.periodic_count)
            first_stack.remove(widget)
            second_stack.add(widget)
            first_window._handle_periodic()
            self.assertEqual(1, widget.periodic_count)
            second_window._handle_periodic()
            self.assertEqual(2, widget.periodic_count)

    def test_canvas_widget_in_replaced_scroll_area_content_no_longer_receives_periodic(self) -> None:
        ui = TestUI.UserInterface()
        window = TestUI.DocumentWindow()
        with contextlib.closing(window):
            scroll_area = ui.create_scroll_area_widget()
            window.attach(scroll_area)
            old_content = ui.create_canvas_widget()
            # replacing the content of a scroll area does not close the replaced content, so it is closed here instead.
            with contextlib.closing(old_content):
                old_periodic_calls = list[bool]()
                old_content.on_periodic = lambda: old_periodic_calls.append(True)
                scroll_area.content = old_content
                window._handle_periodic()
                scroll_area.content = ui.create_canvas_widget()
                window._handle_periodic()
                self.assertEqual(1, len(old_periodic_calls))

    def test_canvas_widget_in_replaced_root_widget_no_longer_receives_periodic(self) -> None:
        ui = TestUI.UserInterface()
        window = TestUI.DocumentWindow()
        with contextlib.closing(window):
            old_root_widget = ui.create_canvas_widget()
            # attaching a new root widget does not close the replaced one, so it is closed here instead.
            with contextlib.closing(old_root_widget):
                old_periodic_calls = list[bool]()
                old_root_widget.on_periodic = lambda: old_periodic_calls.append(True)
                window.attach(old_root_widget)
                window._handle_periodic()
                window.attach(ui.create_canvas_widget())
                window._handle_periodic()
                self.assertEqual(1, len(old_periodic_calls))

    def test_widget_overriding_periodic_without_registering_is_not_called_by_window_periodic(self) -> None:
        # the window calls only what registers, rather than walking its widget tree.
        ui = TestUI.UserInterface()
        window = TestUI.DocumentWindow()
        with contextlib.closing(window):
            column = ui.create_column_widget()
            widget = PeriodicCountingWidget(is_registered=False)
            column.add(widget)
            window.attach(column)
            window._handle_periodic()
            self.assertEqual(0, widget.periodic_count)

    def test_registered_widget_within_each_kind_of_registered_container_receives_periodic_once(self) -> None:
        # a registered container must not also deliver periodic to what it contains, or that is called twice.
        ui = TestUI.UserInterface()

        def make_box(child: UserInterface.Widget) -> UserInterface.Widget:
            box = ui.create_column_widget()
            box.add(child)
            return box

        def make_splitter(child: UserInterface.Widget) -> UserInterface.Widget:
            splitter = ui.create_splitter_widget()
            splitter.add(child)
            return splitter

        def make_tab(child: UserInterface.Widget) -> UserInterface.Widget:
            tab = ui.create_tab_widget()
            tab.add(child, "Tab")
            return tab

        def make_stack(child: UserInterface.Widget) -> UserInterface.Widget:
            stack = ui.create_stack_widget()
            stack.add(child)
            return stack

        def make_group(child: UserInterface.Widget) -> UserInterface.Widget:
            group = ui.create_group_widget()
            group.add(child)
            return group

        def make_scroll_area(child: UserInterface.Widget) -> UserInterface.Widget:
            scroll_area = ui.create_scroll_area_widget()
            scroll_area.content = child
            return scroll_area

        def make_composite(child: UserInterface.Widget) -> UserInterface.Widget:
            return Widgets.CompositeWidgetBase(child)

        container_makers: typing.Mapping[str, typing.Callable[[UserInterface.Widget], UserInterface.Widget]] = {
            "box": make_box,
            "splitter": make_splitter,
            "tab": make_tab,
            "stack": make_stack,
            "group": make_group,
            "scroll_area": make_scroll_area,
            "composite": make_composite,
        }
        for container_name, make_container in container_makers.items():
            with self.subTest(container=container_name):
                window = TestUI.DocumentWindow()
                with contextlib.closing(window):
                    widget = PeriodicCountingWidget()
                    container = make_container(widget)
                    container.register_periodic()
                    window.attach(container)
                    window._handle_periodic()
                    self.assertEqual(1, widget.periodic_count)

    def test_registered_widgets_which_compare_equal_each_receive_periodic(self) -> None:
        ui = TestUI.UserInterface()
        window = TestUI.DocumentWindow()
        with contextlib.closing(window):
            column = ui.create_column_widget()
            first_widget = EqualPeriodicCountingWidget()
            second_widget = EqualPeriodicCountingWidget()
            column.add(first_widget)
            column.add(second_widget)
            window.attach(column)
            window._handle_periodic()
            self.assertEqual(1, first_widget.periodic_count)
            self.assertEqual(1, second_widget.periodic_count)


class TestUserInterfaceLineEditClass(unittest.TestCase):

    def test_clicking_a_button_while_typing_in_a_line_edit_finishes_the_edit_first(self) -> None:
        # a binding needs an event loop.
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)
        self.addCleanup(event_loop.close)
        self.addCleanup(asyncio.set_event_loop, None)
        ui = TestUI.UserInterface()
        window = TestUI.DocumentWindow()
        with contextlib.closing(window):
            name_model = Model.PropertyModel("old")
            column = ui.create_column_widget()
            line_edit = ui.create_line_edit_widget()
            line_edit.bind_text(Binding.PropertyBinding(name_model, "value"))
            button = ui.create_push_button_widget("OK")
            names_when_clicked = list[str | None]()
            button.on_clicked = lambda: names_when_clicked.append(name_model.value)
            column.add(line_edit)
            column.add(button)
            window.attach(column)
            line_edit.focused = True
            # typing changes the text and doesn't finish editing; the click arrives as a real one does, through the button.
            line_edit._behavior.text = "new"
            button_clicked = button._behavior.on_clicked
            assert button_clicked
            button_clicked()
            self.assertEqual(["new"], names_when_clicked)


# locale data abridged from Qt for en_US, de_DE, ja_JP and pl_PL, in LocaleInfo notation.
EN_US_LOCALE_INFO = UserInterface.LocaleInfo(
    short_time_pattern="h:mm a", short_date_pattern="M/d/yy", long_date_pattern="EEEE, MMMM d, yyyy",
    month_names=("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"),
    month_abbreviations=("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
    standalone_month_names=("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"),
    standalone_month_abbreviations=("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
    day_names=("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
    day_abbreviations=("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    am_text="AM", pm_text="PM", zero_digit="0")

DE_DE_LOCALE_INFO = UserInterface.LocaleInfo(
    short_time_pattern="HH:mm", short_date_pattern="dd.MM.yy", long_date_pattern="EEEE, d. MMMM yyyy",
    month_names=("Januar", "Februar", "M\N{LATIN SMALL LETTER A WITH DIAERESIS}rz", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"),
    month_abbreviations=("Jan.", "Feb.", "M\N{LATIN SMALL LETTER A WITH DIAERESIS}rz", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sept.", "Okt.", "Nov.", "Dez."),
    standalone_month_names=("Januar", "Februar", "M\N{LATIN SMALL LETTER A WITH DIAERESIS}rz", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"),
    standalone_month_abbreviations=("Jan", "Feb", "M\N{LATIN SMALL LETTER A WITH DIAERESIS}r", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"),
    day_names=("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"),
    day_abbreviations=("Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa.", "So."),
    am_text="AM", pm_text="PM", zero_digit="0")

JA_JP_LOCALE_INFO = UserInterface.LocaleInfo(
    short_time_pattern="H:mm", short_date_pattern="yyyy/MM/dd",
    long_date_pattern="yyyy\N{CJK UNIFIED IDEOGRAPH-5E74}M\N{CJK UNIFIED IDEOGRAPH-6708}d\N{CJK UNIFIED IDEOGRAPH-65E5}EEEE",
    month_names=tuple(f"{month}\N{CJK UNIFIED IDEOGRAPH-6708}" for month in range(1, 13)),
    month_abbreviations=tuple(f"{month}\N{CJK UNIFIED IDEOGRAPH-6708}" for month in range(1, 13)),
    standalone_month_names=tuple(f"{month}\N{CJK UNIFIED IDEOGRAPH-6708}" for month in range(1, 13)),
    standalone_month_abbreviations=tuple(f"{month}\N{CJK UNIFIED IDEOGRAPH-6708}" for month in range(1, 13)),
    day_names=("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),  # placeholders; no test uses Japanese day names.
    day_abbreviations=("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    am_text="AM", pm_text="PM", zero_digit="0")

PL_PL_LOCALE_INFO = UserInterface.LocaleInfo(
    short_time_pattern="HH:mm", short_date_pattern="d.MM.yyyy", long_date_pattern="EEEE, d MMMM yyyy",
    month_names=("stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "wrze\N{LATIN SMALL LETTER S WITH ACUTE}nia",
        "pa\N{LATIN SMALL LETTER Z WITH ACUTE}dziernika", "listopada", "grudnia"),
    month_abbreviations=("sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "pa\N{LATIN SMALL LETTER Z WITH ACUTE}", "lis", "gru"),
    standalone_month_names=("stycze\N{LATIN SMALL LETTER N WITH ACUTE}", "luty", "marzec", "kwiecie\N{LATIN SMALL LETTER N WITH ACUTE}", "maj", "czerwiec", "lipiec",
        "sierpie\N{LATIN SMALL LETTER N WITH ACUTE}", "wrzesie\N{LATIN SMALL LETTER N WITH ACUTE}", "pa\N{LATIN SMALL LETTER Z WITH ACUTE}dziernik", "listopad",
        "grudzie\N{LATIN SMALL LETTER N WITH ACUTE}"),
    standalone_month_abbreviations=("sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "pa\N{LATIN SMALL LETTER Z WITH ACUTE}", "lis", "gru"),
    day_names=("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),  # placeholders; no test uses Polish day names.
    day_abbreviations=("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    am_text="AM", pm_text="PM", zero_digit="0")


class LocaleUserInterface(TestUI.UserInterface):
    """A test user interface with a fixed locale."""

    def __init__(self, locale_info: UserInterface.LocaleInfo) -> None:
        super().__init__()
        self.__locale_info = locale_info

    def get_locale_info(self) -> UserInterface.LocaleInfo | None:
        return self.__locale_info


class TestUserInterfaceFormatDateTimeClass(unittest.TestCase):

    def test_format_date_time_writes_the_time_in_the_locale(self) -> None:
        local_datetime = datetime.datetime(2026, 11, 9, 14, 5, 3)
        self.assertEqual("2:05 PM", LocaleUserInterface(EN_US_LOCALE_INFO).format_date_time(local_datetime, "jm"))
        self.assertEqual("2:05:03 PM", LocaleUserInterface(EN_US_LOCALE_INFO).format_date_time(local_datetime, "jms"))
        self.assertEqual("14:05:03", LocaleUserInterface(DE_DE_LOCALE_INFO).format_date_time(local_datetime, "jms"))

    def test_format_date_time_writes_midnight_and_noon_on_a_12_hour_clock(self) -> None:
        self.assertEqual("12:05 AM", LocaleUserInterface(EN_US_LOCALE_INFO).format_date_time(datetime.datetime(2026, 11, 9, 0, 5), "jm"))
        self.assertEqual("12:00 PM", LocaleUserInterface(EN_US_LOCALE_INFO).format_date_time(datetime.datetime(2026, 11, 9, 12, 0), "jm"))

    def test_format_date_time_writes_seconds_with_the_separator_of_the_minute(self) -> None:
        # Finnish separates the minute with a period, and Yoruba writes the minute as one digit.
        local_datetime = datetime.datetime(2026, 11, 9, 14, 5, 3)
        self.assertEqual("14.05.03", LocaleUserInterface(dataclasses.replace(DE_DE_LOCALE_INFO, short_time_pattern="H.mm")).format_date_time(local_datetime, "jms"))
        self.assertEqual("14:5:03", LocaleUserInterface(dataclasses.replace(DE_DE_LOCALE_INFO, short_time_pattern="H:m")).format_date_time(local_datetime, "jms"))

    def test_format_date_time_writes_seconds_with_a_colon_when_the_minute_is_separated_by_a_word(self) -> None:
        # Dzongkha separates the minute with its word for minute.
        minute_word = "\N{TIBETAN LETTER SA}\N{TIBETAN SUBJOINED LETTER KA}\N{TIBETAN LETTER RA}\N{TIBETAN MARK INTERSYLLABIC TSHEG}\N{TIBETAN LETTER MA}\N{TIBETAN MARK INTERSYLLABIC TSHEG}"
        dzongkha_locale_info = dataclasses.replace(DE_DE_LOCALE_INFO, short_time_pattern=f"H {minute_word} mm")
        local_datetime = datetime.datetime(2026, 11, 9, 14, 5, 3)
        self.assertEqual(f"14 {minute_word} 05:03", LocaleUserInterface(dzongkha_locale_info).format_date_time(local_datetime, "jms"))

    def test_format_date_time_writes_the_digits_of_the_locale(self) -> None:
        arabic_locale_info = dataclasses.replace(EN_US_LOCALE_INFO, zero_digit="\N{ARABIC-INDIC DIGIT ZERO}")
        local_datetime = datetime.datetime(2026, 11, 9, 14, 5, 3)
        self.assertEqual("\N{ARABIC-INDIC DIGIT TWO}:\N{ARABIC-INDIC DIGIT ZERO}\N{ARABIC-INDIC DIGIT FIVE} PM", LocaleUserInterface(arabic_locale_info).format_date_time(local_datetime, "jm"))

    def test_format_date_time_writes_the_date_in_the_locale(self) -> None:
        local_datetime = datetime.datetime(2026, 3, 9, 14, 5, 3)
        self.assertEqual("Mar 9", LocaleUserInterface(EN_US_LOCALE_INFO).format_date_time(local_datetime, "MMMd"))
        self.assertEqual("3/2026", LocaleUserInterface(EN_US_LOCALE_INFO).format_date_time(local_datetime, "yMM"))
        self.assertEqual("03.2026", LocaleUserInterface(DE_DE_LOCALE_INFO).format_date_time(local_datetime, "yMM"))
        self.assertEqual("Monday, March 9", LocaleUserInterface(EN_US_LOCALE_INFO).format_date_time(local_datetime, "MMMMEEEEd"))

    def test_format_date_time_keeps_the_punctuation_of_the_locale(self) -> None:
        local_datetime = datetime.datetime(2026, 11, 9, 14, 5, 3)
        self.assertEqual("9. Nov.", LocaleUserInterface(DE_DE_LOCALE_INFO).format_date_time(local_datetime, "MMMd"))
        self.assertEqual("11\N{CJK UNIFIED IDEOGRAPH-6708}9\N{CJK UNIFIED IDEOGRAPH-65E5}", LocaleUserInterface(JA_JP_LOCALE_INFO).format_date_time(local_datetime, "MMMd"))

    def test_format_date_time_keeps_text_before_the_first_field(self) -> None:
        # Low German writes "Kl." before the time.
        low_german_locale_info = dataclasses.replace(DE_DE_LOCALE_INFO, short_time_pattern="'Kl'. H.mm")
        local_datetime = datetime.datetime(2026, 11, 9, 14, 5, 3)
        self.assertEqual("Kl. 14.05", LocaleUserInterface(low_german_locale_info).format_date_time(local_datetime, "jm"))

    def test_format_date_time_leaves_out_punctuation_after_the_last_field(self) -> None:
        # the Urdu long date separates its fields with an Arabic comma.
        urdu_locale_info = dataclasses.replace(EN_US_LOCALE_INFO, long_date_pattern="EEEE\N{ARABIC COMMA} d MMMM\N{ARABIC COMMA} yyyy")
        local_datetime = datetime.datetime(2026, 11, 9, 14, 5, 3)
        self.assertEqual("9 Nov", LocaleUserInterface(urdu_locale_info).format_date_time(local_datetime, "MMMd"))

    def test_format_date_time_writes_a_month_without_a_day_in_its_standalone_form(self) -> None:
        local_datetime = datetime.datetime(2026, 11, 9, 14, 5, 3)
        self.assertEqual("listopad 2026", LocaleUserInterface(PL_PL_LOCALE_INFO).format_date_time(local_datetime, "yMMMM"))
        self.assertEqual("9 listopada", LocaleUserInterface(PL_PL_LOCALE_INFO).format_date_time(local_datetime, "MMMMd"))

    def test_format_date_time_joins_a_date_and_a_time(self) -> None:
        local_datetime = datetime.datetime(2026, 11, 9, 14, 5, 3)
        self.assertEqual("Nov 9, 2026 2:05 PM", LocaleUserInterface(EN_US_LOCALE_INFO).format_date_time(local_datetime, "yMMMdjm"))
        self.assertEqual("9. Nov. 2026 14:05", LocaleUserInterface(DE_DE_LOCALE_INFO).format_date_time(local_datetime, "yMMMdjm"))

    def test_format_date_time_writes_an_explicit_clock_in_the_locale_clock(self) -> None:
        # an explicit 12-hour or 24-hour clock is not supported, so these differ from the Unicode standard's results.
        local_datetime = datetime.datetime(2026, 11, 9, 14, 5, 3)
        self.assertEqual("2:05 PM", LocaleUserInterface(EN_US_LOCALE_INFO).format_date_time(local_datetime, "Hm"))
        self.assertEqual("14:05", LocaleUserInterface(DE_DE_LOCALE_INFO).format_date_time(local_datetime, "hm"))

    def test_format_date_time_writes_an_unsupported_skeleton_as_a_fallback(self) -> None:
        # a two-digit year, an hour alone and a weekday with a numeric month are not supported, so these differ from the
        # Unicode standard's results.
        local_datetime = datetime.datetime(2026, 11, 9, 14, 5, 3)
        self.assertEqual("11/2026", LocaleUserInterface(EN_US_LOCALE_INFO).format_date_time(local_datetime, "yyMM"))
        self.assertEqual("2:05 PM", LocaleUserInterface(EN_US_LOCALE_INFO).format_date_time(local_datetime, "j"))
        self.assertEqual("Mon, Nov 9", LocaleUserInterface(EN_US_LOCALE_INFO).format_date_time(local_datetime, "MEd"))

    def test_format_date_time_without_a_locale_writes_fixed_forms(self) -> None:
        ui = TestUI.UserInterface()
        local_datetime = datetime.datetime(2026, 11, 9, 14, 5, 3)
        self.assertEqual("14:05:03", ui.format_date_time(local_datetime, "jms"))
        self.assertEqual("11-09", ui.format_date_time(local_datetime, "MMMd"))
        self.assertEqual("2026-11 14:05", ui.format_date_time(local_datetime, "yMMjm"))
        self.assertEqual("Mon 2026-11-09", ui.format_date_time(local_datetime, "EyMd"))


if __name__ == '__main__':
    unittest.main()
