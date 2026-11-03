# skill-scanner

Agent Skill 工程化检查与对抗审核工具。当前处于**手工触发、试点验证**阶段，不依赖 CI。

- 方案文档：`docs/Agent Skill 工程化检查落地方案.md`（v2.8）
- 当前进度：`progress.md`
- Agent 工作约定：`AGENTS.md`

## 能做什么

- 校验 `SKILL.md` 结构与元数据
- 用 Promptfoo 做确定性回归（边界、PII、AI 腔、格式）
- 用 DeepEval 做指标化评分（相关性、忠实度、幻觉）
- 用 Garak 对 **Skill 包装端点**做发布前扫描
- 用 Semgrep / Ruff 做静态检查
- 为脚本型 Skill 提供 Promptfoo provider 与契约测试
- 保存基线并对比回退
- 生成可审计的 Markdown/JSON 报告

## 快速开始

### 1. 依赖

```bash
pip install -r requirements-dev.txt -r requirements-eval.txt
npm install
```

需要 Python 3.10+、Node.js 20+。

### 2. 本地模型网关

默认地址：

```text
http://localhost:8086/v1
模型：qwen3
```

所有模型调用只走本地网关，不访问外部模型。

### 3. 一键手工检查

```bash
# L0：结构 + 静态检查
python scripts/manual_check.py --skill write-report --level L0

# L1：L0 + Promptfoo
python scripts/manual_check.py --skill write-report --level L1

# L2：L1 + DeepEval
python scripts/manual_check.py --skill manager-report --level L2

# L3：L2 + Garak（自动启动 Skill 端点）
python scripts/manual_check.py --skill manager-report --level L3
```

输出：

```text
reports/<skill>/<timestamp>/
├── summary.json
├── report.md
├── run.log
├── promptfoo.json
└── garak.report.jsonl
```

### 4. 基线

```bash
python scripts/baseline.py save manager-report
python scripts/baseline.py diff manager-report
python scripts/baseline.py list
```

### 5. 单独运行各工具

```bash
# 结构校验
python ci/validate_skill.py
python ci/validate_skill.py --skill write-report

# 静态检查
ruff check adapters ci evals skills scripts
semgrep --config p/python --config p/owasp-top-ten adapters ci skills scripts --error

# Promptfoo
SKILL_API_BASE=http://localhost:8086/v1 SKILL_MODEL=qwen3 \
  npx promptfoo eval -c evals/promptfooconfig.write-report.yaml --max-concurrency 1

# DeepEval
RUN_LLM_EVALS=1 JUDGE_MODEL=qwen3 SKILL_API_BASE=http://localhost:8086/v1 \
  SKILL_MODEL=qwen3 DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE=300 \
  deepeval test run evals/deepeval/test_s2_skills.py

# Garak（Skill 级，建议在独立 venv/容器中安装）
SKILL=write-report ./evals/garak/scan.sh

# Skill 包装端点
python adapters/skill_server.py --skill write-report --port 8090
```

## 检查分级

| 级别 | 内容 | 适用 |
|---|---|---|
| L0 | 结构、Ruff、Semgrep、密钥、依赖 | 每次改动快速自检 |
| L1 | L0 + Promptfoo 确定性回归 | 发布前基线 |
| L2 | L1 + DeepEval 指标评分 | 高风险 Skill 评测 |
| L3 | L2 + Garak + 人工复核 | 发布前独立扫描 |

## 已有 Skill

| Skill | 类型 | 说明 |
|---|---|---|
| `write-report` | 纯提示词 | 银行管理层汇报 |
| `system-specification` | 纯提示词 | 金融系统规格书 |
| `manager-report` | 纯提示词 | 算力申请汇报 |
| `expense-policy-qa` | 纯提示词 | 费用报销问答（示例） |
| `md-to-word` | 提示词 + 脚本 | Markdown 转 Word |

## 目录结构

```text
docs/                 方案、试点报告、审核模板
skills/               试点 Skill
adapters/             Promptfoo/Garak/DeepEval 适配器
evals/                用例、配置、基线
ci/                   校验、静态检查、测试
scripts/              手工检查与基线工具
reports/              运行产物（不入库）
progress.md           项目进度
AGENTS.md             Agent 工作约定
```

## 当前结果

| 检查 | 结果 |
|---|---|
| SKILL.md 结构校验 | 5 个全部通过 |
| S2 Promptfoo | 23/24 通过（F-003 待处理） |
| S2 DeepEval 相关性 | 3/3 |
| Faithfulness / Hallucination | 通过 |
| md-to-word Promptfoo | 5/5 |
| md-to-word 契约测试 | 4/4 |
| Garak `dan.Dan_11_0` | 1/1（Skill 端点） |
| Semgrep | 0 findings |
| pytest | 7 passed，6 skipped（LLM 用例需显式开启） |

## 已知限制

- F-003：`write-report` 在追问/模板中仍可能出现 AI 腔。
- Garak `promptinject` 有 256 条，本地 qwen3 速度不足，尚未跑完。
- gitleaks、Trivy、ShellCheck 尚未安装。
- H3 工具调用 / 多步 Agent 尚未实现。
- 目前是单轮基线，不足以支撑 PR 阻断。
- 纯脚本 Skill 不适用 DeepEval/Garak，其质量由确定性断言和契约测试保证。

## 安全约束

- 只使用合成数据，禁止真实 PII、密钥、生产凭证。
- 所有模型调用走本地网关。
- 扫描目标必须获得授权，只允许白名单 endpoint。
- 未经验证不要声称测试通过。

## 相关文档

- `docs/Agent Skill 工程化检查落地方案.md`
- `docs/Agent Skill 试点报告.md`
- `docs/对抗审核报告模板.md`
- `docs/针对 Agent Skill，业界标准的工程化检查怎么做.md`
- `docs/解释Garak, Promptfoo, LLM-Eval的用法.md`
