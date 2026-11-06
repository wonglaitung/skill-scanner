# skill-scanner

Agent Skill 工程化检查与对抗审核工具。当前处于**手工触发、试点验证**阶段，不依赖 CI。

- 方案文档：`docs/Agent Skill 工程化检查落地方案.md`（v2.11）
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
# 运行前检查：配置、权限、环境、基线是否齐全
python scripts/preflight.py --skill write-report --risk S2 --level L2

# 目标包
python scripts/preflight.py --targets targets --skill write-report --risk S2 --level L2
python scripts/manual_check.py --targets targets --skill write-report --level L2
python scripts/scan_all.py --targets targets

# L0：结构 + 静态检查
python scripts/manual_check.py --skill write-report --level L0

# L1：L0 + Promptfoo
python scripts/manual_check.py --skill write-report --level L1

# L2：L1 + DeepEval
python scripts/manual_check.py --skill manager-report --level L2

# L3：L2 + Garak（自动启动 Skill 端点）
python scripts/manual_check.py --skill manager-report --level L3

# Garak 发布前复查（独立 venv + 约定 probe 集）
SKILL=account-balance-query ./evals/garak/scan_release.sh

# Agent 模式
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
python scripts/baseline.py collect manager-report --runs 3
python scripts/baseline.py trend manager-report
python scripts/baseline.py diff manager-report --tolerance 0.05
python scripts/baseline.py gate manager-report --tolerance 0.05
python scripts/capability_audit.py --skill account-balance-query
python scripts/prompt_audit.py --skill write-report
JUDGE_MODEL=qwen3 python scripts/judge_calibration.py
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

## 分级模型

完整说明见 [`docs/Skill 分级与检查使用指南.md`](docs/Skill%20分级与检查使用指南.md)。

- **S0-S3**：业务风险等级
- **L0-L3**：检查深度
- **`--agent`**：Agent 执行标志，不是等级

### S：风险等级

| 等级 | 含义 |
|---|---|
| S0 | 无风险/纯展示 |
| S1 | 低风险 |
| S2 | 中高风险，默认重点检查 |
| S3 | 高风险，必须完整检查 |

### L：检查深度

L1 包含 L0，L2 包含 L1，L3 包含 L2。

| 级别 | 查什么 |
|---|---|
| L0 | 结构、完整性锁、静态检查、供应链、权限审计、提示词审计 |
| L1 | L0 + Promptfoo 回归 |
| L2 | L1 + DeepEval 指标 |
| L3 | L2 + Garak 独立扫描 |

### Agent：执行方式

```bash
python scripts/manual_check.py --skill account-balance-query --level L2 --agent
```

Agent 只用于工具型 Skill，不是 L4，也不能替代 L0-L3。

### 最低检查

| Skill 类型 | 最低检查 |
|---|---|
| S0/S1 纯提示词 | L1 |
| S2 纯提示词 | L2 |
| S3 纯提示词 | L3 |
| 工具型 Skill | L2 + Agent |
| 高风险工具型 | L2 + Agent，发布前 L3 |
| 脚本型 | L1 |

## 已有 Skill

| Skill | 类型 | 说明 |
|---|---|---|
| `write-report` | 纯提示词 | 银行管理层汇报 |
| `system-specification` | 纯提示词 | 金融系统规格书 |
| `manager-report` | 纯提示词 | 算力申请汇报 |
| `expense-policy-qa` | 纯提示词 | 费用报销问答（示例） |
| `md-to-word` | 提示词 + 脚本 | Markdown 转 Word |
| `account-balance-query` | 提示词 + 工具 | Agent 工具调用测试 Skill |

## 目录结构

```text
docs/                 方案、分级指南、扫描指南、模板
skills/               旧布局试点 Skill（迁移中）
targets/              目标包（8 个）
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
| SKILL.md 结构校验 | 8 个全部通过 |
| 多轮基线 | 8 个 S2 各 3 轮，Delta Gate 全部 PASS |
| Promptfoo | write-report 8/8、system-specification 8/8、manager-report 8/8、expense-policy-qa 5/5、md-to-word 5/5、account-balance-query 15/15、service-ticket-update 10/10、cross-skill-router 9/9 |
| DeepEval | account 7/7；write/system/ticket/cross 均通过 |
| Garak Release v2 | 7 个 LLM Skill，4 个 probe，true compliant 0 |
| Judge 校准 | 20 条，一致率 95% |
| Semgrep / Ruff | 0 findings / 0 errors |
| gitleaks | 0 leaks |
| npm audit / Trivy | 0 vulnerabilities / 0 findings |
| SBOM | 622 components（CycloneDX） |
| 沙箱 | 脚本转换、逃逸检查、模型端点沙箱通过 |
| Skill 完整性锁 | 8 个全部匹配 |
| 密码学签名 | Ed25519 签名/验签通过，篡改检测符合预期 |

## 已知限制

- Garak Release v2 仍是约定的 4 个 probe，不是全部 Garak probe。
- 每个 S2 只有 3 轮基线，尚未累计 2-4 周稳定性数据。
- Agent 模式使用 Mock 工具，真实工具权限、副作用、回滚尚未验证。
- 网页/文件/RAG/记忆注入尚未覆盖。
- 输入护栏会拒绝编码/解码和训练数据复述请求；未来合法场景需要白名单。
- 私钥托管/轮换、模型网关按 Skill 隔离、可观测性、报告签名/归档仍未闭环。
- 全流程默认不在沙箱内执行；Docker/gVisor 脚本是独立能力。
- 目前是人工/半自动检查，不单独作为自动发布审批依据。

## 依赖锁定

- `harness-sdk` 必须锁定版本与 commit，使用 `requirements-harness.txt`。
- 推荐项目本地隔离环境，不污染全局：
  ```bash
  ./scripts/setup_harness_env.sh
  ./scripts/with_harness.sh python -c "import harness; print(harness.__file__)"
  ```
- 禁止使用浮动分支或 `latest`。
- 升级 harness 时重新跑 Agent 用例并更新基线。

## 安全约束

- 只使用合成数据，禁止真实 PII、密钥、生产凭证。
- 所有模型调用走本地网关。
- 扫描目标必须获得授权，只允许白名单 endpoint。
- 未经验证不要声称测试通过。

## 相关文档

- [`docs/README.md`](docs/README.md)：文档索引
- [`Agent Skill 工程化检查落地方案.md`](docs/Agent%20Skill%20工程化检查落地方案.md)
- [`生产级演进路线.md`](docs/生产级演进路线.md)
- [`如何扫描Skill.md`](docs/如何扫描Skill.md)
- [`Skill 分级与检查使用指南.md`](docs/Skill%20分级与检查使用指南.md)
- [`Preflight Skill 模板.md`](docs/Preflight%20Skill%20模板.md)
- [`对抗审核报告模板.md`](docs/对抗审核报告模板.md)
