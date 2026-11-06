# Lumen

This fork adds configurable screen mapping. Original project: [PierreSylla/Lumen](https://github.com/PierreSylla/Lumen). Licensed GPL-3.0-or-later.

Desktop control for Philips Hue lights, built for Linux/Wayland (Hyprland,
but the UI runs anywhere `pywebview`'s GTK/WebKit backend does). Everything
goes through the bridge's local API (CLIP v2): no cloud, and no
dependency on the mobile app once paired.

Three commands sharing the same configuration:

- **`hue-webui`** - the desktop app: a Vue 3 UI in a native `pywebview`
  window, with a system-tray icon.
- **`hue`** - command-line client, ideal for keyboard shortcuts.
- **`hue-sync`** - screen sync (ambilight) without the GUI.

## Features

- Bridge pairing directly in the app (auto-detection + button), dark/light
  theme, English/French UI.
- Rooms and zones as cards: group control (on/off + brightness), a colour
  wheel and brightness/white-temperature controls per lamp.
- Scenes grouped by room/zone, with a thumbnail generated from the
  scene's real colours. Create, edit and delete scenes (captures the
  current light state of every lamp in the group - the bridge requires the
  full set, not a partial capture).
- Create, edit and delete rooms and zones, from one editor. A room holds
  devices and mirrors your physical setup (a lamp lives in exactly one
  room); a zone holds individual lights and zones may overlap. Every card
  is badged `ROOM` or `ZONE` so the two never get confused.
- Screen sync / ambilight - see below, with a dedicated page (channel
  mapping preview, screen picker, colour boost, frame rate).
- Real-time updates: the UI reflects changes made elsewhere (phone, wall
  switch, another app) live, via the bridge event stream (SSE).
- System tray: open, refresh, settings, quit; closing the window minimizes
  to tray instead of exiting, so a running screen sync keeps streaming.
- Bridge settings: change the IP, re-pair, disconnect.

## Screen sync (ambilight)

Lumen averages regions of your screen and streams them to the lamps over the
Hue Entertainment API, at up to 50 frames per second.

Create an Entertainment area in the official Hue app first, then open the
Sync page (or run `hue-sync`). The original full-height horizontal mapping remains the default. Open **Edit mapping** for a bottom-band desk-strip preset, reported-coverage or equal widths, per-device direction/order, and manual rectangles per channel. Profiles are scoped to bridge, area and monitor. Optional automatic black-bar detection makes regions follow the detected picture, with an applied-boundary preview. See [screen mapping](docs/screen-mapping.md) for controls and limits.

Screen capture drives a system binary rather than a Python binding, and the
first backend that works is used:

| Backend | Needs | Notes |
|---|---|---|
| `wlroots` | `wf-recorder` | Hyprland, Sway. Fastest, never prompts. |
| `portal` | `gst-launch-1.0` (gst-plugin-pipewire), `pw-dump` | Universal: GNOME, KDE, wlroots. Asks which screen on every start. |
| `x11` | `ffmpeg` | Plain X11 sessions. |

Settings hold the screen to capture, a color boost (screen averages are
washed out; lamps need the push) and the frame rate. Screen and color boost
apply to a running sync; changing the frame rate needs a stop and start.

Pairing must have produced a `client_key` - it is the DTLS secret. Configs from
older versions may lack it, in which case re-pair once.

## Installation

**Quick install (Arch/CachyOS):**

```bash
./install.sh
```

Installs the system packages below via `pacman` (asks first), builds the UI,
installs `hue`/`hue-webui`/`hue-sync` with `pipx` (falls back to `pip
install --user`), offers the desktop launcher, and cleans up `hue-gui` if an
older install left it behind. `./install.sh -y` skips every prompt.

**Manual install**, or on another distro - requires Python >= 3.10 and
Node.js/npm (build-time only, for the UI):

```bash
# from the project directory
cd webui && npm install && npm run build && cd ..
# recommended (isolated environment)
pipx install .            
# or
pip install --user .
```

This installs `hue`, `hue-webui` and `hue-sync`.

On Arch/CachyOS, install the UI's runtime pieces from the system instead of
via pip:

```bash
sudo pacman -S python-pywebview webkit2gtk-4.1 python-gobject \
               python-pystray python-pillow libayatana-appindicator \
               nodejs npm
# run the app without installing the package
python -m huectl          
```

Screen sync needs `openssl` (already present on most systems) plus one capture
backend from the table above:

```bash
# Hyprland / Sway
sudo pacman -S wf-recorder
# any other compositor, through the desktop portal
sudo pacman -S gstreamer gst-plugin-pipewire pipewire-utils xdg-desktop-portal
```

### Launcher / autostart

Copy `packaging/lumen.desktop` into `~/.local/share/applications/`.
To start minimized to the tray at session login (Hyprland), set
`start_minimized` in Setup > Appearance, then:

```
exec-once = hue-webui
```

> The tray icon requires a tray host (Waybar's `tray` module, or your shell's
> systray). Without a host, the window simply stays visible.

## First run

```bash
hue-webui
```

On first run the pairing screen detects the bridge (or enter its IP), you press
the bridge button, then click "Pair". Keys are stored in
`~/.config/huectl/config.json` (chmod 600).

## CLI

```bash
hue discover                 # find the bridge
hue auth                     # press the bridge button
hue lights                   # list lamps
hue rooms                    # rooms and zones
hue scenes                   # scenes
hue on "Living room"         # turn a room/zone on
hue toggle "Left lamp"       # toggle a lamp
hue bri "Living room" 60     # brightness 0-100
hue bri "Living room" +10    # relative
hue color "Lamp" #ff3300     # color
hue ct "Living room" warm    # warm white (or 3000, neutral, cool)
hue scene "Relax"            # activate a scene
hue raw GET /clip/v2/resource/light   # raw API access
```

Screen sync from the terminal:

```bash
hue-sync --list              # list Entertainment areas
hue-sync                     # ambilight from the screen
hue-sync --output DP-2       # capture one monitor
hue-sync --saturation 2.0    # stronger colors
hue-sync --test              # rainbow pattern, to check the pipeline
```

Example Hyprland shortcuts:

```
bind = $mod, F1, exec, hue toggle "Living room"
bind = $mod, F2, exec, hue scene "Relax"
bind = $mod SHIFT, F1, exec, hue bri "Living room" +15
```

## Project layout

```
huectl/                Python backend + entry points
  config.py            config load/save
  bridge.py            CLIP v2 HTTP client + discovery
  i18n.py              English/French strings, shared with the UI
  cli.py               command-line interface (hue) - has its own color math,
                        no dependency on the UI or on Qt
  webapp.py            pywebview shell, JS<->Python bridge (Api class),
                        SSE/sync background threads, system tray (hue-webui)
  webui_dist/          built Vue app (generated, gitignored - see below)
  huestream.py         HueStream v2 frame protocol
  entertainment.py     Entertainment configurations and channels
  dtls_stream.py       DTLS-PSK transport over the system openssl
  capture.py           screen capture backends, region averaging
  portal.py            xdg-desktop-portal ScreenCast
  sync.py              color sources, channel mapping, hue-sync entry point

webui/                 Vue 3 UI source, built to huectl/webui_dist/ (npm run
                        build) - a sibling dist/ would sit outside the huectl
                        package and never reach an installed wheel
  src/components/      design-system pieces (cards, sheets, sliders, icons)
  src/pages/           Rooms/Zones/Scenes/Sync/Setup
  src/store/           reactive app state + all calls into Api
  src/lib/             CLIP v2 <-> view-model mapping, colour math (a JS port
                        of the same sRGB<->xy conversions the CLI itself uses)
  src/composables/     theme and i18n
```

## Technical notes

- The bridge exposes its API over HTTPS with a self-signed certificate
  (`verify=False`); authentication uses the `hue-application-key` header.
- Colors are converted in sRGB both ways (RGB<->xy) to stay faithful to the
  picked color - ported independently in the CLI (`cli.py`) and the web UI
  (`webui/src/lib/huecolor.js`), verified to agree with each other.
- A scene's actions must cover every light currently in its room/zone - the
  bridge rejects a partial list with "Light action targets not matching
  lights in referenced group" (confirmed against a real bridge). The Scene
  Editor always re-captures the full group, never a subset.
- The Philips mobile app's real product photos are not available through the
  bridge; Lumen draws its own inline-SVG icons instead.
- DTLS-PSK for Entertainment uses the system `openssl` binary, not a Python DTLS
  binding (`python-mbedtls` is unmaintained and does not build against
  Mbed TLS 3.x).
- Screen capture never grabs one frame at a time: a `grim` call costs about
  120 ms whatever the resolution, which caps it near 8 fps. Continuous streams
  are used instead, and only the newest frame is kept so the lamps cannot drift
  behind the screen. Starting sync with no explicit monitor picked on a
  multi-monitor Hyprland setup will fail the fast `wlroots` path and fall
  through to the `portal` backend instead - the UI always resolves
  "Automatic" to a real output name via `hyprctl` first to avoid that path
  entirely.
- The portal backend asks which screen to share on every start; nothing sends
  the portal's `persist_mode` option yet to suppress that (a real follow-up
  now that `portal.py` is plain GDBus.
- The `x11` capture backend is written but has not been exercised on a real X11
  session.
- WebKitGTK's DMABUF renderer can crash on load (Wayland protocol error)
  on hybrid Intel+NVIDIA setups; `hue-webui` sets
  `WEBKIT_DISABLE_DMABUF_RENDERER=1` before import to avoid it.

## Ideas for later

- A toast/error affordance for failed writes (the bridge's own transient
  "communication issues" warnings are currently swallowed silently).

## License

GNU General Public License v3.0 or later (GPL-3.0-or-later). See `LICENSE`.
