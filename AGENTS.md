# AGENTS.md

## 项目

Agent Skill 工程化检查与对抗审核方案。当前处于「文档先行、准备试点」阶段，代码尚未开始。

- 仓库：https://github.com/wonglaitung/skill-scanner
- 方案主文档：`docs/Agent Skill 工程化检查落地方案.md`（v2.4）
- 当前进度：`progress.md`

## 开始工作前必读

1. `docs/Agent Skill 工程化检查落地方案.md`：唯一方案源，工具链、门禁、目录、路线图以它为准。
2. `progress.md`：当前阶段、已完成事项、待办与风险。
3. `docs/针对 Agent Skill，业界标准的工程化检查怎么做.md` 与 `docs/解释Garak, Promptfoo, LLM-Eval的用法.md`：背景资料，若与主方案冲突以主方案为准。

## 当前阶段

2 周试点实施：

- 已导入 3 个 S2 纯提示词 Skill：`write-report`、`system-specification`、`manager-report`。
- 另有示例 Skill `expense-policy-qa`。
- 安全团队主导。
- 先告警，不阻断 PR。
- 使用本地 OpenAI-compatible 模型网关（`http://localhost:8086/v1`，模型 `qwen3`）。
- 暂不启用 H3、CI 阻断、独立合规审计。

## 目录约定

已存在：

```text
docs/
skills/                 # 试点 Skill
adapters/               # Promptfoo/Garak/DeepEval 适配层
evals/                  # 用例、配置、基线
ci/                     # 校验与门禁脚本
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
- 复用 `harness-sdk` 时锁定版本（Alpha），保留 MIT 许可声明。
- 未经明确要求，不要提交（commit）或推送（push）。

## 当前任务

1. F-001 已修复：`write-report` 增加 PII 硬规则与自检项，PII 用例 2/2、S2 smoke 6/6。
2. DeepEval S2：相关性 3/3；扩展指标 Faithfulness/Hallucination/ToolCorrectness 通过；F-002 已修复，F-003（`write-report` AI 腔）待处理。
3. Garak 已跑 `dan.Dan_11_0`（1/1）；`promptinject` 需独立环境/并行分批。
4. CI 静态告警已接入；LLM 夜间任务骨架已加（`skill-nightly.yml`，需自托管 runner）；是否设为 required check 待评审。
5. 决定是否扩大 Skill 范围、是否启用 H3。
6. Semgrep 已跑（0 findings）；SCA/密钥/ShellCheck 待工具安装；有脚本的 Skill 再扩展。

## 命令（部分已可用）

```bash
# 已可用
python ci/validate_skill.py
ruff check adapters ci evals skills
pytest -q

# Promptfoo（需本地 qwen3 网关）
SKILL_API_BASE=http://localhost:8086/v1 SKILL_MODEL=qwen3 \
  npx promptfoo eval -c evals/promptfooconfig.smoke.yaml --max-concurrency 1

# DeepEval（需本地 qwen3 网关）
RUN_LLM_EVALS=1 JUDGE_MODEL=qwen3 SKILL_API_BASE=http://localhost:8086/v1 \
  DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE=300 \
  deepeval test run evals/deepeval/test_s2_skills.py

# Garak（已安装 0.16.0；建议独立 venv/容器，避免依赖冲突）
python3 -m garak --target_type rest -G evals/garak/rest_config.json \
  --spec probes.dan.Dan_11_0 --generations 1 \
  --report_prefix "$PWD/reports/garak_dan"

# 尚未安装/接入
semgrep --config p/python --config p/javascript --config p/owasp-top-ten skills/ --error
shellcheck skills/**/*.sh
gitleaks detect --source . --no-git
trivy fs --scanners vuln,misconfig --format sarif --output reports/trivy.sarif .
```

## 进度更新要求

- **随时更新**：每次完成任务、做出决策、发现风险、改变计划或结束一次会话前，立即更新 `progress.md`，不要等到里程碑。
- 更新内容至少包括：当前状态、已完成事项、待办、风险/阻塞。
- 若变更影响方案，先更新主文档与附录 D 修订记录，再同步 `progress.md`。
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
- 文档变更需更新版本号与附录 D 修订记录。
- 每个里程碑同步更新 `progress.md`，并按「进度更新要求」随时维护。
- 不改动与本任务无关的章节。

## 已知风险

- 本地模型 judge 能力与稳定性未知，需人工校准。
- 首轮没有历史基线，只能记录，不能据此阻断。
- 试点 Skill 未选定，工作量无法准确估算。
- 合规要求未明确，首期只做工程基线证据。
