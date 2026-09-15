# PoseBridge Lab development instructions

This repository is an independent camera-vision project. Do not modify the sibling
OSR repositories or their Python environments. Current source: 0.1.0-alpha.1.

Read README.md, docs/ARCHITECTURE.md, docs/POSE_PROTOCOL.md, docs/VALIDATION.md,
THIRD_PARTY_NOTICES.md and git status before developing. The exact local paths are
in AI_HANDOFF.local.md on the original developer machine; never commit that file.

Scope: camera input, RTMPose 2D, explicitly unvalidated RTMW3D option, skeleton,
mannequin and developer diagnostics. Future games use the packet contract.
No TCode, real-device actuation, Bluetooth sensor data or generic game-plugin claim.
Wireless phones are system cameras or explicit video-stream URLs.

Keep camera/model/filters/UI separate. Latest-frame transport must remain bounded.
Do not return synthetic depth for 2D. Held points are not observations. Latency
begins at software receipt, not exposure; camera FPS requests are not measurements.

Use `python tests/run_tests.py` for all ordinary regression checks. It isolates
POSEBRIDGE_HOME before imports and verifies real preferences did not change.
GUI fixtures use persist=False. Never patch save only around setup and let cleanup
write real preferences afterward. The user restores defaults before each trial;
acceptance should work from defaults, without depending on personal settings.

Keep Chinese/English, save/load/defaults and docs synchronized. Models, runtime
wheels, videos, screenshots of personal camera content, logs, private paths,
credentials and local settings do not belong in commits. A synthetic screenshot
clearly labeled as such may be included for UI documentation.

For a finished change, state what changed, actual verification, remaining limits,
and provide Start.cmd / Start.md. Do not claim unrun hardware, 3D, phone or GPU tests.
