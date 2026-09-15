# Changelog

## 0.1.0-alpha.1 — 2026-09-15

- Independent Windows camera-pose developer workbench with Chinese/English UI.
- System camera enumeration, DirectShow/MSMF choices, requested format/FPS,
  and session-only RTSP/HTTP(S) input for phone/network cameras.
- Single-slot shared-memory camera process, latest-frame inference and bounded
  camera shutdown; actual rates and clearly scoped software latency metrics.
- Existing RTMPose 2D model/API route, same-frame skeleton, joint confidence table,
  configurable stabilization and JSON debug snapshots.
- Bound solid mannequin preview; 2D depth is unmeasured and RTMW3D remains explicitly
  experimental/unvalidated, with a separate model path and download option.
- In-app model download and isolated CUDA/DirectML setup with progress, execution
  verification and explicit CPU fallback. No changes to the OSR environments.
- Source attribution, architecture, takeover guide and isolated regression suite.
- Final local validation: 51 isolated tests, Chinese/English launch checks, real
  webcam CPU/DirectML execution, model download and synthetic avatar inspection.

This is camera visual analysis only. A real game adapter, calibrated 3D tracking,
multi-person identity and character retargeting are future work. Validation results,
including limitations and failed checks, are recorded separately.
