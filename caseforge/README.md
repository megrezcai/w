# CaseForge · 本地审问与谈判 NPC

面向案件模拟器的可运行组件：加载章节和角色资料，用本地语言模型理解自由提问，再由游戏规则根据**立场、弱点、利益、证据和承诺**决定回避、反问、开价、改口或披露情报。

这是基于 **Qwen3 + Ollama 的应用与模型配置**，不是从零训练或微调后的新权重。仓库不含几 GB 的基础权重，首次运行时由安装器下载到你自己的电脑。下载完成后，正常推理不需要联网，也不需要付费 API 或密钥。

## Windows 最快开始

1. 从 [Ollama 官方网站](https://ollama.com/download/windows) 安装并启动 Ollama。
2. 解压完整的 CaseForge Windows ZIP 到你有写入权限的目录，比如 `D:\Games\CaseForge`。
3. 双击 **`SETUP-MODEL.cmd`**：选 `1` 使用 Qwen3 8B；电脑内存较少时可选 `2` 使用 4B。首次会下载数 GB，请等待下载与 `ollama create` 完成。
4. 双击 **`START.cmd`**，浏览器自动打开 `http://127.0.0.1:8765`。看到“本地模型就绪”后开始审问。
5. 选择“雨夜庄园”，点击“开始新审问”。右侧勾选证据/条件，输入任何问法。

**Windows ZIP 中若包含 `CaseForge.exe`，无需安装 Python。** 如果你下载的是源码包，则需要 [Python 3.10+](https://www.python.org/downloads/windows/)，安装时勾选 Add python.exe to PATH。源码本身没有 pip 运行依赖。

仅想先看规则和界面：双击 `DEMO.cmd`。该模式明确标注“非 AI”，只识别少量示例表达，不能用它评价模型的语义理解能力。

### 下载与构建

- Windows 成品：仓库右侧 Releases 中的 **CaseForge v0.1.0**，选择 `CaseForge-Windows-x64.zip`。
- 如果 Release 尚未生成，前往 Actions 的 **CaseForge Windows** 查看构建状态，成功后可下载同名产物。
- 源码 ZIP 可直接下载本分支，进入 `caseforge/` 使用上述脚本。
- Windows 本机也可构建：`py -3 -m pip install pyinstaller==6.16.0`，再运行 `py -3 build_windows.py`。

## 已有功能

- 中文自由提问与间接表达的语义分类；角色会选择否认、试探、提出交换、承认或坚持底线。
- 每个角色独立的利益权重、秘密、初始谎言和披露前置条件。
- 真实证据由游戏传入 ID，玩家口头声称“有监控”不能凭空增加筹码。
- 同一证据、同一承诺不重复累计收益；反复示好也不能无限刷信任。
- 承诺有权限、提出、兑现和违背之分。违约降低后续合作意愿。
- 未解锁的秘密原文不进入语义解析器或台词模型上下文；披露的案件事实由程序追加。
- SQLite 保存每次对话、已承认事实、证据和承诺。重启后可恢复，修改章节不改写已有会话。
- 支持 TXT/Markdown 剧本整理为可编辑 JSON，再经作者审查与交叉引用校验后加载。
- 本机 HTTP API，可接入 Unity、Unreal、Godot 或其他游戏。附 Unity C# 示例。

## 两种台词模式

**自然模式（默认）**：模型理解意图，并生成符合人设的短回应；案件陈述由程序追加。自由对话更灵活，但生成的铺垫仍可能出现不恰当的暗示或编造。字面检查不能保证阻止所有幻觉或提示注入。

**严格台词**：模型只分析玩家意图，角色回答采用作者审定台词，案件事实只从章节取值。适合先保证推理游戏的一致性；表达变化会减少。仍须审查模型对话题和承诺的理解是否正确。

导入器会完整读取作者资料，但它是独立的编剧步骤，不会与游戏中的 NPC 共用聊天记忆。请检查 `public_brief`、`persona`、`public_knowledge`、话题标签和证据描述是否提前写出了秘密。系统无法自动判断所有语义泄密。

## 实际跑通示例

规则演示和真实模型均可按以下路径检验；自然问法的识别效果取决于模型：

1. 勾选“走廊监控”，问“你离开过厨房吗？” → 承认走过走廊。
2. 勾选“截获信”，问“你看见谁？” → 要求保护妹妹。
3. 勾选“安排妹妹的安全住处”，继续问“你看见谁？” → 供出所见人物。
4. 问“凶器藏在哪？” → 要求如实记录配合情况。
5. 勾选“如实记录主动配合”，再次询问 → 得到物品藏匿位置。

右侧承诺下有“模拟兑现/违约”，用于作者测试。正式游戏应由任务系统调用 `/world` 传入真实事件，不能让模型自行宣布兑现。示例工作台默认持有全部证据和承诺权限；游戏接入时请传入实际库存与权限。

## 导入自己的章节

可用 `chapters/你的章节模板.md` 写作。界面里粘贴文本 → “让本地模型整理剧本” → 审查 JSON → “校验并加载章节” → 开始新审问。无需训练或重新下载模型。

单次支持 30～12000 字文本，超出会拒绝，不会悄悄丢掉末尾。自动整理时使用 24576-token 上下文，显存/内存占用高于正常对话。长章请按审问场景拆分。直接导入 JSON 不调用模型。

完整格式见 `chapters/chapter.schema.json`，设计说明见 [章节与谈判规则](docs/DESIGN.md)。校验命令：

```powershell
py -3 run.py --validate chapters\rain_manor.json
```

## 硬件与替换模型

建议从 16GB 系统内存和 Qwen3 8B 的量化版本开始试用。有合适显卡会快很多；CPU 可以推理，但首轮加载、长章导入和两次模型调用可能明显等待。上述为选型建议，不是本机实测配置或速度保证。

- 资源较少：`py -3 setup_model.py --base qwen3:4b`
- 内存足够再尝试 14B：`py -3 setup_model.py --base qwen3:14b`
- 已有 Ollama 模型：界面修改模型名称，不需要创建专用名称。
- 端口冲突：`START.cmd --port 8766`
- 已有本地 Ollama 其他端口：`START.cmd --ollama-url http://127.0.0.1:11435`
- macOS/Linux：安装 Python 和 Ollama 后，执行 `python3 setup_model.py`、`python3 run.py`。

配置专用名默认是 `caseforge-npc`。只直接运行 `ollama run caseforge-npc` 并不能获得证据、存档和利益规则，游戏要调用此组件 API。

## 数据与接口

`data/` 保存本机章节、SQLite 会话和生成的 Modelfile；不会提交到 Git。开发控制台只监听本机，默认不对局域网开放。它是作者工具，包含章节编辑和调试入口，不应直接作为面向不可信玩家的生产服务。接口使用每次启动生成的令牌，见控制台输出或左侧“游戏接入令牌”。

详见 [API 文档](docs/API.md) 和 [Unity 示例](integrations/CaseForgeClient.cs)。

## 参考项目与许可证

已阅读以下公开仓库资料，参考设计而独立实现，没有复制它们的运行源码：

- [undreamai/LLMUnity](https://github.com/undreamai/LLMUnity)：本地角色提示、结构化输出、角色历史以及 KnowledgeBaseGame 示例。Apache-2.0。
- [google/mysteryofthreebots](https://github.com/google/mysteryofthreebots)：按人物可知范围组织侦探问答。它使用句向量匹配，且仓库已归档，不是本项目的生成模型后端。Apache-2.0。
- [ollama/ollama](https://github.com/ollama/ollama)：本地推理服务、JSON Schema 输出与 Modelfile。MIT。
- [QwenLM/Qwen3](https://github.com/QwenLM/Qwen3)：默认基础模型及本地运行说明。部署基础权重时须同时遵守所选模型的许可证。

本项目原创代码采用 MIT，详见 LICENSE。源码包不包含上述项目或基础模型权重。

## 验证范围

`python -m unittest discover -s tests -v` 覆盖谈判进程、底线、去重、游戏库存、承诺事件、秘密上下文隔离、接口协议、存档与章节快照。自动化测试中的模型使用替身，只证明程序逻辑与协议，不证明真实模型的谈判质量。

本次开发环境为 Linux，无 Ollama、GPU 或已下载权重，未执行 Qwen3 真实推理与真人对话质量验收。Windows 工作流负责运行同一组测试、构建并启动 exe 做接口冒烟测试；它也不下载基础权重或测量推理速度。上线前请在目标 Windows 电脑完成模型下载，使用自己的章节测试自由表达、跨轮一致性和边界问法。
