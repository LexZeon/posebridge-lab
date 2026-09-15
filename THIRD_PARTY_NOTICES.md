# Sources and licenses

Reviewed on 2026-09-15. This is a source project, not a bundled binary distribution.

| Project | License / role | How it is used |
| --- | --- | --- |
| [LexZeon/osr-screen-tcode](https://github.com/LexZeon/osr-screen-tcode) | Apache-2.0 | Stabilizer, GPU runtime/download manager, DirectML adapter and related tests adapted from local test.22. Existing attribution preserved. New camera/UI/packet/avatar integration is separate. |
| [Tau-J/rtmlib](https://github.com/Tau-J/rtmlib) | [Apache-2.0](https://github.com/Tau-J/rtmlib/blob/main/LICENSE) | Runtime dependency; RTMPose/RTMPose3d preprocessing and decoding are inherited without reimplementing them. CPU session thread control and provider handling are application adapters. |
| [OpenMMLab MMPose](https://github.com/open-mmlab/mmpose) | Apache-2.0 code; consult model/dataset terms upstream | Source of RTMPose research/models. We do not train or claim ownership of those models. |
| [OpenCV](https://github.com/opencv/opencv) | Apache-2.0 for current releases | Camera capture, optical flow, Kalman filters, affine/image operations. |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | MIT | CPU/CUDA/DirectML inference and tiny arithmetic-only GPU check. |
| [cv2_enumerate_cameras](https://github.com/lukehugh/cv2_enumerate_cameras) | MIT, Copyright (c) 2024 Yu He | Installed dependency to enumerate camera names and matching OpenCV indexes. No source copied into this repository. |
| [NumPy](https://numpy.org/), [Pillow](https://python-pillow.github.io/) | BSD-3-Clause / HPND | Arrays and Tk image display. Installed dependencies, not vendored binaries. |
| [imutils WebcamVideoStream](https://github.com/PyImageSearch/imutils/blob/master/imutils/video/webcamvideostream.py) | MIT, Adrian Rosebrock | Conceptual reference: continuously capture and consume the most recent frame. No code copied; our version uses a bounded shared-memory slot and a separate process with termination. |

The 2D download URL is the RTMPose-s Body7 ONNX export linked by the original
OSR app / MMPose model zoo. The experimental 3D URL is the RTMW3D-x model
referenced by [rtmlib Wholebody3d](https://github.com/Tau-J/rtmlib/blob/main/rtmlib/tools/solution/wholebody3d.py).
Downloads remain in the user's private application directory. The computed
SHA-256 records downloaded bytes; it is not an upstream signature or independent
authenticity guarantee. Input shape/output count are checked before publication.

Optional GPU installation resolves PyPI wheels, validates their recorded hashes,
and publishes a private overlay only after an execution probe succeeds. CUDA/cuDNN
components retain their own NVIDIA license terms and are not redistributed here.
DirectML runtime components retain their upstream terms. Existing package metadata
and license files are preserved in the private installation.

Implementation references:

- [OpenCV capture property limitations](https://docs.opencv.org/4.x/d4/d15/group__videoio__flags__base.html): capture properties depend on hardware, drivers and backend; buffer requests are not promises.
- [CUDA provider requirements](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html) and [DirectML session requirements](https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html).
- [Windows phone camera input](https://support.microsoft.com/en-au/windows/use-your-mobile-device-s-camera-7d3f9cc3-ccdc-44be-9b49-015d2cb3be05) and [Windows network camera support](https://learn.microsoft.com/en-us/windows-hardware/drivers/stream/network-cameras). These explain system video sources; they do not establish Bluetooth as a generic webcam transport.

If distributing a future standalone binary, include the actual dependency license
files belonging to that build. This source release does not imply permission to
redistribute third-party sample photos, datasets or model weights.
