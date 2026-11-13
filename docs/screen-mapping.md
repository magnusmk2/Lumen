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

Live channel colours appears on both the Sync page and inside Edit mapping. Large swatches and hex values show current sampled light output in left-to-right spatial order. The diagram also uses those live colours while syncing. This is the currently applied mapping; draft edits do not change the output until Apply. Both views share the existing preview polling, with no additional capture session.

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

## Button help

Hover over a button or focus it with the keyboard to see an explanation. Greyed buttons also explain the blocking condition. Disabled controls keep their normal disabled behavior. Press Escape to dismiss a visible tip; press it again to close the mapping editor. Help is available in English and French throughout navigation, setup, pairing, light controls and mapping.

## Automatic black-bar detection

In **Sync → Edit mapping**, enable **Ignore black bars automatically**, then Apply. The setting is saved with the bridge/area/monitor profile and also works when the CLI loads that saved profile. Existing profiles default to off. Cancel leaves both the saved profile and running sampler unchanged.

The sampler looks for stable paired letterbox/pillarbox bars in its existing low-resolution capture. It requires a visible interior and a one-second stable candidate; black/dim frames and temporary one-sided overlays retain the accepted boundary. It returns to the full picture after 0.4 seconds of clear full-frame content. Asymmetric borders are deliberately not detected. Use fullscreen video: browser chrome, taskbars or window borders touching the capture edges can prevent detection; this stage does not locate a player window inside a desktop. This is a conservative visual heuristic: it cannot distinguish every dark composition from genuine bars, and its boundary is quantized to the capture grid.

When enabled, all mapping coordinates are relative to the detected picture. Bottom band height, bottom inset, device screen range and manual rectangles keep their meaning inside that picture. An inset previously used only to avoid a black bar should usually be set to zero; the app does not silently change your calibration.

The applied-picture preview shows the accepted content boundary and effective channel sampling regions. The editable diagram stays in picture-relative coordinates; its draft is applied only after Apply. Full-monitor capture still occurs; detection only changes which captured pixels contribute to the lights. No additional capture session, screenshot upload or image storage is introduced.

The [upgrade plan](sync-upgrades.md) records the research and gates for later response/colour, capture and stop-behavior improvements.

## Response and colour

The Sync page keeps colour boost visible and puts response time, brightness and gamma under **Response & colour**. Sliders and number fields support keyboard input. Changes save when you release a slider or commit a number; they apply at the next sampling frame without restarting capture. A failed save leaves the visible saved settings and runtime unchanged. Start/FPS/context actions wait while a colour save is in progress.

- **Response time:** 0 ms is immediate. Higher values soften changes using elapsed-time exponential smoothing. The value is a time constant: after that interval a steady target has moved about 63% of the way to its new colour. It is not a fixed delay or time to completion. Range 0–2000 ms.
- **Brightness:** output multiplier, 0–100%. The default 100% preserves existing output.
- **Gamma:** 1 preserves the brightness curve; above 1 darkens dim colours and below 1 brightens them. Range 0.1–5.
- **Colour boost:** saturation multiplier, 0–4. Existing default 1.6 is retained.

Defaults preserve the previous colour math exactly. Smoothing operates on processed RGB output and the live swatches show that same processed result. Starting/reopening capture, applying a mapping, or changing processing values resets history so old output does not leak into a new context. Setting the same values leaves history intact. No new subjective preset is selected for you; Reset colour controls restores the documented defaults.

These settings are shared by the GUI and CLI. `hue-sync` loads saved values; `--brightness 0.8 --gamma 1.2 --response-ms 250` overrides them for one screen-sync run without changing the saved preferences. `--saturation` also remains available. The rainbow test source is unaffected by these screen-processing controls.

## Capture choices and quality

Screen to capture lists direct monitors plus explicit portal monitor/window choices advertised by the desktop. Starting a portal choice opens the desktop sharing picker. Select the intended source there. For window capture, open the picker’s **Window** tab and choose the application row; this Hyprland picker may initially show its Screen tab even for a window-only request. A returned monitor is rejected with a clear instruction. A window-only request is not silently changed into whole-desktop capture when the portal does not support it. Each capture choice has its own saved mapping profile; unknown portal selections use normalized geometry and the live preview adopts the returned source aspect ratio when available.

Under **Capture & finishing**, choose Economy (32×18), Balanced (64×36, the existing default) or Detailed (128×72). These are sampling grids, not the native monitor resolution. More samples can improve small rectangles and border precision, with more processing work. Stop sync before changing this setting. The CLI uses the saved quality, or `--quality economy|balanced|detailed` for one run.

**Remember portal selection** is optional and off by default. It requests the desktop's persistent selection mechanism where advertised; the desktop still controls consent. Restore tokens are stored only in the local private configuration, consumed once and replaced after successful selection. They are never returned to the UI. Turning remembering off discards saved tokens. If a desktop picker remains visible after cancelling or timing out, dismiss the picker itself; Lumen has already cancelled its request. The direct monitor path needs no portal token. Window and monitor tokens are separate.

The live picture preview shows effective sampled regions, their channel IDs and processed colours; the editable mapping diagram stays picture-relative. Capture health shows the active backend, sampling grid, mean sent FPS and capture age. These describe sample/stream progress, not game rendering performance. They clear when the source stops or fails, so old output is not presented as live.

## Lighting after stopping

The default **Leave lighting as the bridge decides** preserves the previous stop behavior. Optional modes are:

- **Restore captured light state:** send the affected lights' ordinary on/brightness/colour/gradient/effect state captured before activation.
- **Apply selected scene:** recall a chosen scene after the stream is released. Only scenes whose actions affect lights entirely within this Entertainment area are offered; select a scene before enabling this mode. If none is eligible, create a zone containing only the desired sync lights, save a scene for that zone, then Refresh.

Preferences are saved while sync is stopped and fixed for that session. They apply after the Stop button, explicit tray Quit, or graceful CLI Ctrl+C after at least one frame. Startup cancellation, capture/transport errors, forced signals and unconfirmed/changed ownership skip finishing requests. The app checks its identity from `/auth/v1`, the area's active streamer, ordinary light state and overlapping active areas. Changed scenes are revalidated before recall. Partial completion, skipped requests and failures are displayed separately.

Restoration is best effort: Hue has no atomic compare-and-swap for these requests, another controller can act between checks, apps sharing the same Hue authorization cannot be distinguished, and an accepted bridge request does not prove an offline light physically changed. Finishing is restricted to the area and aborts remaining requests on cancellation, ownership/state changes or errors. It does not restore every kind of dynamic scene execution state. Ordinary state snapshots stay in memory for that session; credentials and tokens are never included in UI telemetry.
