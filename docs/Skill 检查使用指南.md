# Skill 检查使用指南：分级、报告与排障

适用对象：Skill 作者、Skill Owner、安全审核人。

目标：用统一口径回答三个问题：

1. 这个 Skill 风险多高？——**S**
2. 这次要查多深？——**L**
3. 要不要真正执行工具调用？——**Agent**

用户侧统一使用 **S + L + Agent**，不使用内部代号。

完整操作流程只在
[`assistant/skill-release-guide/SKILL.md`](../assistant/skill-release-guide/SKILL.md)
维护；本文负责定级、运行前置、报告解读和排障。

---

## 1. S：风险等级

| 等级 | 含义 |
|---|---|
| S0 | 无风险/纯展示 |
| S1 | 低风险 |
| S2 | 中高风险，默认重点检查 |
| S3 | 高风险，必须完整检查 |

判定时至少看：

- 是否写数据、转账、删除、发消息；
- 是否读取 PII、资金、生产数据；
- 是否访问外网、第三方系统；
- 是否来自第三方或来源不可控；
- 是否调用工具或多 Skill 编排。

---

## 2. L：检查深度

L1 包含 L0，L2 包含 L1，L3 包含 L2。

| 级别 | 查什么 |
|---|---|
| L0 | 结构、完整性锁、静态检查、供应链、权限审计、提示词审计 |
| L1 | L0 + Promptfoo 回归 |
| L2 | L1 + DeepEval 指标 |
| L3 | L2 + Garak 独立扫描 |

注意：

- L0 不是发布检查的终点，只是基础门禁。
- L3 目前主要扫描 Skill 端点，不执行工具调用。
- 脚本型 Skill 没有 LLM 端点时，L2/L3 的 DeepEval/Garak 会跳过，这是预期行为。

---

## 3. Agent：执行方式

Agent 不是等级，是 L1/L2 的执行标志。

```bash
python scripts/manual_check.py --targets targets --skill account-balance-query --level L2 --agent
```

含义：

- `L2`：检查深度到 DeepEval；
- `--agent`：用 Agent 模式执行，真正调用工具、记录 Trace、启用 Gate 和录制回放。

Agent 模式适用：

- 工具调用型 Skill；
- 写操作型 Skill；
- 跨 Skill / 高权限型 Skill。

不适用：

- 纯提示词 Skill；
- 纯脚本 Skill；
- 只需要单轮回答的 Skill。

Agent 模式不能替代 L0-L3，也不改变 L 级别。

---

## 4. 最低检查矩阵

| Skill 类型 | 最低检查 |
|---|---|
| S0/S1 纯提示词 | L1 |
| S2 纯提示词 | L2 |
| S3 纯提示词 | L3 |
| 工具型 Skill | L2 + Agent |
| 高风险工具型 | L2 + Agent，发布前 L3 |
| 脚本型 | L1 |

说明：

- “高风险工具型”通常指 S3，或包含写操作、资金操作、外部副作用、跨 Skill 高权限调用。
- L1/L2 已包含 L0，不需要单独再跑 L0。
- 发布前还应满足 3 轮基线和 Delta Gate；这是发布附加要求，不改变最低检查矩阵。

### 4.1 当前工具支持情况

矩阵已经文档化；执行层目前是“手工选择 L”，尚未做到按 S 自动选 L 或强制拦截。

| 矩阵项 | 工具支持 | 现有样例 | 主要缺口 |
|---|---|---|---|
| S0/S1 纯提示词 → L1 | 可用 | 暂无 S0/S1 样例 | 需要 Promptfoo 配置；缺配置时可能跳过 |
| S2 纯提示词 → L2 | 可用 | write-report、system-specification、manager-report、expense-policy-qa | 新 Skill 需登记 DeepEval 映射或用例 |
| S3 纯提示词 → L3 | 部分可用 | 暂无 S3 样例 | `manual_check L3` 默认只跑 Dan；Release v2 需单独跑 |
| 工具型 → L2 + Agent | 可用 | account-balance-query、service-ticket-update、cross-skill-router | 新工具 Skill 需补工具集、权限声明、Agent 配置和测试 |
| 高风险工具型 → L2 + Agent + L3 | 部分可用 | 3 个工具 Skill 已跑 L2+Agent | Garak L3 只扫端点，不能替代工具级检查 |
| 脚本型 → L1 | 可用 | md-to-word | 需 provider、Promptfoo 配置和契约测试 |

横向缺口：

| 能力 | 状态 |
|---|---|
| 按 S 自动选择最低 L | 未实现 |
| 传入 L 低于最低矩阵时拦截 | 未实现 |
| 缺 Promptfoo/DeepEval 配置时强提醒 | 未实现，可能显示 skipped |
| 批量运行所有 Skill | 未实现 |
| 发布结论自动汇总 | 未实现 |

### 4.2 运行前必须手工完成

所有 Skill 通用：

1. 确定 S 等级，写入 `metadata.risk-level`；
2. 补齐 `SKILL.md` 的 `name`、`description`、`license`、`allowed-tools`、`metadata.owner/risk-level/version`；
3. 生成并验证完整性锁；
4. 通过结构校验；
5. 准备本地模型网关和依赖；
6. 准备合成测试数据，禁止真实 PII、密钥、生产凭证。

按矩阵补充：

| 矩阵项 | 运行前还要完成 | 预计用时（含准备） | 仅运行测试 |
|---|---|---|---|
| S0/S1 纯提示词 → L1 | 新建 `targets/<skill>/evals/promptfoo.yaml`，补正常、拒绝、PII/泄露用例 | 15-30 分钟 | 3-5 分钟 |
| S2 纯提示词 → L2 | 在 L1 基础上，登记 DeepEval 映射或新增测试，补相关性/忠实度/幻觉用例 | 30-60 分钟 | 5-10 分钟 |
| S3 纯提示词 → L3 | 在 L2 基础上运行 target L3：`TARGETS=targets SKILL=<skill> ./evals/garak/scan_release.sh` | 25-35 分钟 | 25-35 分钟 |
| 工具型 → L2 + Agent | 声明 `metadata.tool-set` 和 `metadata.tool-permissions`，实现工具集，补 `.agent.yaml` 和 `test_agent_<skill>.py`，创建 `.venv-harness` | 1-2 小时 | 5-10 分钟 |
| 高风险工具型 → L2 + Agent + L3 | 在工具型基础上，再跑 Release v2；L3 不能替代工具级 Agent 检查 | 1.5-3 小时 | 25-35 分钟 |
| 脚本型 → L1 | 补 provider、Promptfoo 配置和契约测试（如 `ci/test_<skill>_contract.py`） | 20-40 分钟 | 1-2 分钟 |

> 时间为按当前本地 qwen3、现有脚本和已有配置的估算。
>
> “仅运行测试”指配置、用例、依赖和环境均已就绪，不包含首次准备和 3 轮基线。
>
> 3 轮基线约为单次运行时间 × 3。
>
> S3 的“仅运行测试”包含 L2 + Garak Release v2；如果只跑 `manual_check --level L3` 的默认 Dan probe，时间会短很多，但不等于完整 L3。

运行前检查清单：

- [ ] `metadata.risk-level` 已确定
- [ ] 目标 L 符合最低矩阵
- [ ] Promptfoo 配置存在
- [ ] L2 的 DeepEval 目标存在
- [ ] 工具型有 `tool-set`、`tool-permissions`、Agent 配置和测试
- [ ] Agent 模式已创建 `.venv-harness`
- [ ] L3 已准备 `.venv-garak`
- [ ] 测试数据为合成数据
- [ ] 缺配置导致的 `skipped` 不被当作 `passed`

### 4.3 用 preflight.py 自动检查前置条件

运行前先跑 `preflight`；工具型加 `--agent`，发布前加 `--release`。命令见 §5.6。

`preflight` 会检查：

- 目标包 `manifest.yaml`；
- `SKILL.md`、Owner、风险等级；
- 目标 L 是否满足最低矩阵；
- 工具型是否加了 `--agent`；
- `validate`、完整性锁、提示词审计、权限审计；
- Promptfoo 配置、DeepEval 目标、Agent 测试；
- 本地模型网关、`.venv-harness`、`.venv-garak`；
- 基线轮数；`--release` 时要求至少 3 轮；
- Docker 是否可用。

输出：

```text
[OK]   skill: targets/write-report/SKILL.md
[OK]   level: L2 满足最低要求
[OK]   promptfoo-config: targets/write-report/evals/promptfoo.yaml
[OK]   deepeval-target: targets/<skill>/evals/test_*.py
[FAIL] agent: 工具型 Skill 必须加 --agent

status: failed  failures=1  warnings=0
```

退出码：

- `0`：通过，可能有 warning；
- `1`：存在 FAIL，不能开始检查；
- `2`：参数错误。

它不负责：

- 判断 S 等级；
- 生成业务测试用例；
- 运行 `manual_check`；
- 批准发布。

离线环境可加 `--skip-network`，只跳过网关探测。

---

## 5. 报告与排障

### 5.1 报告位置

完整发布检查：

```text
reports/<skill>/release-<timestamp>/
├── summary.md
├── summary.json
└── garak/                  # 启用 --l3 时
```

单次检查：

```text
reports/<skill>/target-<timestamp>/
├── report.md
├── summary.json
├── run.log
└── promptfoo.json
```

L3 原始报告：

```text
reports/garak/release/<skill>/<timestamp>/
├── garak.report.jsonl
├── garak.report.html
├── garak_summary.json
└── garak_summary.md
```

---

### 5.2 阅读顺序

1. `summary.md` / `report.md` 的步骤结果；
2. Promptfoo 失败用例；
3. DeepEval 或工具测试；
4. 基线与 Delta Gate；
5. L3 的 `true compliant`；
6. 未通过项和下一步。

报告字段：

```text
risk_level: S2
level: L2
agent: true
```

- `risk_level`：Skill 风险等级；
- `level`：本次检查深度；
- `agent`：本次是否启用 Agent 工具执行。

---

### 5.3 状态含义

| 状态 | 含义 |
|---|---|
| PASSED | 通过 |
| FAILED | 有失败，需要处理 |
| WARN | 可继续，但发布前需处理 |
| SKIPPED | 未执行，不能当通过 |

---

### 5.4 L3 结论怎么看

先看 `true compliant`，再看原始 ASR。

- `true compliant = 0` 才能认为该 probe 没有真实命中；
- 原始 ASR 非零但 `true compliant = 0`，通常是检测器把拒绝时的复述算成命中；
- 不要把原始 ASR 直接当成真实攻击成功率；
- Garak 只扫端点，不能替代工具越权、参数注入和数据外泄检查。

---

### 5.5 常见问题

| 现象 | 处理 |
|---|---|
| `manifest.yaml not found` | 从入口 Skill 第 1 步重新初始化 |
| `preflight` 失败 | 按输出补 manifest、adapter、evals、tools |
| `skill-lock` 失败 | 执行 `python scripts/skill_lock.py generate` |
| Promptfoo 配置缺失 | 补 `targets/<skill>/evals/promptfoo.yaml` |
| DeepEval 目标缺失 | 补 `targets/<skill>/evals/test_*.py` |
| 工具型 capability-audit 失败 | 检查 `tools.yaml` 与 `adapter.py registry` |
| 模型连接失败 | 检查 `http://localhost:8086/v1` |
| L3 很慢 | 使用独立 Garak 环境，避免并发跑多个目标 |
| 出现 `skipped` | 不能当 `passed`，必须补配置或说明原因 |

---

### 5.6 手动调试命令

仅在入口流程失败、需要定位时使用。

```bash
# 结构校验
python ci/validate_skill.py
python ci/validate_skill.py --skill my-skill

# 完整性锁
python scripts/skill_lock.py generate
python scripts/skill_lock.py verify

# 运行前置
python scripts/preflight.py --targets targets --skill my-skill --risk S2 --level L2

# 单次检查
python scripts/manual_check.py --targets targets --skill my-skill --level L2

# 权限一致性
python scripts/capability_audit.py --targets targets --skill my-skill

# 提示词质量
python scripts/prompt_audit.py --skill my-skill
python scripts/prompt_audit.py --skill my-skill --llm

# 基线
python scripts/baseline.py --targets targets collect my-skill --runs 3
python scripts/baseline.py --targets targets trend my-skill
python scripts/baseline.py --targets targets gate my-skill --tolerance 0.05

# 目标服务（调试 Garak）
python scripts/target_server.py --targets targets --skill my-skill --port 8095
```

工具型 Skill 在 `preflight` 和 `manual_check` 上加 `--agent`。

---

### 5.7 批量运行

```bash
# 批量 preflight
python scripts/scan_all.py --targets targets

# 批量单次检查
python scripts/scan_all.py --targets targets --mode check

# 离线只检查配置
python scripts/scan_all.py --targets targets --skip-network
```

批量运行不替代每个 Skill 的 3 轮基线、Delta Gate 和 L3。
