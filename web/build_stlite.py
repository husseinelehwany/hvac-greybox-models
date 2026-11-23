"""Package the Streamlit app (app.py) to run in the browser with stlite.

Writes two files:

  web/index.html             loads the project files by URL. Serve the REPO ROOT over HTTP
                             (e.g. `python -m http.server` from the repo root) and open
                             http://localhost:8000/web/ . Picks up code edits on reload;
                             re-run this script only when files are added or removed.

  web/dist/hvac_app.html     standalone: every Python module and EPW file is embedded, so this
                             one file can be hosted anywhere static (GitHub Pages, a shared web
                             folder, `python -m http.server` in web/dist). Re-run this script
                             after any code change.

  web/dist/open_app.bat      double-click launcher for the standalone file on Windows: starts a
  web/dist/open_app.py       local web server in web/dist and opens the app in the browser.
                             Needs Python (standard library only). On macOS/Linux run
                             `python3 open_app.py`. Share the whole web/dist folder.

Both must be served over http(s). Opening the HTML directly from disk (file://) does not work:
the browser blocks stlite's Pyodide worker and the page stays blank or stuck on "Loading Pyodide".
Both also need internet on first load (stlite, Pyodide and the Python packages come from a CDN).

Usage, from anywhere:
    python web/build_stlite.py
"""
import json
from pathlib import Path

STLITE_VERSION = "1.12.0"
REQUIREMENTS = ["numpy", "scipy", "matplotlib", "pandas"]
ENTRYPOINT = "app.py"

ROOT = Path(__file__).resolve().parent.parent
WEB = Path(__file__).resolve().parent

# What the app needs: root-level modules, packages (with their subpackages) and the weather files.
ROOT_MODULES = ["app.py"]
PACKAGES = ["hvac_greybox"]
DATA_GLOBS = ["data/weather/*.epw"]

TITLE = "Two zones with VAV boxes and AHU"

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />
  <title>{title}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@stlite/browser@{version}/build/stlite.css" />
</head>
<body>
  <div id="root"></div>
  <script type="module">
    import {{ mount }} from "https://cdn.jsdelivr.net/npm/@stlite/browser@{version}/build/stlite.js";
    const files = {files};
    mount(
      {{
        requirements: {requirements},
        entrypoint: "{entrypoint}",
        files: files,
      }},
      document.getElementById("root"),
    );
  </script>
</body>
</html>
"""


LAUNCHER_PY = '''"""Serve this folder on localhost and open the app in the browser.

Browsers block the app when hvac_app.html is opened straight from disk, so it
has to come from a (local) web server. Close this window or press Ctrl+C to stop.
"""
import functools
import http.server
import os
import threading
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = "hvac_app.html"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    handler = functools.partial(QuietHandler, directory=HERE)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)   # port 0: any free port
    url = f"http://127.0.0.1:{server.server_address[1]}/{PAGE}"
    print(f"Serving the app at {url}")
    print("The first load downloads Python and its packages, which can take a minute.")
    print("Keep this window open while you use the app. Close it or press Ctrl+C to stop.")
    threading.Timer(0.5, webbrowser.open, args=[url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
'''

LAUNCHER_BAT = """@echo off
rem Double-click to open the app: starts a local web server and opens the browser.
cd /d "%~dp0"
where py >nul 2>nul && (py open_app.py & goto :end)
where python >nul 2>nul && (python open_app.py & goto :end)
echo Python was not found. Install it from https://www.python.org/downloads/ and try again.
pause
:end
"""


def project_files():
    """Paths (relative to the repo root, POSIX style) of every file the app needs."""
    paths = [ROOT / m for m in ROOT_MODULES]
    for pkg in PACKAGES:
        paths += sorted((ROOT / pkg).rglob("*.py"))   # includes subpackages
    for pattern in DATA_GLOBS:
        paths += sorted(ROOT.glob(pattern))
    missing = [p for p in paths if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"missing project files: {missing}")
    return [p.relative_to(ROOT).as_posix() for p in paths]


def js_literal(obj):
    """JSON for embedding inside a <script> tag (a literal '</' would end the tag)."""
    return json.dumps(obj, ensure_ascii=False, indent=2).replace("</", "<\\/")


def page(files):
    return PAGE.format(title=TITLE, version=STLITE_VERSION, files=js_literal(files),
                       requirements=json.dumps(REQUIREMENTS), entrypoint=ENTRYPOINT)


def main():
    paths = project_files()

    # served: index.html is in web/, so the project files are one level up
    served = {p: {"url": f"../{p}"} for p in paths}
    (WEB / "index.html").write_text(page(served), encoding="utf-8")

    # standalone: embed the file contents as text
    embedded = {p: (ROOT / p).read_text(encoding="utf-8") for p in paths}
    dist = WEB / "dist"
    dist.mkdir(exist_ok=True)
    out = dist / "hvac_app.html"
    out.write_text(page(embedded), encoding="utf-8")
    (dist / "open_app.py").write_text(LAUNCHER_PY, encoding="utf-8")
    (dist / "open_app.bat").write_bytes(LAUNCHER_BAT.replace("\n", "\r\n").encode("ascii"))

    print(f"{len(paths)} files packaged")
    print(f"  served:     {(WEB / 'index.html').relative_to(ROOT)}")
    print(f"  standalone: {out.relative_to(ROOT)} ({out.stat().st_size / 1e6:.1f} MB)")
    print(f"  launcher:   {(dist / 'open_app.bat').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
