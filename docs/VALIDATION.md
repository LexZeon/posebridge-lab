# Validation — 0.1.0-alpha.1

Date: 2026-09-15. This report separates real camera/runtime checks, synthetic tests,
and unverified roadmap features. Source-only alpha; no packaged executable.

## Automated checks

Final isolated suite: **51 tests passed in 8.203 s**, after the final UI and mannequin
changes. Initial suite: 47 passed in 8.508 s. The first expanded 51-test run also
passed (129.405 s while another model process was initializing); it is not used as
a performance benchmark.
Tests use a temporary `POSEBRIDGE_HOME` and compare the real settings fingerprint.
Camera tests in this suite use synthetic frames, not physical hardware. GPU
installation tests simulate failures/verification; real checks are listed below.

## Real 2D model download

The app's default download function retrieved a 20,496,303-byte RTMPose-s Body7
archive from the documented OpenMMLab host. It extracted only the model, checked
ONNX input/output shape and published the file in PoseBridge Lab's private model
directory. No model was added to Git. Tests additionally cover failed validation,
cancellation, truncation, unexpected redirect hosts, ambiguous archives and atomic
preservation of an earlier cache.

The actual downloaded CPU model also processed the upstream rtmlib `demo.jpg`
in memory: 641×950 input, 17/17 joints above 0.35, all XY values finite, and no
2D depth returned. This is a model compatibility sanity check, not an accuracy
evaluation. The third-party image is not included in this repository.

## Real camera, CPU

The system enumerated Integrated Webcam with both DSHOW and MSMF. Only the DSHOW
capture path was physically checked in the first run.

- Requested 640×480 / 60 FPS; actual measured capture roughly 30.6 FPS.
- 151 analysis updates over approximately five seconds after initialization.
- Last analysis rate 30.9 FPS; no skipped source sequence numbers.
- Inference median / p95: **16.07 / 19.34 ms**.
- Total processing median / p95: **17.26 / 20.52 ms**.
- Software queue median / p95: **6.38 / 14.90 ms**.
- Receipt-to-result-consumer median / p95: **25.40 / 34.07 ms**.
- Backend reported its buffer-size request was **not accepted**. The implementation
  does not claim it disabled camera/driver buffering.
- Last frame had **0 accepted body joints**. This establishes live camera/model
  execution and cleanup, not successful human motion tracking in that scene.
- Stop completed and the camera process was released; no frames, positions or
  preferences were saved by the check.

These timings exclude sensor exposure, camera/driver buffers, network encoding and
screen scan-out. They are one machine/scene, not a guaranteed end-to-end latency.

## Real GPU setup

DirectML initially reported unavailable in the base interpreter. The same installer
called by the UI resolved and downloaded 45,128,444 bytes of wheels to this app's
private staging directory, installed a separate runtime overlay, and passed its
actual execution probe with ONNX Runtime DirectML **1.24.4**. The overlay includes
ORT only (and provider metadata), not numpy/OpenCV from the resolved dependency set.
No package was installed into the shared OSR environment.

CUDA was not physically validated. The inherited isolated installer, DLL lookup,
failure preservation and verification paths are covered by regression tests. A
working system driver is still necessary. Provider registration alone is not
treated as successful GPU setup.

### Real camera with DirectML Pose

- 102 updates; DirectML active with no fallback warning; 640×480 DSHOW.
- Last measured capture / analysis: **20.1 / 19.8 FPS**; 9 skipped frames.
- Inference median / p95: **14.71 / 18.62 ms**.
- Processing median / p95: **15.72 / 19.78 ms**.
- Queue median / p95: **9.30 / 15.02 ms**.
- Receipt-to-result-consumer median / p95: **25.62 / 33.67 ms**.
- Last frame: 4 accepted joints. Camera process stopped cleanly; no camera data
  or settings were saved. This is not a full-body tracking acceptance test.

Camera rate and scene differ from the CPU check. These runs do not establish that
DirectML provides a higher overall frame rate; GPU availability and real Pose
execution were verified independently of that claim.

## Launch and visible UI

- Root Start.cmd completed `--smoke --language zh` and `--smoke --language en`
  successfully on the local interpreter; no personal settings writes.
- Chinese and English synthetic worker/UI runs stopped without callback errors.
- Visible Chinese input, model/GPU and tuning panels, English workbench, and
  Chinese/English bound mannequin were inspected. Final mannequin and workbench
  screenshots are explicitly synthetic and contain no camera content/model paths.
- No physical camera is used by smoke, synthetic UI or ordinary regression tests.

## Remaining limits

- RTMW3D download/inference with real weights, calibrated 3D, phone/wireless streams,
  prolonged occlusion, multi-person scenes and actual game integration are unverified.
- Raw/full-frame RTMPose has no independent person detector. Background hallucination
  and incomplete-body inference require real-scene evaluation.
- A fresh Setup.cmd dependency installation on a clean machine has not been tested.
  Local launch used a read-only existing interpreter and private dependency overlays.
- GitHub Actions is provided for clean Windows regression checks; a local pass is
  not evidence that a remote workflow has passed.
