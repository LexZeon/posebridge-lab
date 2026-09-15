# AI takeover prompt (portable)

You are taking over **PoseBridge Lab**, a Windows camera-pose debugging application
and foundation for the owner's future game development. Read AGENTS.md, git status,
README.md, architecture/protocol/validation documents and the current version before
changing code. Preserve completed work and identify what still needs validation.

The product must remain focused on camera visual analysis: system cameras and
explicit phone/network video streams, RTMPose 2D, an explicitly unvalidated RTMW3D
option, same-frame source/skeleton display, bound mannequin, tuning controls,
model download and private GPU setup. Do not add OSR device control or Bluetooth
sensor protocols. The current mannequin is a debug model, not game-ready retargeting.

The original machine has an **AI_HANDOFF.local.md** next to Start.cmd containing
the full project/interpreter/private-storage paths, verified launch commands and
current results. It is intentionally excluded from Git. On another machine, use
the checkout directory and Setup.cmd instead of inventing those paths.

Understand `PosePacket` before integrating a game. 2D returns no measured Z;
RTMW3D native values are uncalibrated. Mirror is display-only. Scores are original;
held points never become observations. Timing starts after camera read returns.
Use bounded newest-frame consumption and stop-safe worker lifecycle.

Reuse provenance is documented: OSR stabilization/GPU tools were adapted;
RTMPose preprocessing/decoding remain upstream rtmlib; camera process, workbench,
packet and mannequin are new application code. Preserve the notices and avoid
claiming original authorship of upstream algorithms.

Run isolated tests and startup checks after changes. Real webcam checks must be
explicit and should print only aggregate diagnostics unless the owner requests
recording. Do not publish models, runtime downloads, personal camera images,
settings, logs or private paths. The owner's trial begins with Restore Defaults.

Next priorities: permitted real-motion validation, optional person detection/ROI,
3D calibration/coordinate audit, then an actual engine adapter with retargeting
and appropriate stale/confidence behavior. Do not claim those roadmap items are done.
