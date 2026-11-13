# Screen mapping verification

Final acceptance: 13 November 2026. Branch: `feat/screen-region-mapping`. Installed release: `b921d77138e33a60`. Earlier sections below record incremental checks.
Review: https://github.com/magnusmk2/Lumen/pull/1

## Final acceptance — all five stages

96 Python tests, 17 frontend tests, production build, compilation, 322 matching English/French keys and zero npm audit vulnerabilities passed. The installed source/build matches the checkout.

The final installed build completed 1,800.11 seconds of real monitor capture and bridge streaming: 54,003 frames, 180 advancing samples, measured mean 30.0 FPS throughout, maximum sampled capture age 34 ms, and no worker error. Native leave/restore and all three quality grids passed. A real Window-tab selection returned window metadata and 30 valid frame reads. Actual area-only scene-on-stop and explicit tray Quit with state restoration passed; temporary scene/zone resources were removed, original preferences restored, the area became inactive, and capture/DTLS children exited.

A third-party pystray atexit callback logged an already-missing notification ID after successful application shutdown. This did not prevent restoration or child cleanup; it remains a cosmetic upstream shutdown log issue. A normal installed application was already running when final relaunch was attempted; the single-instance guard raised it successfully, and it was left open and idle rather than replacing that session.

Current desk mapping is the bottom 20%, inset 0, black-bar detection enabled. Original response/colour and balanced/leave/no-persistence preferences are retained. HDR, gaming overhead, physical calibration, arbitrary film detection accuracy and other compositor/hardware combinations remain unverified. Restoration is best effort because Hue provides no atomic compare-and-swap. Optional portal consent persistence has fixture coverage and was not enabled on this desktop.

## Incremental verification history

## Automated checks

- 38 Python tests pass.
- 7 frontend store tests pass using Node's built-in test runner.
- Production Vue/Vite build and Python compilation pass.
- English/French dictionaries contain the same 213 keys.
- npm audit reports zero vulnerabilities after updating the lockfile.
- Staged source was checked for the locally used bridge credentials before publication.

The suites cover legacy mapping parity, unequal reported coverage, nonsequential channel order, manual geometry, inset/range/direction, nullable capabilities, multiple sources, shared channels, topology changes, RGB/RGBA bottom-only sampling, atomic settings updates, stale revisions, cancellation, capture EOF/stderr failures, stream locks, CLI saved-monitor behavior, refresh/retry, failed context saves and tray-quit regression behavior.

## Live integration checks

Performed on CachyOS with Hyprland/Wayland and a real Hue bridge/gradient strip:
- wf-recorder produced continuous raw frames.
- Bridge discovery exposed three sync channels with seven internal segments.
- A bottom 20% profile resolved to left-to-right widths 37.5%, 43.75%, 18.75%.
- Saved profile reload, live manual edits and reset worked; the runtime adopted mapping revisions without restarting the stream.
- Ten start/stop cycles completed in an integration pass.
- Bounded channel identification completed without worker errors.
- A second CLI streaming session was refused while the GUI session owned the stream.
- Actual GTK/WebKit windows were inspected at normal and 400-pixel widths, including dark/light rendering and keyboard focus handling.
- A signal-quit regression was fixed. Subsequent native shutdown checks exited in 1.31 and 1.41 seconds, left the area inactive and left no capture/DTLS child processes.
- Final installed-build UI smoke passed: Refresh, double-start guard, active sync, device editor, Escape and focus return.

A sustained core-path check recorded **766 seconds, 22,913 sent frames and 75 status samples**, with advancing frame counts and no worker error. This was a bounded run while final metadata/frontend hardening was reviewed; the final revision was subsequently installed and smoke-tested. It is not a completed 30-minute soak of the final build.

A local microbenchmark measured approximately 0.0132 ms per frame for averaging three bottom-band RGB0 regions at 64x36. This excludes capture, colour conversion, transport, UI, GPU costs and game performance.

## Limits

No claim of zero defects follows from these checks. Physical strip direction and visible coverage still need calibration by observation. Gaming/frame-time overhead, HDR colour calibration, long-duration stability, non-Hyprland portal selection and other light hardware remain unverified. The earlier design's full 30-minute soak was not completed.

No bridge area layout, device segmentation or additional independent channels were created. Manual mapping controls screen sampling within the bridge's existing channel capabilities.

## Live preview follow-up

Restored large live channel swatches on Sync and Edit mapping, preserving channel IDs while displaying them left to right. Diagram regions follow current output colours. Production build, 38 Python tests, 7 frontend tests and 213-key translation parity pass. The installed GTK/WebKit app was observed returning different hex colours across successive samples; its editor showed matching coloured regions. Draft/applied distinction is labelled explicitly.

## Button help follow-up

Added shared hover/focus help for every button, with disabled-state reasons, accessible descriptions, viewport positioning and Escape dismissal. Native GTK/WebKit checks confirmed the disabled Identify explanation while syncing, keyboard focus help, and tooltip dismissal while preserving the editor. The initial automation used an incorrect label and then needed to wait for its programmatic scroll event before hovering; corrected smoke checks pass. No pointer movement was used.

38 Python tests and 10 frontend tests pass, including button coverage and disabled hit-test modal isolation. Production build, compilation, 266-key English/French parity and runtime dependency audit pass. The REST gradient example was researched separately; Philips guidance rules out continuous fast REST updates as a screen-sync replacement.

## Automatic black-bar detection — stage 1

Source review and acceptance gates are recorded in [sync upgrade plan](sync-upgrades.md), with the reviewed Lumux revision and primary portal documentation. Independent dependency-free implementation; no Lumux code or NumPy dependency was added.

54 Python tests and 11 frontend tests pass. Added cases cover RGB/RGB0 and ignored alpha, letterbox, pillarbox, combined bars, candidate instability, dark/all-black retention, full-picture recovery, one-sided overlays, sparse subtitle/edge noise, saturated blue, excessive crop, resize/reset, malformed frames, manual geometry/rounding, old-profile identity, setting validation, live frame-boundary toggles and telemetry clearing. Production build, Python compilation and 273-key English/French parity pass.

A local microbenchmark analyzed 1,000 64x36 RGB0 frames in about 0.325 seconds (0.325 ms per analyzed frame), with analysis capped at 5 Hz in the runtime. This is detector-only timing, not end-to-end CPU/GPU or gaming overhead.

Native installed-build Apply/Cancel and preview checks are performed with the actual bridge and wf-recorder. Synthetic pixel fixtures validate crop and sampled-colour behavior; normal desktop playback is a separate live path and is not presented as proof of detection on every film. Detector accuracy on HDR, unusual/asymmetric borders, heavily compressed near-black bars and arbitrary dark compositions remains unverified. A full final-build long soak and film comparison remain future validation gates.

Final stage-1 native check: Cancel discarded the detection draft, Apply saved/enabled it without changing the manual inset, reopening showed the persisted checkbox, and the applied boundary/regions appeared in the installed GTK/WebKit window. A subsequent 90-second real-bridge/wf-recorder run advanced from 45 to 2,745 sent frames (2,700 frames) at 30 FPS with detection enabled and no worker error. The captured desktop had no accepted paired bars; the live check used the full-picture boundary, while crop behavior is verified by synthetic fixtures. Initial test harness attempts mishandled Promise results and toggled an already enabled checkbox off; the harness was corrected to check worker telemetry and account for initial state. No product defect was hidden by those corrections.

## Response and colour — stage 2

Added a validated shared processing module, elapsed-time exponential response with float history, brightness/gamma controls, a serialized partial-patch API and shared CLI defaults/overrides. Complete settings snapshots are queued to the sample thread after successful atomic persistence. First frame, changed parameters, capture restart and mapping revisions reset response history; zero response bypasses smoothing. Default settings match previous colour output exactly.

Automated checks currently pass: 67 Python tests, 14 frontend tests, production build, compilation and 284-key English/French parity. Added tests cover original-colour parity, gamma/brightness/black, 63%-at-tau and equal response at 20/30/50 FPS, bounded steps/dark fade, reset/unchanged parameters, channel count changes, finite ranges/types, old config, copying queued snapshots, processed preview equality, failed persistence, partial-patch preservation, CLI saved/override settings, frontend failure behavior, serialized rapid edits and active-source refresh.

Native stage-2 checks passed on the installed GTK/WebKit app with the real bridge and wf-recorder: response, brightness and gamma applied while running; source identity and recorder PID were unchanged; gamma 6 was rejected without changing saved/runtime gamma; a subsequent valid edit cleared the error. A 60-second run advanced 1,803 frames without worker errors. After adding pending-save UI guards, the final installed build passed the same edits plus a delayed-write check confirming Start/Stop is disabled until the write finishes, a 300-pixel control-container overflow check, and a 15-second run advancing 453 frames without errors. Existing settings were restored through the UI after both runs (saturation 1.6, brightness 100%, gamma 1, response 0). Live screenshots were inspected. Response speed remains a user preference; no subjective default/preset or performance superiority is claimed. This is not a long-duration final-build soak.

## Preview, capture and finishing — stages 3–5

Implemented a single applied-content preview with channel IDs/processed colours, actual capture grid/source aspect metadata, frame freshness and measured mean send rate. Idle/error states clear live telemetry. Capture adds three fixed quality grids, capability-gated explicit monitor/window portal requests, hidden cursor when available, optional private single-use token persistence and v6 PipeWire serial targeting supported by the installed `pipewiresrc`.

Finishing preferences default to the previous leave behavior. Optional restore and area-only scene recall use an in-memory writable-state snapshot, verified application identity, current streamer/ordinary-state/overlapping-area checks, scene revalidation, graceful/forced-stop distinctions, and per-write cancellation checks. Cleanup failures no longer silently disappear or prevent an owned area being released when snapshot reads fail. Startup rechecks area availability after potentially lengthy capture selection. Missing bridge application identity refuses activation rather than taking an unsafe ownership fallback.

Automated checks: 96 Python tests, 17 frontend tests, production build, compilation, 322-key English/French parity and zero dependency audit vulnerabilities. New cases cover paired bars across all quality grids, writable-state selection, scene scope, changed/partial state, another owner, failed reads/writes, cancellation, missing identity, normal/error/forced finishing, atomic preferences/token discard, unsupported portal types, pre-v4/opt-out persistence, token consumption/replacement, pipeline source types/serial/quality, and stale health/finish UI state.

Live evidence so far:
- This desktop advertises ScreenCast v6, source types 7 and cursor modes 3. GET `/auth/v1` returned an application ID matching the active streamer's auth_v1 reference.
- A real window-sharing request cancelled in 3.01 seconds and closed its session without selecting a source.
- Installed GTK/WebKit cycles used 64×36, 32×18 and 128×72 and showed current health/channel geometry. Ordinary leave completed, and restore-on-stop requests applied successfully on the real strip in the tested restore cycles. Preferences were restored through the UI afterwards.
- The initial acceptance harness read output choices before async initialization, then clicked a disabled Refresh while trying to reload a direct config write. The harness was corrected to wait for initialized choices and restore through the enabled UI controls; product behavior was not changed to bypass those checks.

Final long-run, window frame and live scene-recall results are recorded in Final acceptance above. Finishing checks reduce races but do not provide an atomic guarantee; simultaneous external writes, same-key clients, offline physical behavior, HDR, gaming overhead and all other compositors/hardware are not established by these checks.

Portal investigation found an inherited request-response race: stock Lumen subscribed after calling the portal, so a fast CreateSession response could be lost. Requests now subscribe first, buffer responses by returned request path (including legacy paths), and run on a private GLib context rather than the GTK context. Regression tests cover response-before-reply and cancellation cleanup; the primary [Request specification](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Request.html) explicitly describes this ordering requirement.

With the fixed code, the user-selected Lumen window returned source type 2 and size 1269×1389. The actual portal/GStreamer pipeline produced 30 valid 64×36 RGB frames (6,912 bytes each), then closed cleanly. Earlier selections returned source type 1 and 3840×2160: the user confirmed selecting the monitor, and window-only validation correctly rejected those results before reading frames. No compatibility exception for a suspected backend source-type bug was introduced. The picker can open on its Screen tab even when the client requested windows, so the error now explains selecting the Window tab. Optional persistent selection/token rotation remains fixture-tested rather than silently enabled on the user's desktop.

The final source also distinguishes caller cancellation from capture failure. A typed cancellation during an explicit Stop is a graceful end, so restoration is not lost to a race in frame reading; a forced shutdown still revokes finishing permission. A regression test sends a frame, cancels the next read and verifies the owned normal stop restores state. Total automated coverage is now **96 Python tests and 17 frontend tests**.

An isolated browser fixture using the production bundle and real translation dictionaries was inspected at a 400-pixel viewport in dark/light themes and English/French. Both new control panels had matching client/scroll widths (no horizontal overflow), long labels wrapped, and keyboard ArrowRight changed the gamma slider from 1.0 to 1.1. These layout checks did not operate the bridge or alter native application preferences; the fixture server/tab and viewport override were closed/reset afterwards.

A synthetic three-channel sampling benchmark (3,000 calls/grid, simulated 30 FPS, bar checks capped at 5 Hz, response 250 ms) measured approximately 0.0542/0.0969/0.2728 ms per call at 32×18/64×36/128×72. It includes raw-region averaging, detection, colour processing and telemetry plus test/mock plumbing; it excludes capture, DTLS, GTK/WebKit, GPU and game rendering costs. It is not an end-to-end performance comparison with Lumux.

Portal cancellation requests close the request and session. During investigation this Hyprland version left a timed-out picker helper visible after its client ended; the stale test helper was closed before retrying. This is distinct from an active Lumen-owned capture process. No window frames are read after rejecting a returned monitor, and no persisted consent was enabled for these checks. Persistent consent remains opt-in and token mechanics are covered by fixtures.


## Application lifecycle options — 13 November 2026

Added opt-in automatic sync at application startup and selected-area lights-off on explicit tray Quit. Saved settings are validated booleans, default false, exposed with English/French explanatory text and persisted through the existing atomic preferences API. Startup uses the saved area/output/rate/processing once; errors remain visible in sync state. Worker launch and shutdown are serialized to avoid starting a capture after quit. Quit waits for the worker, skips off on timeout/forced termination, and rechecks area membership and overlapping streams before every light request. Idle quit is supported; closing to tray remains unchanged.

102 Python tests and 17 frontend tests pass, production build/compilation pass, and all 326 English/French keys match. Added regression cases exercise defaults, invalid boolean types, saved startup arguments, failed/missing startup selection, exact area-only off payloads, absent selection, overlapping streams, takeover between writes, signal/normal-stop exclusion and shutdown timeout. Native installed-build acceptance automatically streamed 91 frames, confirmed checked/disabled controls, toggled both preferences off/on through the UI, stopped sync, then used actual tray Quit while idle and verified all target lights reported off and area inactive. Original preferences and on/off states were restored. The first UI probe ran before asynchronous preference initialization; waiting for the checked state corrected the harness. The previously documented third-party notification atexit log remains cosmetic.
