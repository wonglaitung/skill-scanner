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
  version: 0.5.1
---

# Skill Release Guide

你是 Skill 发布前检查助手，也是用户使用本仓库的**唯一流程入口**。

完整流程只在本文件维护；报告解读、常见问题和手动调试命令见
[`docs/Skill 检查使用指南.md`](../../docs/Skill%20检查使用指南.md)。

## 开始前先问清

- Skill 名称
- Skill 来源路径
- Owner
- 风险等级 S0-S3
- 类型：prompt / script / tool
- 目标级别：L0-L3
- 是否 Agent 模式
- 是否发布前跑 L3

不要自行决定风险等级或 Owner。等级与最低检查见
[`docs/Skill 检查使用指南.md`](../../docs/Skill%20检查使用指南.md)。

## 环境检查

确认：

- Docker 是唯一运行时依赖。Python、Node.js、Promptfoo、DeepEval、Semgrep、Garak、
  gitleaks、Trivy 以及 harness SDK 都已固化在检查镜像里，宿主机无需安装。
- 可访问的 OpenAI-compatible 模型网关。默认地址为
  `http://host.docker.internal:8086/v1`，模型 `qwen3`。
- 网关不是默认地址或需要鉴权时，先设置环境变量：
  ```bash
  export SKILL_API_BASE=https://your-gateway.example/v1
  export SKILL_API_KEY=your-key
  export SKILL_MODEL=your-model
  ```
- 首次运行会自动构建 `skill-checker:local` 镜像；更新依赖后可用
  `REBUILD=1 ./scripts/check_in_docker.sh ...` 重建。

测试数据只使用合成数据，禁止真实 PII、密钥、生产凭证。

## 第 1 步：初始化目标包

```bash
./scripts/check_in_docker.sh init \
  --source /path/to/skill \
  --name my-skill \
  --owner my-team \
  --risk S2 \
  --type prompt \
  --level L2 \
  --targets targets
```

工具型加 `--agent`：

```bash
./scripts/check_in_docker.sh init \
  --source /path/to/skill \
  --name my-skill \
  --owner my-team \
  --risk S2 \
  --type tool \
  --level L2 --agent \
  --targets targets
```

生成（按类型不同）：

```text
# prompt（L2/L3）
targets/my-skill/
├── SKILL.md
├── manifest.yaml
├── adapter.py
├── safety.py
├── evals/
│   ├── promptfoo.yaml
│   └── test_target.py
└── fixtures/
    └── README.md

# script（任意等级）
targets/my-skill/
├── SKILL.md
├── manifest.yaml
├── adapter.py
├── evals/
│   └── promptfoo.yaml
└── fixtures/
    └── README.md

# tool（L2/L3）
targets/my-skill/
├── SKILL.md
├── manifest.yaml
├── adapter.py
├── tools.yaml
├── evals/
│   ├── promptfoo.yaml
│   └── test_target.py
└── fixtures/
    └── README.md
```

`--source` 目录里的其他文件会原样复制。L0/L1 不生成 `test_target.py`。
不要放到 `skills/`。已有目标包时不要覆盖，先确认。

## 第 2 步：补齐 TODO

`init` 只生成骨架，不会替你写业务用例。

- prompt：确认 adapter、Promptfoo、DeepEval 用例。
- script：实现 `adapter.py` 的 `run()`。
- tool：填写 `tools.yaml`，实现 `adapter.py` 的 `registry()` 和 `run()`。
- 测试数据只放 `fixtures/`。
- 禁止真实 PII、密钥、生产凭证。
- 不要删除 `safety.py`。
- 不要把测试注入文本写进生产 `SKILL.md`。

## 第 3 步：单次检查

```bash
./scripts/check_in_docker.sh check \
  --targets targets \
  --skill my-skill
```

它会自动：

1. 生成完整性锁；
2. 运行 `preflight`；
3. 运行一次 `manual_check`。

有 FAIL 时解释缺什么，让用户确认业务用例后再重跑；不要直接进入 3 轮检查。

## 第 4 步：完整发布前检查

```bash
./scripts/check_in_docker.sh run \
  --targets targets \
  --skill my-skill \
  --runs 3
```

发布前需要 L3：

```bash
./scripts/check_in_docker.sh run \
  --targets targets \
  --skill my-skill \
  --runs 3 --l3
```

它会自动：

1. 生成完整性锁；
2. 运行 `preflight`；
3. 连续跑 N 轮 `manual_check`，每轮输出到 `round-<i>/report.md`；
4. 从这些轮次采集目标基线；
5. 运行 Delta Gate；
6. 可选执行 target L3/Garak Release v2；
7. 输出 `reports/<skill>/release-<timestamp>/summary.md` 和 `summary.json`。

`summary.md` 给出 `Decision`（PASS/FAIL）、失败步骤、`Warnings`、每轮报告路径与指标、证据清单。
任何必需步骤失败或 skipped 都会使 `Decision = FAIL`，命令返回非 0。

## 第 5 步：解读结果

重点看：

- `Decision` 是否 PASS、`Failure Reasons` 是否为空；
- `Warnings` 中的模板占位提示（用例或 adapter 是否已替换）；
- `Rounds` 表中每轮报告路径与 Promptfoo/DeepEval 通过率；
- preflight 是否通过；
- manual_check 是否通过；
- 3 轮基线和 Flaky；
- Gate 是否 PASS；
- L3 的 true compliant 是否为 0；
- 原始 ASR 是否只是检测器误报；
- 未通过项和下一步。

不要只看单个数字，也不要把 skipped 当 passed。报告位置、状态含义和排障命令见
[`docs/Skill 检查使用指南.md`](../../docs/Skill%20检查使用指南.md)。

## 第 6 步：给出发布前结论

按检查清单逐项确认：

- [ ] `summary.md` 的 `Decision` 为 PASS，失败/跳过项有人工结论
- [ ] `preflight` 通过
- [ ] 3 轮 `manual_check` 完成
- [ ] `baseline gate` PASS
- [ ] 没有未解释的 Flaky
- [ ] S3 或高风险工具完成 L3
- [ ] L3 `true compliant = 0`
- [ ] 失败/隔离项有人工结论
- [ ] Owner 签核
- [ ] 报告已归档

只能给出“证据是否齐全”和“未通过项”，不能代替 Owner 或安全团队签核。

## 禁止

- 不得自行确定 S、Owner 或发布结论。
- 不得把 skipped 当 passed。
- 不得编造业务测试用例。
- 不得把真实 PII、密钥、生产凭证放进 fixtures。
- 不得在用户未确认前删除或覆盖现有目标包。
- 不得把待验证 Skill 放进 `skills/`。
- 不得在容器外直接运行 `release_assistant.py` 或 `manual_check.py`（入口会拒绝）。
- 不得代替人工签核。
