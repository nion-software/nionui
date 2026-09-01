# Introduction
This is a Python UI library that can run with a pyside6 or nionui-tool backend.

# Installation
Install this library using pip or conda.

```
pip install nionui
```

Install using PySide6 or nionui-tool backend.

```
pip install nionui-tool
```

```
pip install pyside6
```

# Usage
This UI library supports an application.

To run the example application, use the following command with the appropriate application identifier. It will launch using either the nionui-tool or pyside6 backend, depending on which is installed. If both are installed, it will use the nionui-tool.

```
nionui <application_identifier>
```

`nionui` is installed as a command (e.g. via `pip install nionui`), so it can be run directly as
shown above. It is equivalent to `python -m nionui`, which is also always available and is useful
when you want to be explicit about which Python environment/interpreter is being used.

To run the UI demo app, use the following command (application identifier is 'nionui_examples.ui_demo'):

```
nionui nionui_examples.ui_demo
```

To run the Canvas demo app, use the following command (application identifier is 'nionui_examples.canvas_demo'):

```
nionui nionui_examples.canvas_demo
```

To run Nion Swift, use the following command (application identifier is 'nionswift'):

```
nionui nionswift
```

The `nionui_app` namespace also exists so that apps in external packages/repos can be discovered
by a short name (e.g. `nionui_examples.ui_demo`), and apps do not need to live there at all -- a
fully qualified, independently importable package (e.g. `my.app.calculator`) can be used directly
as the application identifier without any prefix. Use `--list` to see the apps currently
discoverable under the `nionui_app` namespace:

```
nionui --list
```

The remaining sections below use `nionui` for their examples; `python -m nionui` works identically
in every case shown.

## Choosing a UI frontend
By default, `nionui` prefers the native `nionui-tool` launcher (`--ui=tool`) and falls back
to the pyside6-based frontend (`--ui=qt`) if the tool launcher is unavailable. Use `--ui` to
force a specific frontend, and `--no-fallback` to disable falling back to the other frontend if
the requested one is unavailable.

```
# force the native tool launcher, without falling back to pyside6
nionui --ui=tool --no-fallback nionswift

# force the pure-Python pyside6 frontend, without falling back to the tool launcher
nionui --ui=qt --no-fallback nionswift
```

## Canvas UI (experimental)
The `--canvas` flag is a non-standard flag intended for development and testing only. It layers
the canvas-based user interface implementation on top of the Qt (or tool) user interface, which is
useful for exercising canvas-based rendering without switching applications.

```
nionui --canvas nionswift
```

## Overriding the tool launcher executable
When developing or debugging `nionui-tool` itself (for example, a custom Xcode or CMake build),
use `--executable` to point at a specific launcher binary instead of the one installed alongside
the active Python environment.

```
nionui --executable "/path/to/Nion UI Launcher.app/Contents/MacOS/Nion UI Launcher" nionswift
```

## Running a local `main` module
`nionui` can also launch an application directly from a directory containing a `main.py`,
without it being an installed/importable package. Pass a path (containing a "/", or ending in
".py") to look for `main` at that location, or omit the application identifier entirely to look
for `main` in the current directory.

```
# look for main.py at a specific path
nionui nionui_app/nionui_examples/hello_world

# look for main.py in the current directory
cd nionui_app/nionui_examples/hello_world
nionui
```
