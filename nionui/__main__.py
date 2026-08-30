import argparse
import os
import subprocess
import sys


parser = argparse.ArgumentParser(
    prog="python -m nionui",
    description="Launch nionui application using native launcher or pyside6 libraries.",
    epilog="Any additional unrecognized \"--key\" or \"--key=value\" flags (e.g. the non-standard, "
           "dev/test only \"--canvas\" flag) are forwarded through to the ui bootstrap as generic "
           "bootstrap args, without needing to be declared here.",
)

parser.add_argument(
    "app_id",
    nargs="?",
    action="store",
    default=None,
    help="application ID, path, or fragment (e.g. hello_world instead of nionui_app.hello_world). "
         "if omitted, looks for a 'main' module in the current directory.",
)

parser.add_argument(
    "--ui",
    dest="ui",
    action="store",
    choices=["tool", "qt"],
    help="choose UI frontend",
    default="tool",
)

parser.add_argument(
    "--fallback",
    dest="fallback",
    action=argparse.BooleanOptionalAction,
    help="whether to fall back to other UI frontend if preferred choice is unavailable",
    default=True,
)

parser.add_argument(
    "--executable",
    dest="executable",
    action="store",
    help="override the path to the native UI launcher executable (used when --ui=tool)",
    default=None,
)

parsed_args, extra_args = parser.parse_known_args()

app_id = parsed_args.app_id

# path-like app ids (containing a path separator, ending in .py, or referring to an existing
# file/directory) are resolved literally by bootstrap_main's path-based loading (including the
# "look for main in this directory" fallback) -- they are NOT package fragments and must not be
# prefixed with "nionui_app.". Only bare package fragments get that treatment. if app_id was
# omitted entirely, leave it as None so bootstrap_main falls through to its "look for main in
# the current working directory" fallback.
if app_id is not None:
    is_path_like = "/" in app_id or os.sep in app_id or app_id.endswith(".py") or os.path.exists(app_id)
    if not is_path_like:
        app_id = "nionui_app." + app_id if not app_id.startswith("nionui_app.") else app_id

order = list[str]()

if parsed_args.ui:
    order.append(parsed_args.ui)

# if using fallback, add tool and qt to order if not already present.
if parsed_args.fallback:
    if "tool" not in order:
        order.append("tool")
    if "qt" not in order:
        order.append("qt")

# go through the ui preferences in order
for ui in order:
    if ui == "qt":
        # launch the app using the pyside6 qt frontend, resolving app_id the same way
        # bootstrap_main does (explicit path, package import, local "main" module, or -- if
        # app_id was omitted -- "main" in the current working directory).
        from nion.ui import command as ui_command
        bootstrap_argv = ["python -m nionui"]
        if app_id is not None:
            bootstrap_argv.append(app_id)
        bootstrap_argv += extra_args
        app, error = ui_command.bootstrap_main(bootstrap_argv)
        if app is None:
            print(f"Unable to launch '{app_id or '.'}' using qt frontend: {error}")
            continue
        app.run()
        break
    else:
        # launch using the tool frontend, or an explicitly overridden executable if provided.
        if parsed_args.executable:
            exe_path = parsed_args.executable
        elif sys.platform == "darwin":
            exe_path = os.path.join(sys.exec_prefix, "bin", "Nion UI Launcher.app", "Contents", "MacOS", "Nion UI Launcher")
        elif sys.platform == "linux":
            exe_path = os.path.join(sys.exec_prefix, "bin", "NionUILauncher", "NionUILauncher")
        elif sys.platform == "win32":
            exe_path = os.path.join(sys.exec_prefix, "Scripts", "NionUILauncher", "NionUILauncher.exe")
        else:
            exe_path = None
        if exe_path and not os.path.exists(exe_path):
            print(f"Tool launcher executable not found, skipping: {exe_path}")
            exe_path = None
        if exe_path:
            python_prefix = sys.prefix
            # forward any unrecognized "--key[=value]" flags (e.g. "--canvas") through to the
            # native launcher's bootstrap.py, which extracts them the same way. omit app_id
            # entirely if it wasn't specified, so bootstrap.py falls through to its "look for
            # main in the current working directory" fallback.
            launch_args = [exe_path, python_prefix]
            if app_id is not None:
                launch_args.append(app_id)
            launch_args += extra_args
            proc = subprocess.Popen(launch_args, universal_newlines=True)
            proc.communicate()
            break
else:
    print(f"Unable to launch (tried: {', '.join(order)}). Please install 'nionui-tool' (for --ui=tool) or "
          f"'pyside6' (for --ui=qt), or pass a valid --executable path.")
