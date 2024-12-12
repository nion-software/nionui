import argparse
import os
import subprocess
import sys


parser = argparse.ArgumentParser(
    prog="python -m nionui", description="Launch nionui application using native launcher or pyside6 libraries."
)

parser.add_argument(
    "app_id",
    action="store",
    help="application ID or fragment (e.g. hello_world instead of nionui_app.hello_world)",
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

parsed_args = parser.parse_args()

app_id = parsed_args.app_id

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
        # launch the app using the pyside6 qt frontend
        from nionui_app.nionswift import main
        app = main.main(list(), {"qt": None})
        app.run()
        break
    else:
        # launch using the tool frontend
        if sys.platform == "darwin":
            exe_path = os.path.join(sys.exec_prefix, "bin", "Nion UI Launcher.app", "Contents", "MacOS", "Nion UI Launcher")
        elif sys.platform == "linux":
            exe_path = os.path.join(sys.exec_prefix, "bin", "NionUILauncher", "NionUILauncher")
        elif sys.platform == "win32":
            exe_path = os.path.join(sys.exec_prefix, "Scripts", "NionUILauncher", "NionUILauncher.exe")
        else:
            exe_path = None
        if exe_path:
            python_prefix = sys.prefix
            proc = subprocess.Popen([exe_path, python_prefix, app_id], universal_newlines=True)
            proc.communicate()
            break
