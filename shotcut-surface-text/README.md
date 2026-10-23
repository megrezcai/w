# Shotcut 表面贴字 · Surface Text

面向 Windows x64 的**原生透视滤镜 + 本地平面跟踪助手**。适合把字幕贴在灯箱、招牌、屏幕、墙面、包装盒的某一个平面上，并随镜头运动。

这不是只调整位置的普通字幕跟踪：原生 `frei0r.surfacepin` 滤镜对透明字幕图层执行真正的投影变换；助手通过特征点、光流、RANSAC 单应矩阵和参考帧匹配产生逐帧四角数据。没有云端推理、模型下载或 API 密钥。

## Windows：完整解压，先安装再启动

1. 使用官方 **Windows x64、Qt 6 版本 Shotcut**；推荐把官方便携 ZIP 完整解压到你有写权限的目录。
2. 关闭 Shotcut，双击 **`Install-Plugin.cmd`**，在选择框中选中 `shotcut.exe`。重启后，在视频滤镜里搜索 **“表面贴字”**。
3. 双击 **`Start-Assistant.cmd`**。助手会在默认浏览器打开中文操作界面。请保持命令窗口开启。

Windows 完整部署包已带 Python 3.12.10、OpenCV、NumPy 和 Pillow，不需要另外安装 Python、开发工具或编译滤镜。运行不需要联网。使用 Edge、Chrome 等现代浏览器。

**部署结构限制：**安装器要求程序目录内已有 `lib/frei0r-1` 和 `share/shotcut/qml/filters`；不支持 Microsoft Store 沙箱或重排过目录的第三方包。安装目录不可写时会停止，请改用可写目录中的官方便携版。没有提权安装步骤。

## 操作：选平面、输入文字、自动跟随

1. **打开视频。**拖入文件或点击“打开本地视频”。数据只是从浏览器交给同一台电脑上的助手，不会上传到外网。支持 MP4/MOV/MKV/AVI/M4V/WebM，文件不超过 8 GB。
2. **选清晰参考帧。**在帧滑块或帧编号里定位。按 **左上 → 右上 → 右下 → 左下** 点出同一个物体表面的四角。把物理边缘包括进来；不要只框一行已有文字，也不要跨过盒子的两张不同平面。
3. 点击 **“保存当前四角”**，输入字幕，调整颜色、字号、垂直位置。文字比例不合适时微调“表面宽高比”；自动值是估计值，单目画面不能确定表面的真实物理尺寸。
4. 点击 **“开始自动跟踪”**。分析从最早参考帧向后进行，之前的字幕隐藏。可切换“预览字幕”、逐帧检查。
5. 如果丢失，在之后清晰的一帧重新选四角并保存修正点，然后重新分析。助手不会在不确定的情况下自动把文字吸附到另一个目标。
6. 点击 **“下载可编辑 Shotcut 工程”**，完整解压下载的 ZIP，用 Shotcut 打开 `surface-text.mlt`。

## 在 Shotcut 中继续剪辑

- V1 为原视频与原声；V2 为独立透明字幕 PNG，带逐帧透视和可见度关键帧。
- 字幕未烧录进原视频。可调整字幕轨道的四角参数，继续剪辑并用 Shotcut 导出视频。
- **文字内容不是 Shotcut 文本编辑器内的动态文本。**它被渲染为抗锯齿透明图层；修改文案、颜色或字号后，应在助手中重新生成。项目附带 `subtitle.txt` 记录原文。
- 单独应用滤镜时必须对透明字幕/图形层操作，不能放在原视频上，否则整幅视频也会被变形。
- 可在 Shotcut 本滤镜面板的四角输入框修改当前帧坐标，也可在关键帧面板调整。
- 助手的“复制跟踪数据”可将 JSON 粘贴到滤镜面板重新导入；项目分辨率、帧率及完整片段长度必须一致。先完成导入，再剪切、变速或改变视频模式。
- 工程 ZIP **包含原视频副本**，可独立移动；需保留整份目录。大视频会占用相应临时空间和输出空间。正常退出会清理本次临时文件，请先下载结果；强行关闭命令窗口可能留下系统临时目录中的 `shotcut-surface-text-*` 文件夹。

## 能力边界

这是**单平面透视跟踪**，不是任意物体的三维重建。对箱子的一张面、灯箱正面适用；圆柱、球面、布料变形、转到物体背面需要别的方法。它不会识别物体语义或自动给整件立体物体分面。

严重遮挡、无纹理、运动模糊、画面切换和离开画面可能导致丢失。低置信度后隐藏字幕，直到人工修正点；即使状态有效也应逐帧检查，不能保证所有素材自动精确。

没有前景遮挡分割：人手从文字前经过时仍需要额外遮罩。也没有自动去除原画面已烧录文字、镜头畸变校正、光照/反射匹配或运动模糊合成。你的示例保留原有上方文字，在灯箱下方添加新文字。

输入应为**恒定帧率、方形像素、方向已烘焙**的素材。手机可变帧率或带旋转元数据的视频请先在 Shotcut 转成恒定帧率、无旋转标记的编辑格式，再跟踪。工具按解码帧和报告的固定帧率生成工程，不自动检测所有 VFR 情况。原生滤镜处理 RGBA 8 位 SDR；不用于保持 HDR/10 位色彩精度，也未验证 GPU 处理模式。

## 安装位置、更新和删除

安装器只添加或更新自身文件：

```text
Shotcut/lib/frei0r-1/surfacepin.dll
Shotcut/share/shotcut/qml/filters/surface_text/{meta.qml,ui.qml,Track.js}
```

更新前备份旧 DLL 为带时间和随机标识的 `.surface-text-backup-*` 文件；旧界面备份在 `Shotcut/surface-text-backups`。不修改 Shotcut 主程序、已有内置滤镜或个人配置。由于安装目录和 DLL 均需写入，安装中断可能留下部分新文件；修复时关闭 Shotcut，再运行安装器，必要时从上述备份恢复。

删除时先关闭 Shotcut，再删除本插件 DLL 和 `surface_text` 界面目录。若存在其他版本覆盖，先检查再删除；已有工程仍依赖插件才能正确渲染。Shotcut 升级可能替换安装目录，需要重新运行安装器。

CMD 对执行策略的覆盖仅作用于本次 PowerShell 进程。脚本源码、滤镜源码和所有许可证随包提供；组织策略仍可能阻止脚本或未签名 DLL。助手只监听本机回环地址，关闭启动窗口即可结束。

## 已执行的验证

- 合成素材：已知投影运动的四角误差小于 2 像素；完全遮挡后隐藏、在人工修正点恢复。
- 原生滤镜：恒等变换逐字节一致；投影标记误差小于 1 像素；透明边缘无黑边；退化四角和隐藏状态输出透明。
- 导入：JavaScript 与 Python 的 9 条参数动画一致，拒绝错误帧率、长度及折叠四角。
- 浏览器实操：打开你的视频、点选四角、自动跟踪、字幕预览、生成含原素材的工程 ZIP。
- 你的视频：1920×1080、24000/1001 fps、87 帧。从第 24 帧到第 86 帧共 63 帧均未触发丢失；这不等于逐像素人工标注精度保证。
- Linux MLT 实际加载本原生滤镜、渲染完整 87 帧，输出包含音轨。Linux Shotcut 25.03.31 已识别滤镜并打开本界面；工程重新保存后的合成也检查过。
- Windows x64 DLL 已交叉编译，导出完整 frei0r 接口，仅依赖系统 KERNEL32/MSVCRT。**尚未在 Windows 实机执行安装器、运行随包 Python 或验收 Shotcut Windows 图形界面**。因此本包为可测试版本，不声称已完成 Windows 实机验收。

## 开发与复现

源码许可为 GPL-3.0-or-later，见 `LICENSE`。第三方运行时与头文件保留各自许可证，见 `THIRD-PARTY.md`。

```sh
python -m pip install -r requirements.txt
gcc -O3 -std=c99 -fPIC -shared native/surfacepin.c -o bin/linux/surfacepin.so -lm
python -m unittest discover -s tests -v
node tests/test-importer.cjs
python -m surface_text.server
```

Windows 原生滤镜可用 MinGW-w64 编译：

```sh
x86_64-w64-mingw32-gcc -O3 -std=c99 -static-libgcc -shared -s native/surfacepin.c -o bin/windows/surfacepin.dll -lm
```

命令行批处理（帧编号从 0 开始）：

```sh
python -m surface_text.cli video.mp4 --anchors anchors.json --text "透视贴合" --output new-project
```

`anchors.json` 格式：

```json
[{"frame":24,"quad":[[565,402],[1516,537],[1519,843],[552,718]]}]
```

`--preview result.mp4` 可额外导出预览，需要系统 FFmpeg。正常助手和 Shotcut 工程导出不依赖独立 FFmpeg 程序。Windows 部署包里的运行时仅供 Windows；Linux 开发者使用自己的 Python 安装 `requirements.txt`。
