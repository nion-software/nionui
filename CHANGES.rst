Changelog (nionui)
==================

0.3.26 (UNRELEASED)
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
