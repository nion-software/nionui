# type: ignore

import importlib
import os
import pathlib
import subprocess
import sys
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
        main_fn = main_fn or load_module_as_package(args[1])
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


def main() -> None:

    # allow an explicit override of which executable is used to launch the ui (e.g. a custom
    # or debug build of nionui-tool), specified via "--executable <path>" or "--executable=<path>".
    # this is checked before attempting to auto-detect/import nionui-tool so it always takes
    # precedence.
    executable, remaining_args = extract_executable_override(sys.argv)
    if executable:
        sys.exit(subprocess.call([executable] + remaining_args[1:]))

    # first attempt to launch using nionui-launcher
    try:
        from nion.nionui_tool import command
        command.launch(sys.argv)
        return
    except ImportError:
        pass

    success = False

    # next attempt to launch using pyside6
    try:
        from PySide6 import QtCore
        success = True
    except ImportError:
        pass

    if not success:
        print("Please install 'pyside6' using pip or conda; or use nionui-tool to launch.")

    if success:
        app, error = bootstrap_main(sys.argv)

        if app:
            app.run()
        elif error:
            print("Error: " + error)


if __name__ == '__main__':
    main()
