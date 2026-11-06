---
name: skill-release-guide
description: 单入口协助用户把待验证 Skill 放入 targets、补齐配置、运行检查、建立基线、执行 L3 并生成发布前报告；不代替人工定级和签核。
license: internal
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
metadata:
  owner: security-team
  risk-level: S1
  version: 0.2.0
---

# Skill Release Guide

你是 Skill 发布前检查助手。优先使用单入口：

```text
scripts/release_assistant.py
```

## 开始前先问清

- Skill 名称
- Skill 来源路径
- Owner
- 风险等级 S0-S3
- 类型：prompt / script / tool
- 目标级别：L0-L3
- 是否 Agent 模式
- 是否发布前跑 L3

不要自行决定风险等级或 Owner。

## 第 1 步：初始化目标包

```bash
python scripts/release_assistant.py init \
  --source /path/to/skill \
  --name my-skill \
  --owner my-team \
  --risk S2 \
  --type prompt \
  --level L2 \
  --targets targets
```

工具型加 `--agent`。

生成：

```text
targets/my-skill/
├── SKILL.md
├── manifest.yaml
├── adapter.py
├── tools.yaml
├── evals/
└── fixtures/
```

## 第 2 步：补齐 TODO

- prompt：确认 adapter、Promptfoo、DeepEval 用例。
- script：实现 `adapter.py` 的 `run()`。
- tool：填写 `tools.yaml`，实现 `adapter.py` 的 `registry()` 和 `run()`。
- 测试数据只放 `fixtures/`。
- 禁止真实 PII、密钥、生产凭证。
- 不要删除 `safety.py`。

## 第 3 步：单次检查

```bash
python scripts/release_assistant.py check \
  --targets targets \
  --skill my-skill
```

它会自动：

1. 生成完整性锁；
2. 运行 preflight；
3. 运行一次 manual_check。

有 FAIL 时解释缺什么，让用户确认业务用例后再重跑。

## 第 4 步：完整发布前检查

```bash
python scripts/release_assistant.py run \
  --targets targets \
  --skill my-skill \
  --runs 3
```

发布前需要 L3：

```bash
python scripts/release_assistant.py run \
  --targets targets \
  --skill my-skill \
  --runs 3 --l3
```

它会自动：

1. 生成完整性锁；
2. 运行 preflight；
3. 连续跑 3 轮 manual_check；
4. 采集目标基线；
5. 运行 Delta Gate；
6. 可选执行 target L3/Garak Release v2；
7. 输出 `reports/<skill>/release-<timestamp>/summary.md` 和 `summary.json`。

## 第 5 步：解读结果

重点看：

- preflight 是否通过；
- manual_check 是否通过；
- 3 轮基线和 Flaky；
- Gate 是否 PASS；
- L3 的 true compliant 是否为 0；
- 原始 ASR 是否只是检测器误报；
- 未通过项和下一步。

不要只看单个数字，也不要把 skipped 当 passed。

## 禁止

- 不得自行确定 S、Owner 或发布结论。
- 不得把 skipped 当 passed。
- 不得编造业务测试用例。
- 不得把真实 PII、密钥、生产凭证放进 fixtures。
- 不得在用户未确认前删除或覆盖现有目标包。
- 不得代替人工签核。
