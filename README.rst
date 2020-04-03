Introduction
============
This is a UI library that can run the user interface in a browser or a
native viewer [Nion UI Launcher](https://github.com/nion-software/nionui-launcher).

It is targeted at Python 3.5.

Basic Usage (Web UI)
====================
1. Install twisted, autobahn, numpy, and scipy.
2. Clone the repository into a nion/ui subfolder.
3. Run the script ``python tools/websocket.py examples/basic/HelloWorld.py``
4. Open the URL in web browser 'http://localhost:8888/client.html'

Basic Usage (Native UI)
=======================
1. Install numpy and scipy and [Nion UI Launcher](https://github.com/nion-software/nionui-launcher).
2. Clone the repository into a nion/ui subfolder.
3. On Mac OS: ``"Nion UI Launcher.app/Contents/MacOS/Nion UI Launcher" /path/to/anaconda/ nionui/examples/basic/HelloWorld.py``
4. On Windows: ``"Nion UI Launcher.exe" /path/to/anaconda nionui/examples/basic/HelloWorld.py``
5. On Linux: ``"Nion UI Launcher" /path/to/anaconda nionui/examples/basic/HelloWorld.py``
