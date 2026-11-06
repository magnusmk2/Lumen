# Screen mapping

Lumen 0.9 adds configurable sampling regions to the existing Sync page. The original full-height horizontal mapping remains the default until you apply another layout.

## Desk-strip setup

1. Select your Entertainment area and the screen to capture.
2. Open **Edit mapping**, then choose **Desk strip (bottom band)**.
3. Start with Band height 20% and Bottom inset 0%.
4. Choose Reported coverage or Equal widths for each device.
5. Click Apply, then Start screen sync.

Reported coverage uses the lengths of the Entertainment segments referenced by each channel. It does not assume that every channel occupies one third of the strip, and it does not use the number of physical LEDs or gradient palette points as the channel count. If the bridge does not report complete, contiguous coverage, start with equal widths and adjust manually.

A source's metadata cannot prove the visible physical lengths or which end is on the left. Use Identify segment while sync is stopped to check direction. This briefly changes the area lights at low brightness; it does not guarantee restoration of their previous state. Reverse direction or reorder channels if necessary.

The region diagram shows where colours are sampled. Its outlines match the effective rectangles; the swatches below the main diagram show sampled output colours when syncing. It is not a screenshot. On Hyprland the diagram uses the monitor aspect ratio, including rotation, with its display size constrained so portrait screens do not hide all the controls.

## Manual controls

Select a channel using its region label, channel row or selector. Set Left, Top, Width and Height as percentages of the captured screen. Editing any field makes that channel Manual. You can also drag a rectangle to move it; the numeric fields remain the precise and keyboard-accessible method of changing its size.

Manual rectangles can overlap or leave gaps. Reset this channel removes only its manual override. Reset this device restores its inferred order/width settings and removes its channels' manual rectangles. Reset all creates a new desk-strip draft. Resets and all other edits remain drafts until Apply; Cancel and Escape discard them.

Changing automatic band settings does not move manually overridden rectangles. Their coordinates are absolute percentages of the captured screen. This keeps manual calibration predictable.

Use Layout for this device to retain full-height sampling on other lights while the desk strip follows the bottom band. Each device can follow the whole screen band or a subsection using Screen range start/end. Multiple strips are treated separately. A channel shared by more than one source requires an explicit manual rectangle because its members receive one shared colour. Independent rectangles cannot create new independently addressable outputs.

Changes can be applied while ordinary screen sync is running. The worker swaps the complete region set between frames without restarting capture or DTLS. Area and monitor changes require stopping sync first. Source discovery is not repeated for each frame or keystroke.

## Saved profiles and refresh

Profiles are keyed by bridge identity, Entertainment area and monitor. Geometry is normalized, so resolution changes preserve the intended proportions. Manual overrides and automatic device settings are stored separately.

Refresh reads the bridge again. If channel membership, segment geometry or relevant source placement changes, Lumen flags the mapping for review rather than silently replacing it. Keep compatible manual regions explicitly rebinds retained channel rectangles to the new topology; verify the affected channels before Apply. Reset all is the alternative. A display-name change alone does not discard a profile.

Concurrent stale edits are rejected. Settings writes preserve unrelated keys, use a temporary file plus atomic replacement and serialize across processes. The configuration contains bridge secrets and is created with restrictive permissions. Do not publish it.

## Capture and status

Only the configured regions influence colours, but the capture backend still accesses the selected screen. Bottom-only sampling does not imply reduced capture permission, GPU work or calibrated HDR handling.

On Hyprland, wf-recorder is preferred. Other Wayland desktops can choose a screen through the sharing dialog. That fallback profile applies to whichever screen is chosen in the dialog; its actual monitor identity/aspect cannot currently be verified, so inspect the regions after selection. On Hyprland, if a sharing dialog appears after a fast-backend failure, select the same monitor as the saved profile.

The status distinguishes Starting, Waiting for screen selection, Running, Stopping, Error and Identify. Running requires an actual captured frame sent to the bridge. Recorder exit or stalled frames produce an error instead of indefinitely reusing old colours. Stop cancels a pending portal request. Shutdown attempts to close capture/DTLS and release the area cleanly.

GUI, CLI and Identify share a stream lock. An area already active in another app is refused. Stop Lumux or Hue Sync before starting Lumen.

## CLI

The CLI reads the same saved area, monitor and profile as the GUI. Explicit flags override saved settings temporarily and never persist configuration.

```sh
hue-sync --show-mapping
hue-sync --output DP-1 --mapping desk --band-height 20 --bottom-inset 0
hue-sync --mapping legacy
hue-sync --test
```

`--test` streams a rainbow independently of screen mapping. `--show-mapping` performs read-only discovery and prints resolved rectangles without capture or light changes.

## Installation and checks

Use the normal project installation, or install a built copy for your user without pip:

```sh
cd webui
npm ci
npm run build
cd ..
python packaging/install-user.py
hue-webui
```

This installer expects distro Python dependencies to be installed already. It creates versioned copies under the user prefix, managed CLI launchers and a Lumen desktop entry. It does not enable autostart, migrate another app's credentials or change settings. Previous app copies remain available through `~/.local/share/lumen/releases/`; the `current` symlink selects the active copy for the next launch. Stop the app before changing that symlink.

Development checks:

```sh
python -m unittest discover -s tests -v
python -m compileall -q huectl
cd webui && npm test && npm run build && npm audit
```

The tests cover reported coverage, old mapping compatibility, manual geometry, source changes, RGB/RGBA sampling, persistence, worker cleanup and capture failures. These checks do not replace physical calibration or performance testing in games. Automatic letterbox removal, multiple rectangles per channel, HDR tone mapping and Lumux reading-mode parity are outside this feature.
