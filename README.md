# 星伴 Xingban

一个面向 Windows 的 AI 女友桌面应用原型。支持中文聊天、自定义成年角色、主动收藏的长期记忆、本地聊天记录、JSON 导出、互动快捷动作和系统语音朗读。没有密钥时为明确标注的规则演示，并非真正的模型对话。

## 开发运行

需要 Node.js 22 或以上：

```sh
npm ci
npm test
npm start
```

在「角色与连接」填写兼容 OpenAI **Chat Completions** 的接口地址（例如 `https://api.openai.com/v1`）、模型名称和 API Key。地址应包含供应商要求的路径前缀，但不要包含 `/chat/completions`。不支持仅提供 Responses 协议的接口。API 调用费用由供应商收取。

## 获取 Windows 安装包

已提供便携 ZIP 构建命令 `npm run dist:win:zip -- --publish never`。解压整个 ZIP 后双击 `星伴.exe`，不能只复制 exe 文件。当前云环境已生成 Windows 程序文件；安装向导构建因缺少 Wine 未完成，使用下述 Windows 工作流生成。

在 Windows 上运行：

```powershell
npm ci
npm test
npm run dist:win -- --publish never
```

安装包输出到 `release/`。也可以在 GitHub 的 Actions 中手动运行 **Windows installer** 工作流，从产物 `Xingban-Windows-x64` 下载 exe；推送 `v*` 标签时，此工作流会自动创建 GitHub Release 并附上安装包和便携 ZIP；手动运行只生成 Actions 产物。当前安装包未签名，Windows 可能提示未知发布者。尚未执行 Windows 实机安装验收。

## 数据与隐私

聊天、角色和记忆保存在 Electron 的用户数据目录，Windows 通常为 `%APPDATA%/星伴` 或 `%APPDATA%/xingban`，以实际 Electron userData 路径为准。API Key 使用 Electron safeStorage 的系统加密功能保存，渲染页面无法读取密钥。聊天和记忆本身未加密，导出文件也未加密。密钥不能直接迁移到另一台电脑。

每次模型请求会发送角色提示词、全部已收藏记忆和最近 40 条消息；历史消息仍保留在本机。记忆由用户明确收藏，不会自动推断或偷偷收集。删除记忆不会自动删除原聊天记录，可另行清空对话。系统朗读取决于已安装语音，某些语音可能使用系统在线服务；这不是实时语音通话。

## 与 Cortico 的关系

参考 [Pal-AI-Lab/Cortico](https://github.com/Pal-AI-Lab/Cortico)（研究版本 `514ae61364bb534816e2d3e2eeb3ab7197c1fb34`）的 Core / Persona / Memory / World 分层思路。本项目独立实现了较小的聊天工作流，**未集成 Cortico 引擎**，也不具备它完整的事件流、多 World、自主后台认知、分层记忆整理或扩展系统。没有复制其源代码。

- `src/core.cjs`：角色上下文、记忆注入和模型调用
- `src/main.cjs`：桌面生命周期、系统密钥加密与原子数据写入
- `src/preload.cjs`：受限 IPC 接口
- `src/renderer.js`：桌面交互和语音朗读

当前头像为 CSS 绘制的静态角色，尚无 Live2D、嘴型同步、语音识别、主动消息或自动更新。后续可以在现有 IPC 与模型模块之间加入 Cortico 适配层。
