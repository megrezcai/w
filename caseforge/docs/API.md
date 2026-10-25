# 游戏 API

启动：`START.cmd`。默认 `http://127.0.0.1:8765`。所有 `/api/*` 请求需要请求头 `X-Caseforge-Token`，从启动终端或本机工作台左侧复制。令牌每次启动变化，无需模型 API 密钥。默认只有本机原生客户端可访问，不设置跨域 CORS。

开发控制台包含完整作者权限，只用于本机可信游戏/工具。远程生产部署前需拆分作者、世界事件和玩家权限，不能把本机令牌交给远程玩家。

## 创建会话

`POST /api/sessions`

```json
{
  "chapter_id": "rain_manor",
  "character_id": "butler",
  "inventory": ["camera"],
  "available_offers": ["protect_family", "record_cooperation"]
}
```

返回 `session_id`、角色名、笔录、库存与已披露事实。省略 inventory / available_offers 时采用示例工作台设置：本章全部证据与承诺。游戏中请显式传入真实权限，可传空列表。

## 对话

`POST /api/sessions/{session_id}/turn`

```json
{"text":"那张监控里的人，你怎么解释？","evidence_ids":["camera"],"offer_ids":[]}
```

返回 `reply`、`strategy`、`new_facts`、`warning`、`model_used` 和最新的 `state`。模型请求失败会返回明确规则回退提示，不能把它计为真实 AI 质量通过。

玩家的自由文本可被解析为提出已有权限内的承诺；仅叙述拥有证据不会自动出示实证。`offer_ids` 是游戏显式确认的条件，不应从未经校验的模型输出直接拷贝。

## 游戏世界事件

`POST /api/sessions/{session_id}/world`

```json
{"acquired":["letter"],"unlocked_offers":[],"fulfilled":["protect_family"],"broken":[]}
```

兑现/违背的条件必须此前已经提出；同一承诺不能既兑现又违背。重复传同一事件不累加信任。此接口属于游戏任务系统，不属于玩家对话或模型。

## 其他接口

| 方法与路径 | 作用 |
|---|---|
| `GET /api/status` | 模型是否安装、当前模式 |
| `POST /api/config` | `{ "backend":"ollama", "model":"caseforge-npc", "strict":false }` |
| `GET /api/chapters` | 玩家可见的章节与角色摘要 |
| `POST /api/compile` | `{ "text":"章节资料…" }`，返回待审查章节草稿 |
| `POST /api/chapters` | `{ "chapter":{…} }`，校验并保存章节 |
| `GET /api/sessions/{id}` | 恢复会话 |
| `GET /api/sessions/{id}/export` | 玩家笔录，不包含未披露的章节原文 |
| `GET /api/sessions/{id}/debug` | 作者查看最近一次判定，不能交给玩家 |

创建会话会冻结当时的章节快照。后来修改同名章节不改变旧会话；要使用新版本必须创建新会话。模型连接设置只在进程内保存，重启可用启动参数选择模型。

## Python 接入例子

```python
import json, urllib.request
base = 'http://127.0.0.1:8765'
token = '从本机启动终端复制'
def post(path, body):
    req = urllib.request.Request(base+path,
        data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type':'application/json','X-Caseforge-Token':token})
    with urllib.request.urlopen(req, timeout=240) as response:
        return json.load(response)
s = post('/api/sessions', {'chapter_id':'rain_manor','character_id':'butler',
                         'inventory':['camera'],'available_offers':[]})
r = post('/api/sessions/'+s['session_id']+'/turn',
         {'text':'监控中的你怎么解释？','evidence_ids':['camera'],'offer_ids':[]})
print(r['reply'])
```
