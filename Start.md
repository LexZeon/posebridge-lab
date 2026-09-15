# 启动 PoseBridge Lab

双击 **[Start.cmd](Start.cmd)**。当前版本 **0.1.0-alpha.1**，这是与 OSR 分开的项目。
首次取得源码、没有本项目运行环境时，先安装 Python 3.10+（带 Tk），双击 **[Setup.cmd](Setup.cmd)**，完成后再启动。

1. 按你的使用习惯先点“恢复默认”：默认 2D、640 处理最长边、申请 640×480 / 60 FPS、CPU 4 线程、低延迟预设。异常过滤与微抖平滑开启，光流和卡尔曼关闭。
2. 在“输入来源”点“检测输入来源”，选择系统摄像头。打不开时换 DSHOW / MSMF 后重新检测；核对系统权限或是否被其他软件占用。
3. 在“模型 / GPU”点“下载 / 检测模型”，默认下载与 OSR 相同的 RTMPose-s Body7 2D 模型。也可选择已有的对应 ONNX；3D 使用独立路径并一直标为实验未调试。
4. 点“开始摄像头分析”。没有模型时只显示摄像头，并提示缺少模型，不生成虚假骨架。
5. 点“人物模型预览”。模型绑定同帧姿态；灰色关节表示短时保持。2D 的立体外形只用于显示，不是深度测量。
6. 左侧“效果优化”调整开关和滑块；分析参数在下次开始生效。镜像、编号与叠加仅改变显示，不修改导出数据。
7. 要使用 GPU，选择 CUDA（NVIDIA）或 DirectML（Windows GPU），点“一键配置 GPU”。软件会检测、下载到私有目录、验证；成功后重启 Start.cmd。驱动不可用时不能通过下载运行库修复驱动。

手机／无线摄像头：先由系统或手机摄像头应用提供视频来源，再刷新列表；或者选择 Network 输入 RTSP / HTTP(S) 地址。地址不写进配置。蓝牙配对本身不是通用视频传输协议。

“关键点数据”可导出当前姿态 JSON，文件没有摄像头图像。默认不录像、不联网发送姿态。模型、GPU 运行库和设置分别留在用户的 PoseBridgeLab 私有目录，未加入公开源码。

关闭窗口会先停止摄像头并取消后台任务。摄像头读取卡住时可结束本软件的采集子进程；重新开始会创建新会话。

## Developer checks

- `python tests/run_tests.py`：隔离设置后运行回归测试，不连接摄像头、不下载 GPU 包。
- `Start.cmd --smoke --language zh` / `en`：仅检查界面启动，不保存设置。
- `Start.cmd --demo`：合成动作演示，不调用摄像头／模型。
- `python tools/check_camera.py --seconds 5`：明确打开真实摄像头，只输出统计，不保存图像或个人设置。

本机的完整路径和接手提示词位于 `AI_HANDOFF.local.md`（本地文件，Git 忽略）。公开开发说明见 [docs/AI_HANDOFF.md](docs/AI_HANDOFF.md)。

## English

Double-click Setup.cmd once, then Start.cmd. Detect a camera, download the 2D model and start. Use Avatar preview for the bound mannequin. Analysis options take effect on the next run; display-only mirror/IDs/overlay are live. GPU setup is private and requires restarting the app. 3D is an unvalidated experimental option. No camera video is recorded or uploaded by default.
