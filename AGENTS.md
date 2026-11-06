# AGENTS.md

## 项目

Agent Skill 工程化检查与对抗审核方案。当前处于「文档先行、准备试点」阶段，代码尚未开始。

- 仓库：https://github.com/wonglaitung/skill-scanner
- 方案主文档：`docs/Agent Skill 工程化检查落地方案.md`（v2.11）
- 当前进度：`progress.md`

## 开始工作前必读

1. `docs/Agent Skill 工程化检查落地方案.md`：唯一方案源，工具链、门禁、目录、路线图以它为准。
2. `progress.md`：当前阶段、已完成事项、待办与风险。
3. `docs/生产级演进路线.md`：Phase A-D、验收标准与 KPI。
4. `docs/如何扫描Skill.md`：手工扫描步骤、命令与常见问题。
5. `docs/Skill 分级与检查使用指南.md`：S 风险、L 深度、Agent 标志与最低检查矩阵。
6. `docs/README.md`：文档索引；只保留当前有效文档。

## 当前阶段

2 周试点实施：

- 已导入 3 个 S2 纯提示词 Skill：`write-report`、`system-specification`、`manager-report`。
- 另有示例 Skill `expense-policy-qa`。
- 另有脚本型 S2 Skill `md-to-word`，用于验证 SAST 与脚本适配。
- 安全团队主导。
- 先告警，不阻断 PR。
- 使用本地 OpenAI-compatible 模型网关（`http://localhost:8086/v1`，模型 `qwen3`）。
- Agent 模式已覆盖 3 类工具 Skill：只读查询、写操作、跨 Skill 只读路由。

## 目录约定

已存在：

```text
docs/
targets/                 # 目标包（8 个）
assistant/              # 内部辅助 Skill（不参与目标检查）
adapters/               # Promptfoo/Garak/DeepEval 适配层
evals/                  # 用例、配置、基线
ci/                     # 校验与门禁脚本
scripts/                # 手工检查与基线工具
reports/                # 测试报告与证据（产物不入库）
progress.md
AGENTS.md
```

适配层统一叫 `adapters/`，不要改回 `harness/`，避免与 `wonglaitung/harness` Agent SDK 重名。

## 已锁定的工具链

| 职责 | 主工具 |
|---|---|
| 多语言 SAST | Semgrep |
| Python 质量 | Ruff |
| Shell 检查 | ShellCheck |
| 密钥扫描 | gitleaks |
| 依赖/镜像/IaC/SBOM | Trivy |
| Prompt 回归与红队 | Promptfoo |
| 指标化评分 | DeepEval |
| 发布前独立扫描 | Garak（仅 L3） |
| 运行时兜底 | Docker/gVisor + OPA |

不引入 Bandit、pip-audit、npm audit、trufflehog、SonarQube、Dependabot 作为主工具，除非经过评审。

## 关键约束

- Skill 是通用包装格式，不绑定开发语言或 SDK。
- `wonglaitung/harness` 只作为可选执行层复用（Mock/录制、gate、security、guardrails、tracing），不要求 Skill 迁移。
- 所有模型调用走本地 OpenAI-compatible 网关，禁止访问外部模型。
- 本地模型网关默认 `http://localhost:8086/v1`，可用 `SKILL_API_BASE` 覆盖。
- Garak 只做发布前独立扫描，不进入 PR 门禁。
- DeepEval 用于 L2 指标化评分，分数纳入基线。
- 测试数据默认使用合成数据，禁止真实 PII、密钥、生产凭证。
- 复用 `harness-sdk` 时锁定 `0.1.0` 与 commit `c4cf29f`，使用 `requirements-harness.txt`；优先项目本地 `.venv-harness/`，禁止污染全局环境；禁止浮动版本，保留 MIT 许可声明。
- 未经明确要求，不要提交（commit）或推送（push）。
- 人工模式技术底座完整前，不引入 CI；先完善 `manual_check`、`baseline`、Agent 模式与 SOP。

## 分级模型

统一使用 **S + L + Agent**，详见 `docs/Skill 分级与检查使用指南.md`。

- **S0-S3**：业务风险等级
- **L0-L3**：检查深度
- **`--agent`**：Agent 执行标志，不是等级

最低检查：

| Skill 类型 | 最低检查 |
|---|---|
| S0/S1 纯提示词 | L1 |
| S2 纯提示词 | L2 |
| S3 纯提示词 | L3 |
| 工具型 Skill | L2 + Agent |
| 高风险工具型 | L2 + Agent，发布前 L3 |
| 脚本型 | L1 |

工具越权、参数注入、数据外泄靠 `L2 + Agent`；L3 不能替代 Agent 检查。

## 当前任务

1. F-001~F-009 已修复并复测；write-report 8/8、system-specification 8/8、account-balance-query 15/15。
2. DeepEval S2：相关性 3/3；Faithfulness/Hallucination/ToolCorrectness 通过。
3. Garak Release v2 已通过：4 个 probe 覆盖 7 个 LLM Skill，true compliant 均为 0；输入护栏覆盖 Base64、编码解码、训练数据复述；md-to-word 跳过。
4. 手工检查与基线工具已建：`manual_check.py` 支持 L0-L3，并接入 `capability-audit`、`prompt-audit`；`baseline.py` 支持多轮采集、趋势、Flaky、容差 diff 与 Delta Gate；8 个 S2 均有 3 轮基线。
5. 脚本型 Skill `md-to-word` 已补齐 Promptfoo 5/5、契约测试 4/4、Semgrep 0 findings；SCA/密钥/ShellCheck 待工具安装。
6. CI 骨架保留但不启用；人工模式技术底座完整（路线图 7.1）后再提 CI。
7. Phase A 已落地：Docker 沙箱、供应链扫描、SHA256 完整性锁、Ed25519 签名工具、逃逸检查、模型端点沙箱、网络白名单；剩余私钥托管/轮换、模型网关隔离。
8. Agent 模式复用 `wonglaitung/harness`：Agent 阶段 4 完成；已覆盖 `account-balance-query`、`service-ticket-update`、`cross-skill-router` 三类工具 Skill；全局安全边界已追加到 Skill 提示词。

## 命令（部分已可用）

```bash
# 已可用
python ci/validate_skill.py
ruff check adapters ci evals scripts targets
pytest -q

# 手工检查（推荐）
python scripts/preflight.py --targets targets --skill write-report --risk S2 --level L2
python scripts/manual_check.py --targets targets --skill write-report --level L2
python scripts/scan_all.py --targets targets
python scripts/manual_check.py --targets targets --skill account-balance-query --level L2 --agent
python scripts/manual_check.py --targets targets --skill service-ticket-update --level L2 --agent
python scripts/manual_check.py --targets targets --skill cross-skill-router --level L2 --agent
python scripts/manual_check.py --targets targets --skill system-specification --level L2 --max-tokens 1024
python scripts/baseline.py --targets targets collect write-report --runs 3
python scripts/baseline.py --targets targets trend write-report
python scripts/baseline.py --targets targets diff write-report --tolerance 0.05
python scripts/baseline.py --targets targets gate write-report --tolerance 0.05

# Judge 校准（需本地 qwen3 网关）
JUDGE_MODEL=qwen3 JUDGE_API_BASE=http://localhost:8086/v1 \
  python scripts/judge_calibration.py

# Promptfoo（需本地 qwen3 网关）
SKILL_API_BASE=http://localhost:8086/v1 SKILL_MODEL=qwen3 \
  npx promptfoo eval -c targets/write-report/evals/promptfoo.yaml --max-concurrency 1

# DeepEval（需本地 qwen3 网关）
RUN_LLM_EVALS=1 JUDGE_MODEL=qwen3 SKILL_API_BASE=http://localhost:8086/v1 \
  DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE=300 \
  pytest -q targets/write-report/evals/test_write_report.py

# Garak target L3
TARGETS=targets SKILL=account-balance-query ./evals/garak/scan_release.sh

# 运行时沙箱
./scripts/run_sandboxed.sh -c "import docx; print('sandbox ok')"
./scripts/sandbox_escape_check.sh

# Skill 完整性锁
python scripts/skill_lock.py verify
python scripts/capability_audit.py --skill account-balance-query
python scripts/prompt_audit.py --skill write-report
python scripts/prompt_audit.py --skill write-report --llm

# 密码学签名（私钥不入库）
python scripts/sign_skills.py keygen --private /secure/skills.pem --public evals/keys/public.pem
python scripts/sign_skills.py sign --key /secure/skills.pem
python scripts/sign_skills.py verify --public evals/keys/public.pem

# Agent 本地隔离环境
./scripts/setup_harness_env.sh
./scripts/with_harness.sh python -c "import harness; print(harness.__file__)"


# 严格网络白名单（仅允许本地模型网关）
docker compose -f adapters/sandbox/docker-compose.model.yml up -d --build

# 供应链扫描（Docker）
./ci/run_security.sh

# 尚未安装/接入
semgrep --config p/python --config p/javascript --config p/owasp-top-ten targets/ --error
shellcheck targets/**/*.sh
```

## 进度更新要求

- **随时更新**：每次完成任务、做出决策、发现风险、改变计划或结束一次会话前，立即更新 `progress.md`，不要等到里程碑。
- 更新内容至少包括：当前状态、已完成事项、待办、风险/阻塞。
- 若变更影响方案，先更新主文档，再同步 `progress.md`。
- 不要在 `progress.md` 写未经验证的“已完成”；没有实际运行或产出的，标记为“计划”或“进行中”。

## 验证要求

- 当前没有可运行测试；不要声称测试通过。
- 新增代码后必须运行 Ruff，并在可用时运行 pytest。
- 修改评测配置后必须实际运行 Promptfoo/DeepEval，保留报告。
- 修改文档后检查 Mermaid 代码块与 Markdown 代码围栏是否配对。
- 任何门禁结论必须有报告文件支撑，不能只写结论。

## 文档规范

- 使用中文、Markdown；架构与流程优先使用 Mermaid。
- 术语首次出现时用括号解释。
- 文档变更需更新版本号；不需要维护修订记录。
- 每个里程碑同步更新 `progress.md`，并按「进度更新要求」随时维护。
- 不改动与本任务无关的章节。

## 已知风险

- 本地模型 judge 能力与稳定性未知，需人工校准。
- 首轮没有历史基线，只能记录，不能据此阻断。
- 试点 Skill 未选定，工作量无法准确估算。
- 合规要求未明确，首期只做工程基线证据。
