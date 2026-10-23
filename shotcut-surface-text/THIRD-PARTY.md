# 第三方来源与许可证

本项目自己的代码采用 GPL-3.0-or-later。没有将 Shotcut 主程序打包进部署 ZIP，也没有修改 Shotcut 源码。

- Shotcut 接口研究基于 https://github.com/mltframework/shotcut 提交 `17d3b13b680a004777eb65d6b4dc64d11b2c3f01`，并在 Debian 提供的 Shotcut 25.03.31 二进制上检查界面加载。QML 界面为本项目编写。
- `native/frei0r.h` 来自 https://github.com/dyne/frei0r 的公开 frei0r ABI 头文件，保留原版权和许可声明；头文件许可见文件开头。
- Windows Python 3.12.10 来自 Python Software Foundation 的官方 NuGet `python` 包： https://api.nuget.org/v3-flatcontainer/python/3.12.10/python.3.12.10.nupkg 。通过 TLS 下载，并核对 NuGet 返回的 SHA-512。随包保留 `runtime/LICENSE.txt`；Python 采用 PSF 许可。源码：https://github.com/python/cpython/tree/v3.12.10 。
- NumPy 2.2.6、opencv-python-headless 4.11.0.86、Pillow 11.2.1 来自 PyPI 官方发布的 Windows x64 wheel，随包保留 `.dist-info` 许可证和第三方声明。包名、版本和文件哈希见 `RUNTIME-ARTIFACTS.json`。
- NumPy 及内含 OpenBLAS、运行库的许可见 `runtime/Lib/site-packages/numpy-2.2.6.dist-info/licenses`；NumPy 源码：https://github.com/numpy/numpy/tree/v2.2.6 。
- OpenCV / Python wheel 的 Apache/BSD 及内含 FFmpeg 等第三方许可见 `runtime/Lib/site-packages/cv2/LICENSE.txt`、`LICENSE-3RD-PARTY.txt` 和对应 `.dist-info`。构建来源：https://github.com/opencv/opencv-python/tree/4.11.0.86 ；内含组件对应源码和构建信息以该发布的构建脚本和第三方许可为准。未修改这些运行库。
- Pillow 的 HPND 和内含组件许可保留在 `runtime/Lib/site-packages/pillow-11.2.1.dist-info/licenses`；源码：https://github.com/python-pillow/Pillow/tree/11.2.1 。

Windows 原生滤镜用 MinGW-w64 GCC 14 编译，未链接 OpenCV、Qt 或编译器的可再分发运行时，仅导入 Windows 系统 KERNEL32/MSVCRT。对应完整源码 `native/surfacepin.c` 随包提供。

字体使用系统已安装的中文字体，不附带或重新分发字体文件。示例视频由用户提供，单独放在用户的示例工程中，不作为插件软件运行库的一部分。
