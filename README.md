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

详细步骤见 `docs/如何扫描Skill.md`。

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

# H3 Agent 模式
python scripts/manual_check.py --skill account-balance-query --level L2 --agent
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

### 5. 运行时沙箱

脚本型 Skill 在 Docker 中运行，默认 `network none`、只读根文件系统、非 root、CPU/内存/超时限制：

```bash
./scripts/run_sandboxed.sh -c "import docx; print('sandbox ok')"
./scripts/sandbox_escape_check.sh
```

逃逸检查覆盖：非 root、工作区只读、`/etc/shadow` 不可读、无外网、无 Docker socket。

沙箱镜像与配置：

- `adapters/sandbox/Dockerfile`：脚本执行沙箱
- `adapters/sandbox/Dockerfile.model`：模型型 Skill 端点沙箱
- `adapters/sandbox/docker-compose.yml`

模型型 Skill 可在容器内启动：

```bash
./scripts/run_skill_server_sandboxed.sh manager-report
```

默认监听 `127.0.0.1:8090`，容器通过 `host.docker.internal` 访问本地模型网关。

严格网络白名单模式：

```bash
docker compose -f adapters/sandbox/docker-compose.model.yml up -d --build
curl http://127.0.0.1:8090/health
docker compose -f adapters/sandbox/docker-compose.model.yml down -v
```

该模式使用：

- `internal` 网络：Skill 容器无外网
- `egress_proxy.py`：只允许 `host.docker.internal:8086`
- `ingress`：只负责把 8090 暴露到本机
- 实测：外部 HTTPS 返回 403，直连 `1.1.1.1:80` 为 `Network is unreachable`

### 6. 供应链扫描

```bash
./ci/run_security.sh
```

包含：

- gitleaks：密钥扫描
- npm audit：Node 依赖漏洞
- Trivy：依赖漏洞、IaC、配置错误
- SBOM：`reports/sbom.cdx.json`
- Skill 文件完整性锁：`python scripts/skill_lock.py verify`

密码学签名（可选，私钥不入库）：

```bash
python scripts/sign_skills.py keygen --private /secure/skills.pem --public evals/keys/public.pem
python scripts/sign_skills.py sign --key /secure/skills.pem
python scripts/sign_skills.py verify --public evals/keys/public.pem
```

`manual_check.py` 在检测到 `evals/keys/public.pem` 与 `evals/skills.lock.sig` 时会自动验签。生产环境私钥应由 KMS/HSM 或独立签名服务托管。

需要 Docker。Garak、Trivy、gitleaks 建议使用独立镜像/容器，避免污染主环境。

### 7. 单独运行各工具

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
| `account-balance-query` | 提示词 + 工具 | H3 工具调用测试 Skill |

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
| gitleaks | 0 leaks |
| npm audit | 0 vulnerabilities（通过 overrides 修复） |
| Trivy | 0 findings |
| SBOM | 622 components（CycloneDX） |
| 沙箱 | md-to-word 转换通过（network none、read-only） |
| 沙箱逃逸检查 | 通过（非 root、只读、无网络、无 Docker socket） |
| 模型型 Skill 沙箱 | manager-report 容器内启动并返回响应 |
| 网络白名单 | 外部访问被阻断，仅允许本地模型网关 |
| Skill 完整性锁 | 5 个 Skill 全部匹配 |
| 密码学签名 | Ed25519 签名/验签通过，篡改检测失败符合预期 |
| H3 Promptfoo | 5/5 |
| H3 ToolCorrectness | 1/1 |
| pytest | 7 passed，6 skipped（LLM 用例需显式开启） |

## 已知限制

- F-003：`write-report` 在追问/模板中仍可能出现 AI 腔。
- Garak `promptinject` 有 256 条，本地 qwen3 速度不足，尚未跑完。
- gitleaks、Trivy、ShellCheck 尚未安装。
- H3 工具调用 / 多步 Agent 尚未实现。
- 目前是单轮基线，不足以支撑 PR 阻断。
- 纯脚本 Skill 不适用 DeepEval/Garak，其质量由确定性断言和契约测试保证。
- 模型型 Skill 严格沙箱依赖 Docker Compose；外部域名白名单目前只允许 `host.docker.internal:8086`。
- 沙箱网络策略是 `network none`；需要外网的 Skill 尚未接入域名白名单代理。
- 密码学签名工具已实现，但私钥托管、轮换和第三方公钥分发流程尚未落地。

## 依赖锁定

- `harness-sdk` 必须锁定版本与 commit，使用 `requirements-harness.txt`。
- 推荐项目本地隔离环境，不污染全局：
  ```bash
  ./scripts/setup_harness_env.sh
  ./scripts/with_harness.sh python -c "import harness; print(harness.__file__)"
  ```
- 禁止使用浮动分支或 `latest`。
- 升级 harness 时重新跑 H3 用例并更新基线。

## 安全约束

- 只使用合成数据，禁止真实 PII、密钥、生产凭证。
- 所有模型调用走本地网关。
- 扫描目标必须获得授权，只允许白名单 endpoint。
- 未经验证不要声称测试通过。

## 相关文档

- `docs/Agent Skill 工程化检查落地方案.md`
- `docs/Agent Skill 试点报告.md`
- `docs/如何扫描Skill.md`
- `docs/对抗审核报告模板.md`
- `docs/针对 Agent Skill，业界标准的工程化检查怎么做.md`
- `docs/解释Garak, Promptfoo, LLM-Eval的用法.md`
