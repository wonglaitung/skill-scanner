# assistant

内部辅助 Skill，不属于 `targets/` 目标包，不参与目标检查。

| Skill | 用途 |
|---|---|
| `skill-release-guide` | 从放置 Skill 到生成报告的用户旅程助手 |

使用方式：把 `assistant/skill-release-guide/` 加载到支持 Skill 的 Agent 环境，或直接执行：

```bash
python scripts/release_assistant.py init ...
python scripts/release_assistant.py check ...
python scripts/release_assistant.py run ...
```
