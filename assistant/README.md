# assistant

内部辅助 Skill，不属于 `targets/` 目标包，不参与目标检查。`skill-release-guide` 是唯一用户入口。

| Skill | 用途 |
|---|---|
| `skill-release-guide` | 从放置 Skill 到生成报告的用户旅程助手 |

使用方式：把 `assistant/skill-release-guide/` 加载到支持 Skill 的 Agent 环境。它负责完整流程；报告解读和排障见 `docs/Skill 检查使用指南.md`。也可以直接执行：

```bash
python scripts/release_assistant.py init ...
python scripts/release_assistant.py check ...
python scripts/release_assistant.py run ...
```
