# Screen mapping verification

Date: 6 November 2026. Feature revision: `b74f848` on `feat/screen-region-mapping`.
Review: https://github.com/magnusmk2/Lumen/pull/1

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
