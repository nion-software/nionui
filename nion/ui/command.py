# type: ignore

import importlib
import importlib.util
import os
import pathlib
import subprocess
import sys
import sysconfig
import typing


class _MainFunctionType(typing.Protocol):
    def run(self) -> None: ...


def load_module_as_path(path: str) -> typing.Any:
    if os.path.isfile(path):
        dirname = os.path.dirname(path)
        module_name = os.path.splitext(os.path.basename(path))[0]
        sys.path.insert(0, dirname)
        module = importlib.import_module(module_name)
        return getattr(module, "main", None)
    return None


def load_module_as_package(package: str) -> typing.Optional[_MainFunctionType]:
    try:
        module = importlib.import_module(package)
        main_fn = getattr(module, "main", None)
        if main_fn:
            return typing.cast(_MainFunctionType, main_fn)
    except ImportError:
        pass
    try:
        module = importlib.import_module(package + ".main")
        main_fn = getattr(module, "main", None)
        if main_fn:
            return typing.cast(_MainFunctionType, main_fn)
    except ImportError:
        pass
    return None


def load_module_local(path: typing.Optional[typing.Union[str, pathlib.Path]] = None, name: typing.Optional[str] = None) -> typing.Optional[_MainFunctionType]:
    try:
        if path:
            sys.path.insert(0, str(path))
        module = importlib.import_module(name or "main")
        main_fn = getattr(module, "main", None)
        if main_fn:
            return typing.cast(_MainFunctionType, main_fn)
    except ImportError:
        pass
    return None


def is_path_like(app_id: str) -> bool:
    """Return True if app_id should be resolved literally as a file/directory path.

    Path-like ids (containing a path separator, ending in ".py", or referring to an existing
    file/directory) must NOT be treated as importable package fragments, since slash-form and
    dot-form app ids are not interchangeable: slash means "look for a module at this file/dir
    path", dot means "import this installed package".
    """
    return "/" in app_id or os.sep in app_id or app_id.endswith(".py") or os.path.exists(app_id)


def is_importable(package: str) -> bool:
    """Return True if package independently resolves to an importable module/package.

    Uses find_spec (rather than actually importing) to check resolvability without running the
    package's code, other than any parent packages along the dotted path, which find_spec does
    need to import to walk into their submodule_search_locations.
    """
    try:
        return importlib.util.find_spec(package) is not None
    except (ImportError, ValueError):
        return False


def normalize_app_id(app_id: typing.Optional[str]) -> typing.Optional[str]:
    """Normalize a bare package fragment app id to its full "nionui_app." package name.

    This lets a short fragment like "nionui_examples.ui_demo" be used as shorthand for the full
    "nionui_app.nionui_examples.ui_demo" package name. The "nionui_app" namespace exists so that
    apps in external packages can be discovered by a short name, but apps are not required to
    live there -- a fully qualified, independently importable package/app id (e.g. "nionswift",
    or an external "my.app.calculator") is left unchanged and is not treated as a "nionui_app"
    fragment. Only ids that do NOT already resolve on their own get the "nionui_app." shorthand
    prefix applied. Path-like app ids (see is_path_like) and None (no app id given) also pass
    through unchanged.
    """
    if app_id is None or is_path_like(app_id) or app_id.startswith("nionui_app.") or is_importable(app_id):
        return app_id
    return "nionui_app." + app_id


def normalize_app_id_in_args(args: typing.Sequence[typing.Any]) -> typing.List[typing.Any]:
    """Find the app id within a raw argument list (e.g. ["nionui", app_id, "--canvas", ...]) and
    normalize it via normalize_app_id(), leaving args[0] (a program name placeholder) and any
    "--key[=value]" flags untouched and in their original position/order.

    Used when forwarding args on to something (e.g. the native tool launcher) that does its own
    positional app id resolution, so the app id needs to be normalized in place ahead of time
    rather than via bootstrap_main directly.
    """
    args = list(args)
    positional_count = 0
    for index, arg in enumerate(args):
        if isinstance(arg, str) and arg.startswith("--") and len(arg) > 2:
            continue
        positional_count += 1
        if positional_count == 2:
            args[index] = normalize_app_id(arg)
            break
    return args


def extract_bootstrap_args(args: typing.Sequence[typing.Any]) -> typing.Tuple[typing.Dict[str, typing.Any], typing.List[typing.Any]]:
    """Pull generic "--key" / "--key=value" style flags out of args.

    "--key" (no value) becomes a boolean True entry; "--key=value" becomes a string value entry.
    Dashes in the key are converted to underscores (e.g. "--some-flag" -> "some_flag"). This lets
    new experimental bootstrap options (like "--canvas") be added and forwarded to the ui
    implementation without requiring changes here for each new flag.

    Returns the extracted flags as a dict, plus the remaining (non "--"-prefixed) args in order.
    """
    bootstrap_args: typing.Dict[str, typing.Any] = {}
    remaining: typing.List[typing.Any] = []
    for arg in args:
        if isinstance(arg, str) and arg.startswith("--") and len(arg) > 2:
            key_value = arg[2:]
            if "=" in key_value:
                key, _, value = key_value.partition("=")
            else:
                key, value = key_value, True
            bootstrap_args[key.replace("-", "_")] = value
        else:
            remaining.append(arg)
    return bootstrap_args, remaining


def bootstrap_main(args: typing.Sequence[typing.Any]) -> typing.Tuple[typing.Optional[_MainFunctionType], typing.Optional[str]]:
    """
    Main function explicitly called from the C++ code.
    Return the main application object.
    """
    version_info = sys.version_info
    if version_info.major != 3 or version_info.minor < 6:
        return None, "python36"
    # extract any "--key[=value]" style flags (e.g. the non-standard, dev/test only "--canvas"
    # flag) and forward them as bootstrap args. strip them out first so they do not interfere
    # with the normal positional argument handling (e.g. args[1] being a module path/package).
    extra_bootstrap_args, args = extract_bootstrap_args(args)
    main_fn = None
    if len(args) > 1:
        path = os.path.abspath(args[1])
        # try to load as an explicit file path, e.g. `nionui nionui_app/example/main.py`
        main_fn = load_module_as_path(path)
        # try to load as an importable package, e.g. `nionui nionui_app.nionui_examples.ui_demo`
        # (bare fragments like `nionui nionui_examples.ui_demo` are normalized to the full
        # "nionui_app." package name).
        main_fn = main_fn or load_module_as_package(normalize_app_id(args[1]))
        # try to load "main.py" from within the given directory, e.g. `nionui /path/to/some_dir`
        main_fn = main_fn or load_module_local(path)
        # try to load a module by name relative to the current working directory, e.g.
        # `nionui main` or `nionui my_module` when run from within that directory.
        module_name = os.path.splitext(os.path.basename(args[1]))[0]
        main_fn = main_fn or load_module_local(pathlib.Path.cwd(), module_name)
    if len(args) >= 0:
        # if no module was specified (or none of the above matched), try to load "main" from
        # the current working directory.
        main_fn = main_fn or load_module_local(pathlib.Path.cwd())
    if main_fn:
        bootstrap_args: typing.Dict[str, typing.Any] = {"qt": None, **extra_bootstrap_args}
        return main_fn(args, bootstrap_args), None
    return None, "main"


def extract_executable_override(args: typing.Sequence[str]) -> typing.Tuple[typing.Optional[str], typing.List[str]]:
    """Pull an explicit "--executable <path>" (or "--executable=<path>") override out of args.

    Returns the executable path (or None if not specified) and the remaining args with the
    override removed.
    """
    executable = None
    remaining: typing.List[str] = []
    index = 0
    args = list(args)
    while index < len(args):
        arg = args[index]
        if arg == "--executable" and index + 1 < len(args):
            executable = args[index + 1]
            index += 2
            continue
        if arg.startswith("--executable="):
            executable = arg[len("--executable="):]
            index += 1
            continue
        remaining.append(arg)
        index += 1
    return executable, remaining


def extract_ui_override(args: typing.Sequence[str]) -> typing.Tuple[typing.Optional[str], bool, typing.List[str]]:
    """Pull an explicit "--ui tool|qt" (or "--ui=tool|qt") and "--fallback"/"--no-fallback" out of args.

    Mirrors the frontend selection options supported by "python -m nionui" so the "nionui"
    console script can also force a specific frontend (and control whether it falls back to the
    other frontend if the requested one is unavailable) instead of always trying nionui-tool
    first, then falling back to pyside6.

    Returns the requested ui ("tool", "qt", or None if not specified), whether to fall back to
    the other frontend if the requested one is unavailable (default True), and the remaining args
    with these options removed.
    """
    ui: typing.Optional[str] = None
    fallback = True
    remaining: typing.List[str] = []
    index = 0
    args = list(args)
    while index < len(args):
        arg = args[index]
        if arg == "--ui" and index + 1 < len(args):
            ui = args[index + 1]
            index += 2
            continue
        if arg.startswith("--ui="):
            ui = arg[len("--ui="):]
            index += 1
            continue
        if arg == "--fallback":
            fallback = True
            index += 1
            continue
        if arg == "--no-fallback":
            fallback = False
            index += 1
            continue
        remaining.append(arg)
        index += 1
    return ui, fallback, remaining


def find_tool_executable() -> typing.Optional[str]:
    """Return the conventional install location of the native nionui-tool launcher for this platform.

    Returns None on unsupported platforms.
    """
    scripts_dir = sysconfig.get_paths()["scripts"]
    if sys.platform == "darwin":
        return os.path.join(scripts_dir, "Nion UI Launcher.app", "Contents", "MacOS", "Nion UI Launcher")
    elif sys.platform == "linux":
        return os.path.join(scripts_dir, "NionUILauncher", "NionUILauncher")
    elif sys.platform == "win32":
        return os.path.join(scripts_dir, "NionUILauncher", "NionUILauncher.exe")
    return None


def launch_tool(args: typing.Sequence[typing.Any], executable: typing.Optional[str] = None) -> bool:
    """Locate (or use the given override) the native nionui-tool launcher executable and run it.

    "args[1:]" (the app id and/or any extra "--key[=value]" bootstrap flags, e.g. the non-standard
    "--canvas" flag) is forwarded to the launcher unchanged; the launcher's own bootstrap.py
    extracts those flags the same way extract_bootstrap_args does here.

    Returns True if the executable was found and spawned (regardless of its exit code), or False
    if it could not be located, so callers can fall back to another ui frontend.
    """
    exe_path = executable or find_tool_executable()
    if not exe_path or not os.path.exists(exe_path):
        return False
    python_prefix = sys.prefix
    args = list(args)
    proc = subprocess.Popen([exe_path, python_prefix] + args[1:], universal_newlines=True)
    proc.communicate()
    return True


def _try_qt(args: typing.Sequence[typing.Any]) -> bool:
    try:
        from PySide6 import QtCore
    except ImportError:
        print("Please install 'pyside6' using pip or conda; or use nionui-tool to launch.")
        return False
    app, error = bootstrap_main(args)
    if app:
        app.run()
        return True
    if error:
        print("Error: " + error)
    return False


def main() -> None:

    # allow an explicit override of which executable is used to launch the ui (e.g. a custom
    # or debug build of nionui-tool), specified via "--executable <path>" or "--executable=<path>".
    # this always forces the tool launcher (regardless of "--ui"), since it is only meaningful
    # for testing a specific tool build, so it is checked before frontend selection.
    executable, remaining_args = extract_executable_override(sys.argv)
    if executable:
        if not launch_tool(normalize_app_id_in_args(remaining_args), executable=executable):
            print(f"Error: unable to launch specified executable: {executable}")
        return

    # allow an explicit override of which frontend is used ("--ui=tool" or "--ui=qt"), and
    # whether to fall back to the other frontend if the requested one is unavailable
    # ("--fallback"/"--no-fallback", default True). without "--ui", the previous default
    # behavior is preserved: try nionui-tool first, then fall back to pyside6.
    ui, fallback, remaining_args = extract_ui_override(remaining_args)

    if ui == "tool":
        if launch_tool(normalize_app_id_in_args(remaining_args)):
            return
        if fallback:
            _try_qt(remaining_args)
        else:
            print("Error: nionui-tool is not available and --no-fallback was specified.")
    elif ui == "qt":
        _try_qt(remaining_args)
    else:
        if launch_tool(normalize_app_id_in_args(remaining_args)):
            return
        if fallback:
            _try_qt(remaining_args)
        else:
            print("Error: nionui-tool is not available and --no-fallback was specified.")


if __name__ == '__main__':
    main()
