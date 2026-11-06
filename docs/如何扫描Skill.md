# 如何扫描一个 Agent Skill（用户使用指南）

适用读者：Skill 作者、Skill Owner、安全审核人。

你将完成：

> 放入目标包 → 补齐配置 → 单次检查 → 3 轮基线 → Delta Gate → 可选 L3 → 生成发布前报告。

---

## 先理解三个词

| 概念 | 含义 |
|---|---|
| **S0-S3** | 业务风险等级 |
| **L0-L3** | 检查深度 |
| **Agent** | 工具调用执行标志，不是等级 |

完整分级说明见 [`Skill 分级与检查使用指南.md`](Skill%20分级与检查使用指南.md)。

最低检查：

| Skill 类型 | 最低检查 |
|---|---|
| S0/S1 纯提示词 | L1 |
| S2 纯提示词 | L2 |
| S3 纯提示词 | L3 |
| 工具型 Skill | L2 + Agent |
| 高风险工具型 | L2 + Agent，发布前 L3 |
| 脚本型 | L1 |

---

## 0. 第一次使用前

确认：

- Python 3.10+
- Node.js 20+
- Docker
- 本地模型网关：`http://localhost:8086/v1`，模型 `qwen3`
- Agent 型 Skill 已执行：
  ```bash
  ./scripts/setup_harness_env.sh
  ```
- L3 已准备独立 Garak 环境：
  ```bash
  uv venv .venv-garak --python 3.10
  uv pip install --python .venv-garak/bin/python 'garak==0.16.0'
  ```

测试数据只使用合成数据，禁止真实 PII、密钥、生产凭证。

---

## 1. 放入待验证 Skill

不要直接放到 `skills/`。当前统一使用 `targets/`。

### 推荐：一条命令初始化

```bash
python scripts/release_assistant.py init \
  --source /path/to/my-skill \
  --name my-skill \
  --owner my-team \
  --risk S2 \
  --type prompt \
  --level L2 \
  --targets targets
```

工具型加 `--agent`：

```bash
python scripts/release_assistant.py init \
  --source /path/to/my-skill \
  --name my-skill \
  --owner my-team \
  --risk S2 \
  --type tool \
  --level L2 --agent \
  --targets targets
```

生成：

```text
targets/my-skill/
├── SKILL.md
├── manifest.yaml
├── adapter.py
├── tools.yaml
├── evals/
├── fixtures/
└── safety.py
```

`init` 在仓库 `targets/` 下会自动更新完整性锁。

### 已有目标包

如果 `targets/my-skill` 已存在，直接进入下一步。

---

## 2. 补齐 TODO

`init` 只生成骨架，不会替你写业务用例。

### 纯提示词 Skill

检查并补齐：

- `adapter.py`：默认已可调用本地网关
- `evals/promptfoo.yaml`：正常、拒绝、PII/泄露用例
- `evals/test_*.py`：DeepEval 相关性/忠实度用例
- `fixtures/`：合成测试数据

### 脚本型 Skill

必须实现：

```python
def run(user_input: str) -> dict:
    return {"output": "...", "metadata": {}}
```

同时补：

- `evals/promptfoo.yaml`
- 契约测试
- `requirements.txt`

### 工具型 Skill

必须完成：

1. `tools.yaml` 写清工具权限；
2. `adapter.py` 实现：
   ```bash
   python adapter.py registry --json
   python adapter.py run --input "..."
   ```
3. 覆盖：
   - 正常工具调用
   - 未授权工具
   - 参数注入
   - 数据外泄
   - 工具超时/报错

要求：

- 不删除 `safety.py`
- 不在生产 `SKILL.md` 里写 `SENTINEL` 或测试注入文本
- 测试数据放 `fixtures/`

---

## 3. 单次检查

先跑一次，确认配置齐全：

```bash
python scripts/release_assistant.py check \
  --targets targets \
  --skill my-skill
```

它会自动：

1. 生成完整性锁；
2. 运行 `preflight`；
3. 运行一次 `manual_check`。

有 FAIL 时先修，不要直接进入 3 轮检查。

也可以单独调试：

```bash
python scripts/preflight.py --targets targets --skill my-skill --risk S2 --level L2
python scripts/manual_check.py --targets targets --skill my-skill --level L2
```

工具型加 `--agent`。

---

## 4. 完整发布前检查

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

`run` 会依次执行：

1. 完整性锁
2. `preflight`
3. 3 轮 `manual_check`
4. 采集目标基线
5. `baseline gate`
6. 可选 target L3/Garak Release v2
7. 汇总报告

运行时间参考：

| 类型 | 仅检查 |
|---|---|
| S2 纯提示词 L2 | 5-10 分钟/轮 |
| 工具型 L2 + Agent | 5-10 分钟/轮 |
| 加 L3 | 额外 20-30 分钟 |

3 轮检查约为单轮 × 3。

---

## 5. 单独跑 L3

```bash
TARGETS=targets SKILL=my-skill ./evals/garak/scan_release.sh
```

输出：

```text
reports/garak/release/<skill>/<timestamp>/
├── garak.report.jsonl
├── garak.report.html
├── garak_summary.json
└── garak_summary.md
```

看结论时：

- 先看 `true compliant`
- 再看原始 ASR
- 原始 ASR 非零但 true compliant 为 0，通常是检测器把“拒绝时复述”算成命中
- 不要把原始 ASR 直接当成真实攻击成功率

---

## 6. 看报告

单入口汇总：

```text
reports/<skill>/release-<timestamp>/
├── summary.md
├── summary.json
└── garak/                  # 启用 --l3 时
```

单次检查报告：

```text
reports/<skill>/target-<timestamp>/
├── report.md
├── summary.json
├── run.log
└── promptfoo.json
```

阅读顺序：

1. `summary.md` / `report.md` 的步骤结果
2. Promptfoo 失败用例
3. DeepEval/工具测试
4. 基线与 Gate
5. L3 true compliant
6. 未通过项和下一步

状态含义：

| 状态 | 含义 |
|---|---|
| PASSED | 通过 |
| FAILED | 有失败，需要处理 |
| WARN | 可继续，但发布前需处理 |
| SKIPPED | 未执行，不能当通过 |

---

## 7. 发布前检查清单

- [ ] `preflight` 通过
- [ ] 3 轮 `manual_check` 完成
- [ ] `baseline gate` PASS
- [ ] 没有未解释的 Flaky
- [ ] S3 或高风险工具完成 L3
- [ ] L3 `true compliant = 0`
- [ ] 失败/隔离项有人工结论
- [ ] Owner 签核
- [ ] 报告已归档

---

## 8. 常见场景

### 只想快速验证配置

```bash
python scripts/release_assistant.py check --targets targets --skill my-skill
```

### 批量检查所有目标

```bash
python scripts/scan_all.py --targets targets
```

### 批量执行完整检查

```bash
python scripts/scan_all.py --targets targets --mode check
```

### 只看目标包是否满足最低检查

```bash
python scripts/preflight.py --targets targets --skill my-skill --risk S2 --level L2
```

---

## 9. 常见问题

| 现象 | 处理 |
|---|---|
| `manifest.yaml not found` | 先执行 `release_assistant.py init` |
| `preflight` 失败 | 按输出补 manifest、adapter、evals、tools |
| `skill-lock` 失败 | 执行 `python scripts/skill_lock.py generate` |
| Promptfoo 配置缺失 | 补 `targets/<skill>/evals/promptfoo.yaml` |
| DeepEval 目标缺失 | 补 `targets/<skill>/evals/test_*.py` |
| 工具型 capability-audit 失败 | 检查 `tools.yaml` 与 `adapter.py registry` |
| 模型连接失败 | 检查 `http://localhost:8086/v1` |
| L3 很慢 | 使用本地 Garak 环境，避免并发跑多个目标 |
| `skipped` | 不能当 `passed`，必须补配置或说明原因 |

---

## 10. 手动调试命令

```bash
# 结构校验
python ci/validate_skill.py
python ci/validate_skill.py --skill my-skill

# 完整性锁
python scripts/skill_lock.py generate
python scripts/skill_lock.py verify

# 权限一致性
python scripts/capability_audit.py --targets targets --skill my-skill

# 提示词质量
python scripts/prompt_audit.py --path targets/my-skill/SKILL.md
python scripts/prompt_audit.py --path targets/my-skill/SKILL.md --llm

# 基线
python scripts/baseline.py --targets targets collect my-skill --runs 3
python scripts/baseline.py --targets targets trend my-skill
python scripts/baseline.py --targets targets gate my-skill --tolerance 0.05

# 目标服务（调试 Garak）
python scripts/target_server.py --targets targets --skill my-skill --port 8095
```

---

## 不要做的事

- 不要把待验证 Skill 放进 `skills/`。
- 不要把 `skipped` 当成 `passed`。
- 不要自行决定 S 等级或 Owner。
- 不要用假的测试数据代替真实业务场景。
- 不要为了通过断言而放宽安全规则。
- 不要在未完成 L3 的情况下发布 S3 或高风险工具型 Skill。
- 不要让助手代替人工签核。
