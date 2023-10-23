Changelog (nionui)
==================

7.0.1 (2023-10-23)
------------------
- Minor changes for Python 3.12 compatibility.

7.0.0 (2023-08-16)
------------------
- Render SVG images with pixelated images.
- Many changes to layout engine to simplify and make it easier to use.

0.6.11 (2023-06-19)
-------------------
- Fix issue with closing application, improve compatibility with Qt 6.5.
- Change fallback behavior for preferences to not use old preferences.
- Allow binding for placeholder text in line edit.
- Implement visible property to dock widgets.
- Eliminate spurious write to persistent storage when initializing section widget.
- Improve handling of wheel scrolling.

0.6.10 (2022-12-19)
-------------------
- Add support for text browser (markdown), requires tool 0.4.18 or later.

0.6.9 (2022-11-04)
------------------
- Automatically activate windows when showing them.
- Use alternate low level asyncio on Windows to avoid crash/bug in default.
- Fix race condition in binding helper.

0.6.8 (2022-10-06)
------------------
- Introduce a Bitmap object to optionally replace uses of NDArray/uint32 bitmaps.

0.6.6 (2022-10-03)
------------------
- Fix regression where line edits not using latest text when still focused.
- Improved look for basic (canvas item) tabs.
- Allow background color to be a gradient in most cases.
- Add ability to set specific borders and margins independently in declarative UI.

0.6.5 (2022-09-13)
------------------
- Add a bindable background_color property to widgets, requires tool 0.4.15 or later.
- Add a declarative twist-down section widget.
- Add Path object and method to add it to drawing context.
- Add a alternate compact Tab implementation.
- Add ability to bind text_color property of declarative label.
- Fix issue with dialogs being closed twice.

0.6.4 (2022-07-25)
------------------
- Minor code maintenance.

0.6.3 (2022-04-20)
------------------
- Introduce Declarative.Handler base class. Optional, but will be required in 0.7.0 and later.

0.6.2 (2022-02-18)
------------------
- Allow setting of widget id in declarative; useful for testing.
- Allow binding of image property in declarative image (#33).
- Ensure handlers are closed properly (#50).
- Fix namespace issue.

0.6.1 (2021-12-13)
------------------
- Fix issue with spacing items in column/row widgets.

0.6.0 (2021-11-10)
------------------
- Add ability to set color/font/word_wrap on declarative UI labels.
- Enable strict typing on entire library.
- Drop support for Python 3.7, enable support for Python 3.10.
- Add methods to create persistent value models.
- Allow subclasses to override persistent value behavior.
- Configure stack widgets to expand/contract as content changes.
- Fix issue with declarative label width.
- Extend declarative components to make it easier to implement all-in-one handler+view.
- Improve handling of focus in dock widgets.
- Add divider and draw canvas items and declarative divider.
- Standardize to use a single event loop managed by Application.
- Add canvas item slider.

0.5.2 (2021-05-26)
------------------
- Fix radio button grouping issue.
- Improve font scaling behavior on Windows when running PyQt or PySide.
- Add a window.activate method.
- Expand action capabilities and be able to match key sequences.
- Add additional border color support for declarative images.
- Add icon based declarative radio buttons.
- Fix issue with lists making the selection visible.
- Remove menus from utility windows (affects Windows and Linux).
- Fix case of preference dialog when no preference panels are registered.

0.5.1 (2021-04-12)
------------------
- Default SVG now uses fastest compression rather than best (see nionswift-642).

0.5.0 (2021-03-12)
------------------
- Fix some drawing inconsistencies during splitter dragging.
- Minor improvements to drawing performance.
- Fix potential crash when closing canvas items with threads.
- Add window file path support to Window.
- Add support for directly getting last or current keyboard modifiers.
- Only change canvas item focus when no key modifiers are enabled.
- Add menu methods for adding only if enabled and checking if enabled.
- Expand action architecture to support parameters and results.
- Require sizing to be set by the canvas item (backwards incompatible).

0.4.5 (2021-02-02)
------------------
- Add color dialog support, a color well widget, and some color utility functions.

0.4.4 (2020-12-07)
------------------
- Execute context menus actions by queue to fix crashes.

0.4.3 (2020-11-13)
------------------
- Extend declarative list box to support item tool tips and context menu.
- Add mechanism to request window close from within event loop.

0.4.2 (2020-11-06)
------------------
- Add ability to determine whether a canvas item is interacting with user.
- Add ability to add actions to context menus.
- Improve look of pose dialog.

0.4.1 (2020-09-03)
------------------
- Improve capabilities of window closing workflow.
- Fix issues with file dialogs in PyQt version.

0.4.0 (2020-08-31)
------------------
- Add support for declarative pop-up window (preliminary).
- Improve key handling in list widget.
- Improve handling of slider value to avoid update cycles in multiple sliders bound to same value.
- Spacing in item-bound rows/columns now works.
- Add a declarative image widget.
- Allow custom bindings in declarative handlers.
- Allow binding to push button and check box text content.
- Add support for declarative polymorphic components using get_resource and examples.
- Add support for declarative list box.
- Add support for specifying expanding declarative items (horizontal/vertical-size-policy).
- Add show_ok_dialog and show_ok_cancel_dialog methods to application class.
- Add run_ui to application for running simple declarative windows.
- Add functions for opening file dialogs without a window.
- Add support for adjusting menus at the application level.
- Add function to truncate string to pixel width.
- Add color/font methods to eliminate need for stylesheet properties.
- Improve handling of scrolling when changing list selection.
- Add UI function to retrieve default cursor tolerance for hit testing.
- Add basic notification dialog when actions report warnings/errors.
- Consolidate default behavior (dock windows, window closing, etc.).
- Add backend support for multi-threaded section-serialized rendering.
- Add backend support for section by section drawing for improved performance.
- Add latency display capability with rolling average to backend.
- Fix drawing bugs (nested layers, startup race condition, thread shutdown).
- Introduce action architecture for declarative menus and key bindings.
- Add support for "name" keyword for declarative row and column widgets.

0.3.27 (2020-02-27)
-------------------
- Fix tool tip handling (incorrect recursive implementation caused UI hangs).
- Add support for layer caching (optimized drawing, part 1).

0.3.26 (2020-01-08)
-------------------
- Add support for dynamic tool tips in canvas items and list items.
- Change default logging level to INFO (was DEBUG).
- Add ability to register declarative components.
- Add preliminary support for PySide2 (similar to PyQt).
- Add unbind methods to complement all bind methods.

0.3.25 (2019-10-24)
-------------------
- Add icon to push button. Add binding to both push button text and icon.
- Add binding to enabled/visible/tool_tip and size properties for all declarative elements.
- Fix minor checkbox issue in PyQt.
- Improve ability to handle stacked canvas items during drag and drop.
- Extend list canvas item to support drag and drop on items.
- Fix issues with SVG 1.1 compatibility (use 'none' in place of 'transparent', opacity).
- Do not select list item if click handled in delegate mouse_pressed_in_item method.

0.3.24 (2019-06-27)
-------------------
- Fix problem clearing tasks. Add ability to clear queued tasks too.
- Fix problem leaking threads in PyCanvas in PyQt backend.
- Extend sizing policy support.
- Expand capabilities of StringListWidget. Stricter keyword arguments too.
- Implement high quality image rendering in PyQt backend.

0.3.23 (2019-04-17)
-------------------
- Fix byte ordering bug when exporting RGB data to SVG (includes complex data displays).
- Do not automatically using expanding layout when setting min-width or min-height on widget.
- Add 'expanded' property to SectionWidget for programmatic control.
- Fix issue to avoid combo box having dangling update after close.
- Fix another issue with closing dynamic components.

0.3.22 (2019-02-27)
-------------------
- Fix skewing issue drawing raster images with odd widths in pyqt UI.
- Fix issues with dynamic declarative components.
- Keep selection (by index) on combo box, if possible, when replacing items.

0.3.21 (2019-01-07)
-------------------
- Add 2 pixel margin to tree widget to avoid undesired scrolling behavior.
- Add text edit widget to declarative.
- Allow window show method to specify position and size.

0.3.20 (2018-12-11)
-------------------
- Fix issue with drawing context when writing RGB data to SVG.
- Load resources using pkgutil to be more compatible with embedding.
- Add bitmap loader based on imageio.
- Improve exception handling in pyqt callbacks to avoid crashes.

0.3.19 (2018-11-28)
-------------------
- Fix issues with line edits: returns, escapes, and editing finished events.
- Fix issue with menu items being enabled for key shortcuts.
- Add support for window level key handling.

0.3.17 (2018-11-13)
-------------------
- Add ability to specify width on declarative label, push button, combo box.
- Fix problem comparing keyboard modifiers in pyqt.
- Add text button widget.
- Fix text color in SVG.

0.3.16 (2018-07-23)
-------------------
- Python 3.7 compatibility (command launcher).

0.3.15 (2018-06-25)
-------------------
- Fix combo box initialization issue.

0.3.14 (2018-06-18)
-------------------
- Fix issue with splitters. Also add snapping to 1/3, 1/2, and 2/3 points.
- Fix bugs with PyQt backend (color maps, export image).

0.3.13 (2018-05-18)
-------------------
- Fix bugs with PyQt backend (gradients).

0.3.12 (2018-05-15)
-------------------
- DPI aware drawing code.

0.3.11 (2018-05-12)
-------------------
- Initial version online.
