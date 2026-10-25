# 外部组件

源码包中的应用代码独立实现，采用 MIT。参考设计的仓库与链接见主 README，没有包含其运行代码。

Windows exe 由 CPython 与 PyInstaller 构建。构建脚本在可取得时随包复制 Python LICENSE 和 PyInstaller COPYING；PyInstaller 使用 GPL 与允许分发构建应用的 bootloader 例外。Ollama 不包含在包内，需要用户另行安装。Qwen3 模型权重不包含在包内，需要首次下载，须遵循所选模型自身许可证。

- Python：https://docs.python.org/3/license.html
- PyInstaller：https://pyinstaller.org/en/stable/license.html
- Ollama：https://github.com/ollama/ollama/blob/main/LICENSE
- Qwen3：https://github.com/QwenLM/Qwen3
