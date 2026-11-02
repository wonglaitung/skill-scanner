# 项目进度

## 项目定位

Agent Skill 工程化检查与对抗审核方案。当前处于「试点实施」阶段，最小骨架已建立。

- 仓库：https://github.com/wonglaitung/skill-scanner
- 方案主文档：`docs/Agent Skill 工程化检查落地方案.md`
- 当前版本：v2.5

## 当前状态

| 项 | 状态 |
|---|---|
| 方案文档 | 已完成 v2.5，已推送 GitHub |
| 代码实现 | 最小骨架已建立（示例 Skill、Adapter、校验脚本、评测配置） |
| CI 流水线 | 未接入 |
| 试点 Skill | 示例 `expense-policy-qa` 已建；真实 S2/S3 Skill 待选 |
| 自动化验证 | 校验脚本、Ruff、pytest、Promptfoo 配置校验通过；Promptfoo 6/6、DeepEval 1/1（qwen3） |
| 本地模型网关 | 已具备，`http://localhost:8086/v1`，模型 `qwen3`；真实评测已跑 |
| Garak | 未安装，发布前扫描待跑 |
| Agent harness SDK | 已有 `wonglaitung/harness`，首期暂不启用 |
| 合规审计 | 暂无明确依据，先做工程基线 |

## 已完成里程碑

| 日期 | 版本/提交 | 内容 |
|---|---|---|
| 2026-11-02 | v1.0 | 初稿：分级体系、威胁模型、Harness、门禁、路线图 |
| 2026-11-02 | v1.1 | 吸收评审意见：公共用例底座、Harness 渐进式、PR 确定性断言、Judge 月度校准、首月只告警 |
| 2026-11-02 | v2.0 | 重构为工程化检查总方案：三横一纵、L0-L3、结构/代码/提示词/对抗/运行时 |
| 2026-11-02 | v2.1 | 锁定主工具组合；Garak 定位为发布前独立扫描器；接入本地模型网关 |
| 2026-11-02 | v2.2 | 引入 DeepEval 指标化评分；指标选择、LocalModel、ToolCorrectness、分数基线 |
| 2026-11-02 | v2.3 | 补充复用 Agent harness SDK；新增 Adapter 契约；适配层目录统一为 `adapters/` |
| 2026-11-02 | v2.4 | 补充对抗审核要求：独立性、覆盖、证据、定级与修复时限、审核门禁与指标 |
| 2026-11-02 | `8e5938c` | 最新提交：对抗审核要求与门禁指标 |
| 2026-11-02 | 试点骨架 | 建立示例 Skill、Adapter、校验脚本、Promptfoo/DeepEval/Garak 配置；Ruff/pytest 通过；对本地 `qwen3` 跑 Promptfoo 6/6、DeepEval 1/1 |

## 最近验证（2026-11-02）

| 检查 | 命令 | 结果 |
|---|---|---|
| SKILL.md 校验 | `python3 ci/validate_skill.py` | OK |
| Ruff | `ruff check adapters ci evals skills` | All checks passed |
| pytest | `pytest -q` | 2 passed, 1 skipped |
| Promptfoo 配置 | `npx promptfoo validate config -c evals/promptfooconfig.yaml` | valid |
| Promptfoo redteam 配置 | `npx promptfoo validate config -c evals/redteam.yaml` | valid |
| Promptfoo 实跑 | `SKILL_API_BASE=http://localhost:8086/v1 SKILL_MODEL=qwen3 npx promptfoo eval -c evals/promptfooconfig.yaml` | 6/6 passed |
| DeepEval | `RUN_LLM_EVALS=1 JUDGE_MODEL=qwen3 deepeval test run evals/deepeval/test_skill.py` | 1/1 passed |
| Garak | `./evals/garak/scan.sh` | 未执行（未安装） |

说明：真实评测使用本地 `qwen3`，网关 `http://localhost:8086/v1`；`reports/` 下的产物未提交。

## 关键决策

### 工具链（已锁定）

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
| 模型接入 | 本地 OpenAI-compatible 网关 |

### 其他决策

- Skill 是通用包装格式，不绑定开发语言或 SDK。
- 现有 `wonglaitung/harness` 作为可选执行层复用，不要求 Skill 迁移。
- 适配层统一使用 `adapters/`，避免与 Agent SDK 重名。
- Garak 不进入 PR 门禁，只做发布前独立扫描。
- DeepEval 用于 L2 指标化评分，0-1 分纳入基线。
- 本地模型网关统一接入 Promptfoo、DeepEval、Garak，不访问外部模型。

## 试点计划（2 周）

### 范围

- 2-3 个 S2/S3 Skill
- 纯提示词为主，无工具调用
- 安全团队主导
- 先告警，不阻断 PR
- 暂不做合规审计

### 第 1 周

- 选定试点 Skill，确认本地模型名与网关地址。
- 建最小目录：`skills/`、`adapters/`、`evals/`、`reports/`。
- 编写 10-20 条确定性用例：正常问答、越权、提示词泄露、直接注入。
- 运行 Promptfoo，记录第一版基线。
- 运行 DeepEval：`AnswerRelevancy`、`Faithfulness`、`Hallucination`。

### 第 2 周

- 增加 Promptfoo redteam：直接注入、越狱、敏感信息套取。
- 可选跑一次轻量 Garak（`promptinject`、`dan`、`leakreplay`）。
- 对发现的问题分级、修复、复测。
- 输出试点报告：覆盖率、基线分、ASR、问题清单、下一阶段建议。
- 复盘是否扩大范围、是否接入 CI 告警。

### 成功标准

| 指标 | 目标 |
|---|---|
| SKILL.md 结构检查通过率 | 100% |
| Promptfoo 确定性用例 | Critical=0 |
| AnswerRelevancy | ≥ 0.7 |
| Faithfulness | ≥ 0.7 |
| Hallucination | ≤ 0.5 |
| 直接注入 ASR | ≤ 5%（仅基线，不阻断） |
| 试点报告 | 完成并评审 |

### 首期不做

- 全量 Skill 覆盖
- PR 阻断
- 独立合规审计
- H3 多步 Agent 编排测试
- 平台化看板与长期运营
- Semgrep/Trivy/gitleaks（除非 Skill 含脚本）

## 待办清单

- [x] 建立示例 Skill `expense-policy-qa`
- [ ] 选定 2-3 个真实 S2/S3 纯提示词 Skill
- [x] 建立 `adapters/`、`evals/`、`reports/`
- [x] 编写 Promptfoo 确定性用例
- [x] 运行 Promptfoo 并记录基线（qwen3，6/6）
- [x] 运行 DeepEval 指标评分（qwen3，1/1）
- [ ] 可选运行轻量 Garak
- [ ] 输出试点报告
- [ ] 决定是否接入 CI 告警
- [ ] 决定是否扩大 Skill 范围
- [ ] 评估是否启用 `wonglaitung/harness` 作为 H3 执行层
- [ ] 有脚本的 Skill 增加 SAST/SCA/密钥检查

## 风险与阻塞

| 风险 | 说明 | 应对 |
|---|---|---|
| 试点 Skill 未选定 | 无法估算工作量 | 安全团队本周内确定 2-3 个 |
| 本地模型 judge 能力未知 | 指标分数可能不稳定 | 先跑 20-50 条人工校准 |
| 仅有单轮基线 | 还不能判断趋势 | 先积累 2-4 周数据再设阈值 |
| 无 CI 平台信息 | 暂不能自动化 | 首期本地/定时运行 |
| 合规要求未明确 | 证据链要求不确定 | 先按工程基线保留 JSON 报告 |

## 维护方式

- **随时更新**：完成任务、做出决策、发现风险、改变计划或结束会话前，立即更新本文件，不等里程碑。
- 每个里程碑额外记录版本号与提交号。
- 方案变更同步更新 `docs/Agent Skill 工程化检查落地方案.md` 的修订记录。
- 代码实现后，在本文件记录命令、覆盖率与试点结果。
