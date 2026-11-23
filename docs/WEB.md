# Running the app in a browser (stlite)

The Streamlit app (`app.py`) can run entirely inside a web browser, with no Python server running the model. This uses [stlite](https://github.com/whitphx/stlite), which runs Streamlit on [Pyodide](https://pyodide.org) (Python compiled to WebAssembly). The simulation, plots and tables are all computed in the browser tab, on the user's own computer.

## Files

Everything for the browser version is in `web/`. No other project files are changed by it.

| File | What it is |
|---|---|
| `web/build_stlite.py` | Build script. Run `python web/build_stlite.py` from anywhere to regenerate the files below. |
| `web/index.html` | **Server version.** Loads the project files by URL, so code edits show up on a browser reload. |
| `web/dist/hvac_app.html` | **Standalone version.** One file (about 10 MB) with all Python modules and EPW weather files embedded. |
| `web/dist/open_app.bat`, `web/dist/open_app.py` | Double-click launcher for the standalone version. |

`web/dist/` is build output and is ignored by git. Re-run the build script to recreate it.

When to re-run the build (`python web/build_stlite.py`):

- server version: only when a module or EPW file is added or removed
- standalone version: after any code change

## Running the server version (development)

From the repository root, in cmd:

```
python -m http.server --bind 127.0.0.1
```

Then open http://localhost:8000/web/ in browser.

`--bind 127.0.0.1` keeps the server private to your computer. Without it, `http.server` listens on all network interfaces, and other devices on the same network could browse the repository folder while it runs.

## Running the standalone version (the launcher)

Double-click `web/dist/open_app.bat`.

- `open_app.bat` changes to its own folder, looks for Python (`py`, then `python`) and runs `open_app.py`. If Python is missing it says so and waits.
- `open_app.py` starts a web server for that folder:
  - on `127.0.0.1` only, so only this computer can reach it
  - on any free port, so it never clashes with something else
  - then opens the default browser at `http://127.0.0.1:<port>/hvac_app.html`

Keep the console window open while using the app. Closing it or pressing Ctrl+C stops the server.

On macOS or Linux, run `python3 open_app.py` instead of the `.bat`.

## How it runs

```
Browser ──► local web server   index.html (or hvac_app.html), your .py and .epw files
Browser ──► cdn.jsdelivr.net   stlite, the JavaScript that hosts Streamlit
Browser ──► Pyodide CDN        Python itself, plus numpy, scipy, matplotlib, pandas
```

Inside the browser tab:

1. stlite starts Python (Pyodide) in a background worker.
2. It copies the project files into an in-memory file system that exists only in that tab.
3. It runs `app.py` with Streamlit. Inputs, simulation and plots then work as in the normal app.

The only internet access is to the two CDNs, on first load. GitHub is not involved, and the project code and weather files are not uploaded anywhere: they go from the local disk, through the local server, to the browser. The first load takes about a minute while Python and the packages download. After that the browser caches them.

## Why a web server is needed

Browsers block stlite's Python engine when an HTML file is opened straight from disk (`file://...`): the page stays blank or stuck on "Loading Pyodide". Serving the same file over `http://` makes the browser treat it as a normal website and everything works.

The server only hands files to the browser. It never runs the project's Python code. Python's built-in `http.server` is enough. It is part of the standard library (for example `...\Python39\lib\http\server.py`), so nothing extra needs installing.

## Sharing the project

**For someone who only uses the app**, send the `web/dist` folder (`hvac_app.html`, `open_app.bat`, `open_app.py`). Re-run the build first so it has the latest code. They need:

- Python installed, with no packages
- internet on the first load

Alternatively, host `hvac_app.html` on any static web host (GitHub Pages, an intranet site) and share the link. Then they need only a browser.

**For someone who runs or edits the code**, share the repository, with all files committed. They install the packages with `pip install -r requirements.txt` and run either `python main.py` or `streamlit run app.py`. They don't need `__pycache__/`, `web/dist/` or `TODO.txt`.

## Limits

- Speed: Python in the browser is several times slower than native Python for this kind of step-by-step simulation. Runs of a week or two are quick, a month of 15-minute steps takes noticeably longer, and a full year would be slow.
- Versions: stlite is pinned to `@stlite/browser@1.12.0` in `web/build_stlite.py`. It runs a much newer Streamlit than the local install. The app works on both.
- Offline use: the browser needs internet on first load for the CDN downloads. A fully offline desktop app is possible with `@stlite/desktop` (Electron), but that needs Node.js and is not set up here.
