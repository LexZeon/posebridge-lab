# Architecture

## Ownership and latency

`camera.py` owns each capture handle inside a dedicated spawned process. The process
reads continuously and publishes into one bounded shared-memory frame slot. A
sequence number distinguishes new frames; the parent copies a new frame while
holding the lock briefly. Busy readers cause a publication to be skipped, not a
queue to grow. Capture stop is cooperative first, then terminates only its own
child if the driver is stuck. Camera startup and stall checks are bounded.

`pipeline.py` owns model inference in a background thread. One model is loaded per
run, before opening the camera. The UI never loads models, captures, or infers on
its event thread. Each restart gets new capture and filter state. Stop checks
prevent late inference from publishing into a stopped run. Pose packets expose
read-only NumPy arrays; JSON snapshots contain copies and no images.

The UI receives a matched original image and result from the same packet. It does
not draw an old skeleton on the newest unrelated frame. Input newer than inference
is skipped. More than 0.5 s without a fresh result clears the preview/character,
rather than presenting a frozen character as current tracking.

## Modules

- `config.py`: validated settings, private application paths, atomic replacement.
- `sources.py`: OS camera enumeration and session-only network URL validation.
- `camera.py`: camera lifetime, transport, actual capture stats.
- `pose.py`: upstream RTMPose model methods + configured ONNX Runtime session.
- `stabilizer.py`: attributed OSR image-space filters; no game or TCode mappings.
- `pipeline.py`: lifecycle and immutable `PosePacket`; no Tk imports.
- `render.py`: overlays and solid mannequin; only display mirror, never exported mirroring.
- `models.py`: explicit, cancellable model download, shape validation, atomic publication.
- `gpu_runtime.py` / `gpu_downloads.py` / `directml_pose.py`: adapted isolated GPU setup.
- `app.py`: Tk workbench, event queue, source/model/GPU controls, avatar window.

## Current pose assumptions

The default RTMPose model is top-down, given the whole image as one ROI. There is no
person detector, multi-person selection, body-identity tracker, camera calibration,
metric depth or floor-plane constraint. First 17 COCO body joints are used.
The four optional 2D filters can hold points briefly; `observed` explicitly excludes
those predicted/held points. Filtering does not increase the original model scores.

RTMW3D has a separate path and download. Its upstream native XY/Z output convention
is not a calibrated game-space pose. The preview offers only a relative-depth
experiment and labels it unvalidated. No synthetic Z is returned for 2D.

## Future games

Use the packet boundary, not UI labels or screen scraping. A future adapter must
choose its engine coordinate system, sampling cadence, calibration, confidence
policy and stale timeout. Character proportions, IK, feet contacts and retargeting
belong after the pose contract; they should not change recorded observation data.
No game engine, network pose server, sensor protocol or hardware output is currently
implemented. The application is a camera-vision developer tool.

## Settings and tests

`POSEBRIDGE_HOME` selects application storage. Normal storage is under the current
user's local application data. GPU configuration uses `POSEBRIDGE_GPU_*` variables,
independent of OSR. Network URLs are deliberately not preferences.

`tests/run_tests.py` sets an independent temporary home before imports and checks
the original settings fingerprint. GUI tests explicitly use `persist=False`.
Never let a GUI cleanup callback execute a real preference save in a test.
