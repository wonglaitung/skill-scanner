# AGENTS.md

## 项目

Agent Skill 工程化检查与对抗审核方案。当前处于「试点实施」阶段，target-only 扫描、单入口流程与 Docker 全链路已落地。

- 仓库：https://github.com/wonglaitung/skill-scanner
- 方案主文档：`docs/Agent Skill 工程化检查方案与生产路线.md`（v2.14）
- 当前进度：`progress.md`

## 开始工作前必读

1. [`docs/Agent Skill 工程化检查方案与生产路线.md`](docs/Agent%20Skill%20工程化检查方案与生产路线.md)：唯一方案源，工具链、门禁、目录、路线图、Phase A-D 以它为准。
2. [`progress.md`](progress.md)：当前阶段、已完成事项、待办与风险。
3. [`assistant/skill-release-guide/SKILL.md`](assistant/skill-release-guide/SKILL.md)：唯一用户入口，初始化、检查、基线、Gate、L3 与报告。
4. [`docs/Skill 检查使用指南.md`](docs/Skill%20检查使用指南.md)：S 风险、L 深度、Agent 标志、最低检查矩阵、报告解读与排障。
5. [`docs/README.md`](docs/README.md)：文档索引；只保留当前有效文档。

## 当前阶段

2 周试点实施：

- 存量目标包（历史试点的纯提示词/示例/脚本型/工具型 Skill）已从仓库移除；
  重新测试时由 `init` 在本地生成，或用 `--targets <私有路径>` 指向仓库外目录。
- 安全团队主导。
- 先告警，不阻断 PR。
- 使用可配置的 OpenAI-compatible 模型网关（`SKILL_API_BASE` / `SKILL_API_KEY` / `SKILL_MODEL`），容器内默认 `http://host.docker.internal:8086/v1`，模型 `qwen3`。
- Agent 模式已覆盖 3 类工具 Skill：只读查询、写操作、跨 Skill 只读路由。
- 检查与被测 Skill 执行全链路在 Docker 容器内完成；宿主机唯一入口 `scripts/check_in_docker.sh`。

## 目录约定

已存在：

```text
docs/
assistant/              # 内部辅助 Skill（不参与目标检查）
adapters/               # Promptfoo/Garak/DeepEval 适配层
adapters/sandbox/Dockerfile.checks  # 统一检查镜像（工具链 + 被测执行依赖）
evals/                  # 用例、配置、基线
ci/                     # 校验与门禁脚本
scripts/                # 手工检查与基线工具
reports/                # 测试报告与证据（产物不入库）
scripts/check_in_docker.sh  # 宿主机唯一入口
progress.md
AGENTS.md
```

`targets/` 不是仓库固定内容：由 `init` 在本地生成，或用 `--targets <私有路径>` 指向仓库外目录。

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
- 模型网关通过 `SKILL_API_BASE` / `SKILL_API_KEY` / `SKILL_MODEL` 配置（OpenAI-compatible），容器内默认 `http://host.docker.internal:8086/v1`。
- 检查全链路容器化：宿主机只依赖 Docker；`release_assistant.py` / `manual_check.py` 仅在容器内运行（`SKILL_IN_DOCKER=1`）。
- Garak 只做发布前独立扫描，不进入 PR 门禁。
- DeepEval 用于 L2 指标化评分，分数纳入基线。
- 测试数据默认使用合成数据，禁止真实 PII、密钥、生产凭证。
- 复用 `harness-sdk` 时锁定 `0.1.0` 与 commit `c4cf29f`，使用 `requirements-harness.txt`；已固化在检查镜像的独立虚拟环境中，禁止浮动版本，保留 MIT 许可声明。
- 未经明确要求，不要提交（commit）或推送（push）。
- 人工模式技术底座完整前，不引入 CI；先完善 `manual_check`、`baseline`、Agent 模式与 SOP。
- **FAIL 处理原则（重要）**：检查中任何 FAIL 都必须先定位真因、修根因、再重跑，不得为让流程跑完或让通过率好看而规避。禁止：删除或弱化断言/检查项、用截断输出（`split`/`transform`）绕过断言、改输入措辞迁就断言、以「非阻断/告警」为由跳过真实发现、用后台轮询（如 `tail -1`）掩盖失败信号。发现步骤级 FAIL 必须立即停止、修复后再重跑。

## 分级模型

统一使用 **S + L + Agent**，权威定义见
[`docs/Skill 检查使用指南.md`](docs/Skill%20检查使用指南.md)。

- **S0-S3**：业务风险等级
- **L0-L3**：检查深度
- **`agent: true`**：Agent 执行标志（写入 manifest），不是等级
- **`type`**：项目自定义的 Skill 类型（非业界标准），取值 `prompt`/`script`/`tool`，
  分别指纯提示词、脚本型（确定性脚本）、工具型（LLM Agent 调工具）；详见
  [`docs/Skill 检查使用指南.md` §0](docs/Skill%20检查使用指南.md)

最低检查由 **类型 × 风险** 共同决定：类型决定检查手段，风险决定深度（L 级别）。
下表每行都是一个组合，完整二维速查见 [`docs/Skill 检查使用指南.md` §4](docs/Skill%20检查使用指南.md)。

| 类型 × 风险组合 | 最低检查 |
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
3. Garak Release v2 历史结果（true compliant 0）基于当时的全局安全边界与运行时输入护栏；这两类补丁现已移除（它们改变被测对象、掩盖源 Skill 真实问题）。当前检查针对纯源 Skill：已实测 write-report 的 Garak true compliant 为 42/18/66（Base64 解码、训练数据复述），需由 Skill 自身补规则；md-to-word 跳过。
4. 手工检查与基线工具已建：`manual_check.py` 支持 L0-L3，并接入 `capability-audit`、`prompt-audit`；`baseline.py` 支持多轮采集、趋势、Flaky、容差 diff 与 Delta Gate；8 个 S2 均有 3 轮基线。
5. 脚本型 Skill `md-to-word` 已补齐 Promptfoo 5/5、契约测试 4/4、Semgrep 0 findings；SCA/密钥/ShellCheck 待工具安装。
6. CI 骨架保留但不启用；人工模式技术底座完整（路线图 7.1）后再提 CI。
7. Phase A 已落地：Docker 沙箱、供应链扫描、SHA256 完整性锁、Ed25519 签名工具、逃逸检查、模型端点沙箱、网络白名单；剩余私钥托管/轮换、模型网关隔离。
8. Agent 模式复用 `wonglaitung/harness`：Agent 阶段 4 完成；已覆盖 `account-balance-query`、`service-ticket-update`、`cross-skill-router` 三类工具 Skill；不再向 Skill 提示词追加全局安全边界。
9. 检查与被测执行全链路 Docker 化：统一镜像 `skill-checker:local`，唯一入口 `scripts/check_in_docker.sh`，网关通过 `SKILL_API_BASE`/`SKILL_API_KEY` 配置。

## 命令（Docker 入口）

```bash
# 宿主机唯一入口（首次自动构建镜像；REBUILD=1 可强制重建）
./scripts/check_in_docker.sh init --source /path/to/skill --name my-skill --owner my-team --risk S2 --type prompt --level L2 --targets targets
./scripts/check_in_docker.sh check --targets targets --skill my-skill
./scripts/check_in_docker.sh run --targets targets --skill my-skill --runs 3

# 发布前 L3
./scripts/check_in_docker.sh run --targets targets --skill my-skill --runs 3 --l3

# 模型网关（OpenAI-compatible，默认 http://host.docker.internal:8086/v1）
export SKILL_API_BASE=https://your-gateway.example/v1
export SKILL_API_KEY=your-key
export SKILL_MODEL=your-model

# 容器内调试其他命令
docker run --rm -v "$PWD:/workspace" -w /workspace skill-checker:local \
  python scripts/baseline.py --targets /workspace/targets trend write-report

# 独立脚本沙箱
./scripts/run_sandboxed.sh -c "import docx; print('sandbox ok')"
./scripts/sandbox_escape_check.sh

# 密码学签名（私钥不入库）
python scripts/sign_skills.py keygen --private /secure/skills.pem --public evals/keys/public.pem
python scripts/sign_skills.py sign --key /secure/skills.pem
python scripts/sign_skills.py verify --public evals/keys/public.pem
```

## 进度更新要求

- **随时更新**：每次完成任务、做出决策、发现风险、改变计划或结束一次会话前，立即更新 `progress.md`，不要等到里程碑。
- 更新内容至少包括：当前状态、已完成事项、待办、风险/阻塞。
- 若变更影响方案，先更新主文档，再同步 `progress.md`。
- 不要在 `progress.md` 写未经验证的“已完成”；没有实际运行或产出的，标记为“计划”或“进行中”。

## 验证要求

- 现有 pytest 测试（44 passed, 8 skipped）；新增代码后必须实际运行，不要只写结论。
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
