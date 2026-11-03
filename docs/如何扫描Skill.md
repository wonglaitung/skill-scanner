# 如何扫描一个 Agent Skill

本文说明从接入到出报告的完整手工扫描步骤。

---

## 0. 先判断 Skill 类型

| 类型 | 示例 | 需要扫描什么 |
|---|---|---|
| 纯提示词 | `write-report`、`system-specification` | L0-L3 |
| 提示词 + 确定性脚本 | `md-to-word` | L0 + Promptfoo/契约测试；DeepEval/Garak 可跳过 |
| 工具调用 / 多步 Agent | 暂无 | L0-L3；需要 H3 执行器（尚未实现） |

关键原则：

- **有模型/Agent 端点**，才需要 Garak 和 DeepEval。
- **确定性脚本**，优先用 Promptfoo 确定性断言和契约测试，不要硬套 LLM 评测。

---

## 1. 准备工作

### 1.1 放入 Skill

```text
skills/<skill-name>/
├── SKILL.md
├── scripts/          # 可选
└── references/       # 可选
```

`SKILL.md` 至少包含：

```yaml
---
name: <skill-name>
description: <一句话说明能力和边界>
license: internal
allowed-tools: []
metadata:
  owner: <团队>
  risk-level: S2
  version: 0.1.0
---
```

### 1.2 准备评测配置

纯提示词 Skill：

```text
evals/promptfooconfig.<skill-name>.yaml
```

脚本型 Skill：

- 先写 provider，例如 `adapters/md_to_word_provider.py`
- 再写 `evals/promptfooconfig.<skill-name>.yaml`

模型型 Skill 可选：

```text
evals/deepeval/test_<skill-name>.py
```

### 1.3 更新完整性锁

修改 Skill 文件后必须重新生成：

```bash
python scripts/skill_lock.py generate
python scripts/skill_lock.py verify
```

### 1.4 可选：签名

```bash
python scripts/sign_skills.py sign --key /secure/skills.pem
python scripts/sign_skills.py verify --public evals/keys/public.pem
```

私钥不要提交到仓库。

### 1.5 环境

```bash
pip install -r requirements-dev.txt -r requirements-eval.txt
npm install

# 本地模型网关
curl http://localhost:8086/v1/models
```

---

## 2. 一条命令扫描

```bash
python scripts/manual_check.py --skill <skill-name> --level <L0|L1|L2|L3>
```

示例：

```bash
# 纯提示词 Skill，完整扫描
python scripts/manual_check.py --skill write-report --level L3

# 纯提示词 Skill，常规基线
python scripts/manual_check.py --skill manager-report --level L2

# 脚本型 Skill，静态 + 回归
python scripts/manual_check.py --skill md-to-word --level L1
```

常用参数：

| 参数 | 说明 |
|---|---|
| `--model` | 模型名，默认 `qwen3` |
| `--api-base` | 本地网关，默认 `http://localhost:8086/v1` |
| `--skill-timeout` | 单次模型调用超时，默认 180 秒 |
| `--deepeval-timeout` | DeepEval 单次尝试超时，默认 300 秒 |
| `--out` | 自定义报告目录 |
| `--full-garak` | 尝试 Garak `promptinject`（较慢） |
| `--allow-failures` | 有失败也返回 0，仅生成报告 |

---

## 3. 每一级做什么

| 级别 | 自动执行 | 适用 |
|---|---|---|
| **L0** | 结构校验、完整性锁、签名（如配置）、Ruff、Semgrep、gitleaks、npm audit、Trivy、SBOM、ShellCheck | 每次改动 |
| **L1** | L0 + Promptfoo 确定性回归 | 发布前基线 |
| **L2** | L1 + DeepEval 指标评分 | 模型型 Skill |
| **L3** | L2 + Garak（通过 `skill_server.py` 扫描 Skill 端点） | 发布前审计 |

说明：

- `security` 步骤依赖 Docker；没有 Docker 时会跳过并记录。
- 脚本型 Skill 的 L2 DeepEval 会跳过，并记录“确定性脚本无 LLM 端点”。
- L3 默认只跑 `dan.Dan_11_0`；`--full-garak` 才尝试 `promptinject`。

---

## 4. 报告与证据

输出目录：

```text
reports/<skill>/<timestamp>/
├── summary.json
├── report.md
├── run.log
├── promptfoo.json
├── trivy.sarif
├── sbom.cdx.json
├── garak.report.jsonl
└── garak_rest_config.json
```

`report.md` 包含：

- 级别、时间、模型、网关
- 每步状态与耗时
- Promptfoo 通过/失败
- DeepEval 通过率
- 供应链结果
- Garak 状态
- 证据路径
- 人工复核清单

---

## 5. 人工复核

1. 打开 `report.md`。
2. 检查失败/超时步骤。
3. 对 Promptfoo 失败用例判断：测试问题还是 Skill 问题。
4. 对 Critical/High 发现建工单。
5. 修复 Skill 后：
   - 重新生成完整性锁
   - 重新签名（如启用）
   - 重跑同一级别
6. 在报告上补：定级、修复建议、豁免、结论。

---

## 6. 保存与对比基线

```bash
python scripts/baseline.py save <skill-name>
python scripts/baseline.py diff <skill-name>
python scripts/baseline.py list
```

`diff` 会比较：

- Promptfoo 通过率
- DeepEval 通过率
- 失败用例数

可以加 `--fail-on-regression` 在回退时返回非零。

---

## 7. 单独运行各工具

```bash
# 结构校验
python ci/validate_skill.py --skill write-report

# 完整性
python scripts/skill_lock.py verify --skill write-report

# 静态检查
ruff check adapters ci evals skills scripts
semgrep --config p/python --config p/owasp-top-ten adapters ci skills scripts --error

# Promptfoo
SKILL_API_BASE=http://localhost:8086/v1 SKILL_MODEL=qwen3 \
  npx promptfoo eval -c evals/promptfooconfig.write-report.yaml --max-concurrency 1

# DeepEval
RUN_LLM_EVALS=1 JUDGE_MODEL=qwen3 SKILL_API_BASE=http://localhost:8086/v1 \
  DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE=300 \
  deepeval test run evals/deepeval/test_s2_skills.py

# Garak（Skill 级）
SKILL=write-report ./evals/garak/scan.sh

# 供应链扫描
./ci/run_security.sh

# 沙箱
./scripts/run_sandboxed.sh -c "import docx; print('sandbox ok')"
./scripts/sandbox_escape_check.sh
```

---

## 8. 常见问题

| 问题 | 处理 |
|---|---|
| `Connection refused` | 本地网关未启动，检查 `localhost:8086` |
| Promptfoo 超时 | 提高 `--skill-timeout`，降低并发，或拆小用例 |
| DeepEval 超时 | 提高 `--deepeval-timeout`，或改用短样本 |
| 完整性锁不匹配 | 修改 Skill 后执行 `python scripts/skill_lock.py generate` |
| 签名被跳过 | 未配置 `evals/keys/public.pem` 和 `evals/skills.lock.sig` |
| security 被跳过 | 未安装 Docker |
| Garak 很慢 | 只跑 `Dan_11_0`；`promptinject` 分批/独立环境 |
| 脚本型 Skill 没有 DeepEval/Garak | 预期行为；用 Promptfoo + 契约测试 |

---

## 9. 最短路径

```bash
python scripts/manual_check.py --skill write-report --level L2
python scripts/baseline.py save write-report
python scripts/baseline.py diff write-report
```

先看 `reports/write-report/<timestamp>/report.md`，再决定是否修复、复测或进入 L3。

---

## 10. 当前限制

- H3 工具调用 / 多步 Agent 尚未实现。
- Garak `promptinject` 受本地模型速度限制。
- SCA 目前覆盖 npm/pip 依赖，SBOM 为 CycloneDX；更细的许可证审计未接入。
- 模型网关隔离尚未按 Skill 分配独立凭证/配额。
- 密码学签名的私钥托管与轮换流程待定。
