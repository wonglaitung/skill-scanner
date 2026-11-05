# Skill 分级与检查使用指南

适用对象：Skill 作者、Skill Owner、安全审核人。

目标：用统一口径回答三个问题：

1. 这个 Skill 风险多高？——**S**
2. 这次要查多深？——**L**
3. 要不要真正执行工具调用？——**Agent**

不再使用 H3。H3 只是历史内部代号，用户侧统一称 **Agent 模式**。

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
python scripts/manual_check.py --skill account-balance-query --level L2 --agent
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

---

## 5. 命令示例

### S0/S1 纯提示词

```bash
python scripts/manual_check.py --skill my-skill --level L1
```

### S2 纯提示词

```bash
python scripts/manual_check.py --skill my-skill --level L2
```

### S3 纯提示词

```bash
python scripts/manual_check.py --skill my-skill --level L3
```

### 工具型 Skill

```bash
python scripts/manual_check.py --skill my-skill --level L2 --agent
```

### 高风险工具型

```bash
python scripts/manual_check.py --skill my-skill --level L2 --agent
python scripts/manual_check.py --skill my-skill --level L3
```

### 脚本型

```bash
python scripts/manual_check.py --skill my-skill --level L1
pytest -q ci/test_<my-skill>_contract.py
```

---

## 6. 发布前附加要求

除最低检查外，发布前还要：

1. 连续跑 3 轮基线；
2. 采集基线并跑 Delta Gate；
3. 查看 Flaky 用例；
4. 人工复核失败、隔离和跳过项；
5. S2/S3 由 Owner 签核；
6. S3 发布前完成 L3。

```bash
python scripts/baseline.py collect my-skill --runs 3
python scripts/baseline.py gate my-skill --tolerance 0.05
```

---

## 7. 报告里怎么看

报告和 `summary.json` 使用三个字段：

```text
risk_level: S2
level: L2
agent: true
```

对应含义：

- `risk_level`：这个 Skill 的风险等级；
- `level`：这次检查的深度；
- `agent`：这次是否启用了 Agent 工具执行。

---

## 8. 不要做的事

- 不要用 H3 作为用户侧分级名称。
- 不要把 Agent 当成 L4 或更高级别。
- 不要用 L3 替代工具越权检查；工具权限、参数注入、外泄主要靠 `L2 + Agent`。
- 不要对纯提示词 Skill 强行加 `--agent`。
- 不要用单轮结果代替 3 轮基线和 Delta Gate。
