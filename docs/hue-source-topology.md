# Hue source topology and adaptive screen mapping

Research update: 6 November 2026. This refines the screen-mapping proposal; no streaming or bridge settings were changed.

## Findings from the source

Lumen currently extracts sorted channel IDs and channel x/y/z positions. Its channel-name lookup follows only the first member to a device name. It does not load the Entertainment segment tables, reconstruct coverage, expose gradient capabilities or distinguish several devices contributing to one channel.

The bridge exposes a resource graph:

```text
Entertainment area
  channels[channel_id]
    position                 spatial point for this stream channel
    members[]
      service.rid ----------> Entertainment service
      index ----------------> segments.segments[index]
                                start, length
  locations.service_locations[]
    service.rid, positions   placement/orientation hints

Entertainment service
  owner -------------------> Device (name, model)
  renderer_reference ------> Light (gradient capabilities)
```

One Entertainment channel can reference several internal segments, including members from different services. It remains one independently addressable HueStream channel. Segment index is not a pixel number, and channel ID is not physical left-to-right order.

The Home Assistant aiohue models explicitly define a member index as a segment reference within an Entertainment service, and a channel position as the average member position. Their model also separates segment capabilities from Entertainment area channels:
- [Entertainment configuration model](https://github.com/home-assistant-libs/aiohue/blob/main/aiohue/v2/models/entertainment_configuration.py)
- [Entertainment service model](https://github.com/home-assistant-libs/aiohue/blob/main/aiohue/v2/models/entertainment.py)

These are primary implementation sources, not a substitute for every detail of the Hue specification. The official Hue v2 API reference returned HTTP 403 during this research; exact physical-length and interpolation semantics could not be independently verified there.

## An anonymized topology observed on a gradient strip

The live read-only bridge response reported 16 logical gradient pixels and this segment table:

| Segment index | Start | Length | End exclusive |
|---|---:|---:|---:|
| 0 | 0 | 1 | 1 |
| 1 | 1 | 2 | 3 |
| 2 | 3 | 3 | 6 |
| 3 | 6 | 4 | 10 |
| 4 | 10 | 3 | 13 |
| 5 | 13 | 2 | 15 |
| 6 | 15 | 1 | 16 |

The area groups them as:

| Channel | Member segment indexes | Logical interval | Logical coverage | Area position |
|---|---|---|---:|---|
| 0 | 0, 1 | [0,3) | 3/16 = 18.75% | Right |
| 1 | 2, 3 | [3,10) | 7/16 = 43.75% | Centre |
| 2 | 4, 5, 6 | [10,16) | 6/16 = 37.5% | Left |

For the configured left-to-right direction, a coverage-proportional desk mapping would therefore be:

| Screen region | Channel | Bottom-band rectangle |
|---|---|---|
| Left 37.5% | 2 | [0, 0.8, 0.375, 1] |
| Next 43.75% | 1 | [0.375, 0.8, 0.8125, 1] |
| Right 18.75% | 0 | [0.8125, 0.8, 1, 1] |

This is a mapping inferred from reported logical coverage. It is not a measured statement that physical light coverage has these exact lengths. Firmware, shortening/extensions, internal interpolation and the user's placement can affect the visible result. The room coordinates are placement hints; they do not establish the strip's physical length.

The light separately reports five gradient palette points. These belong to the ordinary light-gradient interface and must not generate five Entertainment channels. Likewise, max_segments=10 is an advertised capability ceiling, not ten active channels; the actual segment list has seven entries. configurable=false describes the reported segmentation capability; by itself it is not proof that every aspect of Entertainment area channel construction is immutable. V1 will consume the existing area without attempting to rewrite it.

## Revised dynamic mapping design

Insert a source-discovery step before region generation:

1. Fetch the selected area and referenced Entertainment services, devices and light services. Resolve every member by service ID and index, not by name or model.
2. Build a sanitized topology containing channel IDs, all device memberships, segment intervals, actual table length, logical extent, light pixel count when present, gradient point capability, positions and service placement hints.
3. Validate member indices, positive lengths, interval bounds, duplicates/overlap, missing services and ambiguous extents. Do not silently repair inconsistent bridge data or sum overlapping ranges twice.
4. Classify each source: single-zone light; segmented strip with usable coverage; segmented source with incomplete coverage; or shared/mixed channel topology.
5. Generate a proposed screen mapping from both source topology and the user-chosen physical layout. Preview exactly what will be sent, then let the user Apply.
6. Revalidate on start and explicit refresh; invalidate on relevant bridge resource changes. Never change a running custom mapping silently after discovery.

A bottom-only intent still comes from the user. A channel's z coordinate cannot tell us reliably that the user wants only a particular screen edge.

### Editor changes

Group channels under physical devices. Show, for example, "Gradient strip: 3 sync channels, 7 internal segments" with expandable technical details. Do not call logical pixels physical LEDs.

Desk strip gains a **Region widths** choice:
- **Reported coverage**: reconstruct channel spans from segment membership.
- **Equal widths**: split the band evenly.
- **Custom**: edit boundaries manually.

When a single straight strip has complete, contiguous, nonoverlapping membership spanning a verified logical extent, propose Reported coverage and label it "Based on bridge data - verify on your strip". Keep Equal widths one click away. If coverage is incomplete or mixed, propose Equal widths with an explanation; never invent a coverage ratio from member count.

Width generation uses union length of member intervals, not number of segment entries. For this example, counting members gives 2:2:3, which is different from the reported 3:7:6 coverage and would be wrong for this model.

For a proven contiguous strip, preserve normalized source boundaries and reverse them when direction is reversed. Derive likely orientation from the relationship between source interval order, channel positions and service placement hints; require explicit identification if those disagree or are ambiguous. Do not assume the first placement point always denotes the power-connector end.

For multiple devices, ask which device(s) follow the desk band. Each device may span the full width independently, or a user-selected share of it. Never divide all channels from unrelated lamps into one long strip. A mixed-device channel must be presented as a shared output that cannot be controlled independently for each member.

For disjoint member intervals, retain the full interval set in topology but do not silently compress it into one inferred rectangle. Keep custom one-rectangle-per-channel in v1 with a warning and an explicit choice; multiple weighted sampling rectangles per channel can be a later schema version.

### Calibration

Provide two explicit stopped-sync tests:
- Identify channel: low-brightness bounded single-channel illumination, to associate channel labels and strip direction.
- Boundary check: distinct stable channel colours, to inspect visible coverage, followed by a moving screen marker during ordinary sync.

Always label tests as changing the lights. Do not infer physical segment lengths solely from the metadata, or promise exact previous-state restoration without testing. The user can adjust coverage boundaries after calibration.

### Persistence refinement

Extend the draft schema before implementation:
- layout type and selected source device/service IDs;
- width strategy (reported_coverage, equal, custom);
- explicit source order/orientation override;
- effective normalized rectangles;
- discovery signature covering channel members AND segment start/length table, relevant pixel_count, placement/orientation metadata and bridge/area identity;
- discovery warnings and calibration status kept separate from the mapping geometry.

A signature must detect firmware/topology changes even when channel IDs and member indexes stay the same. A model-name change alone must not generate a new mapping. Resolved rectangles remain the runtime source of truth; refreshed metadata produces a proposed revision rather than replacing custom settings.

Keep the topology analyzer dependency-free and separate from screen sampling. No bridge discovery or graph traversal belongs in the frame loop. Expose sanitized capability data through the existing Python API/store boundary.

### Acceptance additions

Use anonymized fixtures for:
- a one-channel non-gradient bulb;
- this uneven 3-channel/7-segment/16-unit topology;
- the same channel count with changed segment lengths;
- reversed physical placement;
- a strip exposing a different number of channels;
- duplicate x positions;
- missing pixel_count but consistent segment extent (show inferred extent);
- missing/out-of-range segment references;
- overlapping or disjoint member intervals;
- multiple strips and channels shared across devices.

Assert exact normalized widths, direction reversal, no accidental palette-point/channel conflation, and stable HueStream channel ordering. Treat metadata-to-visible-length agreement as a separate hardware calibration result.

## Effect on the original plan

The equal-thirds illustration remains useful as a selectable Equal widths preset, but it is no longer the sole desk-strip default. Discovery and topology validation become part of the pure mapping-engine milestone. The static UI concept predates this refinement; add the Region widths choice and device-grouped channels when implementing it.

This research establishes enough structure to design a capability-driven mapper. Physical coverage, identify-test behavior and on-device performance are still unverified. No claim is made that the area supports more than its currently advertised stream channels.
