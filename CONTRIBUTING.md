# Contributing

Use Python 3.10+ with Tk, create a local environment and install requirements.txt.
Run `python tests/run_tests.py`. It uses isolated temporary settings; ordinary tests
do not open the webcam, download models or install GPU runtimes.

For an actual camera issue, report OS, camera/backend, requested and measured
resolution/FPS, model and provider, whether filters were on, and aggregate timing.
Do not attach personal camera footage, network credentials or complete private paths
unless you deliberately intend to share them. A small synthetic reproduction is
preferred when it reproduces the problem.

Changes should preserve the UI-independent packet contract, same-frame preview,
bounded capture lifetime, honest measured/held labels and bilingual UI. Include a
test for the behavior being fixed and an entry in CHANGELOG.md. Explain reuse and
keep upstream notices; distinguish implemented behavior from future plans.

The project is a learning/research workbench. Contributions to real camera tests,
latency measurement, person ROI selection and future game adapters are welcome.

## Contact / 联系

Email / 邮箱：[lexzeonstudio@gmail.com](mailto:lexzeonstudio@gmail.com)。
