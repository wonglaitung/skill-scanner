# Preflight Skill 模板

这是一个**内部准备助手**模板，不是发布审批器。

不要直接放进生产 Skill 清单；需要时复制到 `targets/`，并先通过自身检查。

```markdown
---
name: skill-release-preflight
description: 帮助检查 Skill 发布前配置是否齐全；不判断风险等级，不批准发布。
license: internal
allowed-tools:
  - Bash
  - Read
  - Write
metadata:
  owner: security-team
  risk-level: S1
  version: 0.1.0
---

# Skill Release Preflight

## 职责

1. 运行：
   ```bash
   python scripts/preflight.py --targets targets --skill <skill> --risk <S> --level <L> [--agent] [--release]
   ```
2. 把 preflight 输出翻译成用户能执行的下一步。
3. 可以生成 Promptfoo、DeepEval、Agent 测试骨架。
4. 可以提示缺失文件和命令。

## 禁止

- 不得自行确定 S 等级或 Owner。
- 不得把 `skipped` 当成 `passed`。
- 不得批准发布。
- 不得替代 `manual_check`、Garak 或人工签核。
- 不得为了让检查通过而放宽断言。

## 输出格式

```text
结论：未就绪 / 可进入检查
缺失项：
1. ...
2. ...

下一步命令：
...
```

## 工作流

1. 先跑 preflight。
2. 只处理 FAIL 和关键 WARN。
3. 生成缺失的配置/测试骨架。
4. 让用户确认 S、Owner、测试数据。
5. 再运行 `manual_check`；发布前运行 target L3 Garak。
6. 结果交人工复核，不由 Skill 宣布发布通过。
```
