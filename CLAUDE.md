# CLAUDE.md

Guidance for AI assistants (and humans) working on **Lumen**, a desktop
controller for Philips Hue lights. Read this before making changes.

## What this project is

Lumen controls Philips Hue lights from the Linux desktop (built for
Wayland/Hyprland, the UI runs anywhere `pywebview`'s GTK/WebKit backend does).
Everything goes through the bridge's **local CLIP v2 API** - no cloud, no
dependency on the mobile app once paired.

The UI used to be a PySide6/Qt desktop app; it has been rebuilt as a **Vue 3**
frontend running inside a native `pywebview` window (GTK/WebKit, not
QtWebEngine - there is no Qt UI code left in this project). The Python backend
(bridge access, colour math, Entertainment streaming) is unchanged in spirit;
only its consumer changed.

Three entry points, all sharing one config file:
- `hue-webui` - the desktop app (`huectl.webapp:main`): Vue 3 UI + pywebview
  shell + system tray.
- `hue` - command-line client (`huectl.cli:main`).
- `hue-sync` - screen-sync / Entertainment streaming (`huectl.sync:main`).

Language: Python >= 3.10 (backend) + Vue 3/Vite (frontend, built to
`huectl/webui_dist/` and bundled - no Node/npm at runtime). HTTP: `requests`.
License: **GPL-3.0-or-later**.

## Architecture

### Backend (package `huectl/`)

| Module | Responsibility |
|---|---|
| `config.py` | `CONFIG_PATH`, `APP_NAME`, `load_config` / `save_config` (chmod 600) |
| `bridge.py` | `Bridge` (CLIP v2 HTTP: get/put/post/delete/snapshot), `discover_bridge_ip`, `load_bridge` |
| `i18n.py` | `STRINGS` (en/fr), `t(key, **kw)` - shared source of truth, exposed to the UI via `Api.get_strings()` |
| `cli.py` | `hue` command - has its **own** `hex_to_xy`, deliberately not importing anything Qt-coupled |
| `webapp.py` | pywebview entry point: `Api` (JS<->Python bridge), `WebSSE`, `WebSync`, pairing worker, tray (`_setup_tray`), single-instance lock |
| `huestream.py` | HueStream v2 frame protocol (Entertainment) |
| `entertainment.py` | CLIP-side Entertainment control (configs, channels, start/stop) |
| `dtls_stream.py` | `HueDTLS` - DTLS-PSK transport via the system `openssl` binary |
| `capture.py` | `FrameStream` (raw RGB from a system binary), `region_average`, `punch`, wlroots/x11 backends |
| `portal.py` | `PortalSession` - xdg-desktop-portal ScreenCast over QtDBus, feeding `gst-launch pipewiresrc`. **The only reason PySide6 is still a dependency** - no GUI needs it anymore |
| `sync.py` | `ColorSource`, `TestColorSource`, `ScreenCapture`, `channel_regions`, `run_stream`, `hue-sync` |

`window.py`, `widgets.py`, `dialogs.py`, `setup_window.py`, `theme.py`,
`icons.py`, `workers.py`, `sse.py`, `app.py`, `color.py` were the PySide6 GUI
and are **gone**. If you find a reference to `hue-gui` or `huectl.app` in an
old doc/issue, it predates the migration.

### Frontend (`webui/`, Vue 3 + Vite, builds to `huectl/webui_dist/`)

`webui/vite.config.js` sets `build.outDir` to `../huectl/webui_dist`
deliberately - a sibling `webui/dist/` sits outside the `huectl` package
and is invisible to a `pip`/`pipx install .` entirely (setuptools only
packages what's declared under the package it's told about; confirmed by a
real install producing a `huectl` with no built UI next to it at all). See
`pyproject.toml`'s `[tool.setuptools.package-data]`.

| Path | Responsibility |
|---|---|
| `src/App.vue` | top-level: pairing screen vs. main shell, sheet routing |
| `src/components/` | `NavRail`, `PageHeader`, `CardShell` (room/zone card), `LampRow`, `SceneTile`, `LampSheet` (colour wheel), `GroupEditorSheet`, `SceneEditorSheet`, `PairingScreen`, `icons/Icon.vue` (inline SVG registry) |
| `src/pages/` | `GroupsPage` (Rooms and Zones - same component, filtered data), `ScenesPage`, `SyncPage`, `SetupPage` |
| `src/store/index.js` | single reactive store (plain Vue reactivity, no Pinia) - all `window.pywebview.api.*` calls live here, nowhere else |
| `src/lib/` | `snapshot.js` (raw CLIP v2 -> view-model, ports `window.py`'s old membership logic), `huecolor.js` (xy/mirek<->sRGB, a JS port of the CLI's own colour math), `colors.js` (UI-only derived colours: dimming, tinting, HSV wheel) |
| `src/composables/` | `useTheme.js` (dark/light, localStorage), `useI18n.js` (loads `huectl/i18n.py`'s strings once via `Api.get_strings()`) |

Root: `pyproject.toml`, `README.md`, `LICENSE` (GPLv3),
`packaging/lumen.desktop`, `packaging/lumen-webui.spec` (PyInstaller, Linux).

## Config file

`~/.config/huectl/config.json`, shared by CLI + UI, written chmod 600. Keys:
`bridge_ip`, `app_key` (CLIP application key = DTLS PSK identity),
`client_key` (hex; DTLS PSK secret, from pairing), `columns`, `language`,
`start_minimized`, and for screen sync `sync_output` (monitor name, empty =
whole desktop), `sync_saturation`, `sync_fps`, `sync_area_id` and `sync_mapping` (validated per-bridge/area/output profiles).
See `docs/screen-mapping.md` and `huectl/mapping.py`; do not bypass the shared geometry validation.

## Conventions and hard rules

- **No Unicode symbol glyphs in the *Python* layer or CLI output** (still
  matters if you ever touch a terminal-facing message). Inside the Vue UI
  this constraint is explicitly lifted - see `redesign/README.md` - a
  browser always has glyph coverage a minimal-font Wayland session didn't;
  icons there are inline SVG (`webui/src/components/icons/Icon.vue`) by
  design-system choice, not font-safety necessity.
- **Networking never runs on the UI thread.** For the web UI this is true by
  construction: `js_api` calls are served over pywebview's own local
  threaded HTTP server (confirmed by reading its source, see
  `handoff.md`), never the GTK main loop. Long-running work (SSE, screen
  sync, pairing) is its own daemon `threading.Thread` in `webapp.py`
  (`WebSSE`, `WebSync`, the pairing worker), pushing results into the page
  with `window.evaluate_js(...)` calling a registered `window.__lumenXxx`
  hook - never touch DOM/JS state synchronously from those threads.
- **Colors use sRGB in both directions.** `rgb_to_xy`/`xyToHex` must stay a
  matched pair (sRGB matrix + inverse) or picked colors won't match what the
  lamp shows. This now exists in **two** independent places - `cli.py`'s
  `hex_to_xy` and `webui/src/lib/huecolor.js` - keep both matched; don't
  reintroduce the Wide-RGB bug in either. `huecolor.js` also matches
  Python's `int()` **truncation**, not rounding, in its final byte
  conversion - a `Math.round` there was found to be silently off-by-one
  against the reference whites (see `redesign/README.md`'s hex table).
- **English is the default UI language**; French is optional. All Vue
  user-facing strings go through `useI18n().t(key, params)`, backed by
  `huectl/i18n.py`'s `STRINGS` (both languages must have exactly the same
  key set - `set(STRINGS["en"]) == set(STRINGS["fr"])` is a real, checked
  invariant, not just style). Never use — or emoji in comments.
- **Code, comments, docstrings, README are English.** Hyphens `-`, not em-dashes.
- **Keep it prose-light and dependency-light.** New JS dependency? Check
  whether a couple dozen lines of plain Vue/CSS does it first (this is why
  there's no Pinia, no vue-i18n, no icon library). New Python dependency?
  Same scrutiny - `pywebview`, `pystray`+`pillow` were added deliberately
  and narrowly for the migration; `PySide6` survives only for
  `portal.py`'s QtDBus fallback.

## UI behavior worth knowing

- Rooms and zones are rendered as cards (`CardShell.vue`). **Scenes are
  grouped under their room/zone** (via `scene.group`, carried through as
  `groupId`/`groupKind` on the scene view-model). Orphan scenes/lights fall
  into "Others" / "Other scenes" (`lib/snapshot.js`).
- **Rooms and zones are both create/edit/delete in-app**, through one
  `GroupEditorSheet` and the store's `saveGroup`/`deleteGroup`. They differ
  only in membership: a **room holds devices** (`children[].rtype ==
  "device"`, and the bridge allows a device in exactly one room), a **zone
  holds lights** (`rtype == "light"`, zones may overlap). The editor always
  works in terms of *lights* (what a person picks), and `Api.save_group`
  resolves each selected light to its owning device id for a room - never
  send light ids as a room's children.
- **A scene's actions must cover every light currently in its group, not a
  subset** - confirmed against a real bridge: a partial action list is
  rejected with "Light action targets not matching lights in referenced
  group". `Api.save_scene` always re-derives the full light set of the
  scene's group and captures all of them; there is no per-lamp picker in
  `SceneEditorSheet` by design, matching this constraint exactly.
- `LampRow` background = the light's real color at reduced alpha; clicking a
  lamp's name opens `LampSheet` (colour wheel + brightness + white
  swatches). The on/off control is `ToggleSwitch.vue`.
- Recalling a scene triggers `recall_scene`, then a snapshot reload ~600ms
  later (the bridge applies scene changes asynchronously).
- SSE (`WebSSE` in `webapp.py`, pushed via `evaluate_js`) reflects external
  changes live: light `update` fragments patch **only the changed CLIP v2
  keys** (`on`/`dimming`/`color`/`color_temperature`) onto the matching lamp
  in place; `add`/`delete` events debounce a full snapshot reload (700ms,
  single-shot, restarted on each event - matches the old Qt app's timer
  exactly). `WebSSE` re-reads `load_bridge()` on every reconnect attempt
  rather than binding to a fixed `Bridge`, so it survives (and starts
  correctly after) a first-run pairing, disconnect, or re-pair within the
  same process.
- The Sync page's primary button runs `WebSync` (a daemon thread wrapping
  `sync.run_stream` unmodified); stopping sets a `threading.Event` the loop
  checks. Changing the monitor or colour boost while running calls
  `set_output`/`set_saturation` on the live `ScreenCapture` (a plain
  attribute write the sampling thread picks up on its next frame, so the
  Hue stream never blinks); changing fps requires a stop/start, matching
  the underlying `run_stream(..., fps=...)` contract.
- `WebSync` always resolves "Automatic" screen capture to a concrete
  monitor name via `hyprctl` before starting - **never pass `output=None`
  through to `ScreenCapture` from the web UI**. On a multi-monitor Hyprland
  setup that makes the `wlroots` backend fail outright (it refuses to start
  without an explicit output), which falls through to the `portal` backend
  - and `portal.py` needs a running `QGuiApplication`/D-Bus loop that this
  Qt-less process never has, so the fallback **hangs forever** instead of
  failing cleanly. Confirmed by hand; see `handoff.md`.
- The mapping editor uses draft/apply/cancel, normalized rectangles and shared Python validation. All JS API calls remain in the store. Capture and protocol changes need failure-path tests and real GTK screenshots. GUI/CLI/Identify share a file lock; never bypass it. Monitor and area changes now require stop/start to preserve profile identity.
- `pywebview` populates `window.pywebview` before `window.pywebview.api` is
  actually attached, and on this GTK backend the `'pywebviewready'` event
  itself has fired before `.api` was ready too. Any one-shot code that needs
  the API on mount (not just the store's own retrying calls) must `await
  apiReady()` (`store/index.js`) first - two separate screens shipped with
  this race before it was caught by screenshotting the *actual* rendered
  values, not just checking the build succeeded.

## Screen sync / DTLS (important decision)

- **Do not use `python-mbedtls`.** It's unmaintained and won't build against
  Mbed TLS 3.x (Arch and most modern distros) or recent Python.
- The DTLS-PSK transport (`dtls_stream.HueDTLS`) drives the **system `openssl`**:
  `openssl s_client -dtls1_2 -connect <ip>:2100 -cipher PSK-AES128-GCM-SHA256
  -psk <client_key_hex> -psk_identity <app_key> -ign_eof`.
  - `-ign_eof` keeps stdin **binary-safe** (disables s_client R/Q command parsing;
    otherwise a `0x0a` byte in color data could trigger it).
  - Handshake success is detected by the negotiated cipher name appearing in
    output; failure by `Cipher is (NONE)`. Other lines (`SSL-Session:`,
    `handshake has read`) print even on failure - don't use them as markers.
- Frame format lives in `huestream.py` (52-byte header + 7 bytes/channel,
  16-bit color). Entertainment configuration control in `entertainment.py`.

## Screen capture (ambilight)

- Same principle as DTLS: **drive a system binary**, no Python bindings. A
  backend is a command writing raw RGB frames to stdout, plus its bytes/pixel.
- **Never grab one frame per frame.** `grim` costs ~120 ms per call (process
  spawn + compositor round trip, barely affected by scale), so it caps at ~8
  fps. `wf-recorder` piping `rawvideo` holds a measured 30 fps. Continuous
  streams only.
- `FrameStream` keeps **only the newest frame**. Queueing would make the lamps
  drift further behind the screen every second.
- Backends: `wlroots` (wf-recorder, Hyprland/Sway, no dialog), `portal`
  (universal: GNOME/KDE/wlroots), `x11` (ffmpeg x11grab).
- `capture.py`'s own `default_output()` needs a running `QGuiApplication` (the
  old Qt GUI supplied one) - it silently returns `None` otherwise, which is
  exactly why `webapp.py` has its **own** `_default_output()` based on
  `hyprctl monitors -j`, and why `WebSync` always resolves a concrete output
  before calling into `sync.py`/`capture.py`. See "UI behavior worth
  knowing" above for the failure mode this avoids.
- **PySide6 QtDBus quirks**, both worked around in `portal.py`: `a{sv}` comes
  back as an opaque `QDBusArgument` whose `asVariant()` is broken, so Response
  slots must be declared `(uint, QVariantMap)` and connected as
  `"1handle(uint,QVariantMap)"` (the `1` is what the `SLOT()` macro adds);
  and Python ints marshal as `i` while the portal demands `u`, so every uint
  option is omitted and its default used. `session_handle` comes back a string
  but must be re-typed `QDBusObjectPath` for every later call.
- Legacy mapping uses x only and remains the default. Configured mappings use the shared topology/region engine in `mapping.py`. Keep channel wire order separate from physical ordering. Discovery and validation stay outside the frame loop.

## Build / run / test

```bash
# run without installing
cd webui && npm install && npm run build && cd ..
python -m huectl              # web UI (equivalent to hue-webui)
python -m huectl.cli ...      # CLI
python -m huectl.sync ...     # sync

# frontend dev loop (hot reload) - point webapp.py at the Vite dev server
cd webui && npm run dev &
LUMEN_WEBUI_DEV_URL=http://localhost:5173 python -m huectl.webapp

# install (creates hue / hue-webui / hue-sync)
pipx install .                # or: pip install --user .
# Arch: sudo pacman -S python-pywebview webkit2gtk-4.1 python-gobject \
#                      python-pystray python-pillow libayatana-appindicator

# package hue-webui as a standalone binary (dev-only tool, see pyproject.toml's dev extra)
python -m venv --system-site-packages /tmp/build-venv && source /tmp/build-venv/bin/activate
pip install pyinstaller
pyinstaller packaging/lumen-webui.spec   # -> dist/hue-webui/
```

Check first whether the session has a **real bridge and a live Wayland session**
- on the maintainer's machine it does, and `load_bridge()` plus
`grim`/`hyprctl` work directly, which beats any fake. Read-only GETs are
free; for writes, create a throwaway resource and delete it in the same
script (this project's history includes real bugs - the scene-action rule
above, the `_default_output()` hang, an `apiReady()` race - that only a
live bridge and a real launched window ever surfaced; a passing headless
build proves nothing about them). Otherwise, headless:

- `python -m compileall -q huectl` to catch syntax errors.
- `cd webui && npm run build` to catch Vue/JS build errors.
- Import all `huectl` modules normally (nothing left imports Qt at module
  level except `portal.py`, which is only ever imported lazily from inside
  `capture.py`'s fallback path).
- Cross-check `huectl/i18n.py`'s two language dicts have identical key sets
  before trusting a new string - a typo'd key silently falls back to
  English at runtime rather than erroring.
- Protocol/logic is unit-testable without a bridge: `huestream.build_frame`
  (assert exact bytes), `entertainment` parsing, `dtls_stream.HueDTLS._cmd()`
  and its fast-fail against a dead port.

When changing the UI, **actually launch `hue-webui` and screenshot the real
window** (`grim -g "<geometry>"`, from `hyprctl clients -j`) before declaring
it done - this repo's own history (see `handoff.md`) is full of bugs (a
pywebview readiness race, wrong lamp icons from exact- vs substring-matching
archetypes, a stale "first card expanded" id after the sample-data-to-real
swap) that a clean build and a code read both missed and a real screenshot
caught immediately. A background-launched window shares the real desktop -
don't leave it sitting under wherever the mouse actually is, and kill it
promptly after capturing.

## Gotchas

- Missing `client_key` in an old config -> re-pair the bridge (needed for sync).
- Room and zone creation both send `metadata.archetype = "other"` (valid for both).
- Room children are **devices**, zone children are **lights** - the same lamp has
  a different id in each list. `snapshot()` therefore fetches `device` too.
  `Api.save_group`/`Api.get_channel_names` both do the light-id -> device-id
  join server-side; don't push a light id into a room's `children` directly.
- Some lights only report `color_temperature` (white ambiance) - handle both
  `color.xy` and `color_temperature.mirek` everywhere colors are read (both
  `cli.py` and `lib/huecolor.js` do).
- A scene action fragment from SSE, or a partial CLIP v2 update, carries only
  the keys that changed - patch exactly those onto a lamp/light, never
  overwrite the others (an unrelated `dimming`-only fragment must not
  clobber a still-valid derived colour).
- `pywebview`'s Linux tray (`pystray`'s AppIndicator backend) shares the
  process's GTK/GLib main loop rather than running its own - use
  `icon.run_detached()`, call it before `webview.start()`, and never call
  `icon.run()` (which spins its own loop and expects to own the main
  thread).
