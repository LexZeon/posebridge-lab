# posebridge.pose.v1

`PosePacket.to_dict()` is the current engine-independent debug snapshot contract.
The GUI can save one fresh snapshot. No automatic frame recording or network
streaming exists in this alpha.

| Field | Meaning |
| --- | --- |
| `schema` | `posebridge.pose.v1` |
| `sequence` | Camera publication sequence; skipped numbers are expected. |
| `received_monotonic` | Time after the camera read returns; not exposure time. |
| `completed_monotonic` | Time after pose and stabilization finish. |
| `mode` | `2d` or experimental `3d`. |
| `provider` | Actual inference provider category, including CPU fallback. |
| `image_size` | Width/height of the processed image. |
| `xy_pixels` | 17 filtered joints; X right, Y down. Missing values are JSON null. |
| `raw_xy_pixels` | Upstream 2D observations before filtering. |
| `scores` | Original model scores; no synthetic confidence increase. |
| `observed` | Joint accepted this frame; false includes held/estimated and missing. |
| `native_3d_unvalidated` | null for 2D; upstream experimental XYZ for 3D. No metre/game-space guarantee. |
| `inference_ms`, `processing_ms`, `queue_ms` | Software timings, excluding camera exposure/driver buffering. |

Joints: nose; left/right eye; left/right ear; left/right shoulder; left/right elbow;
left/right wrist; left/right hip; left/right knee; left/right ankle. Left/right are
the person's anatomical sides. The GUI mirror option never changes these values.

Snapshot arrays are finite numbers or null; serialization forbids NaN. A future
adapter must treat `observed=false`, stale timestamps, changed sequence/session and
`mode=3d` experimental data deliberately. Monotonic timestamps are local-process
clock values, not wall-clock time or synchronized timestamps for other machines.
