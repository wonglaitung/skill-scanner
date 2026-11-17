# skill-scanner

Agent Skill 工程化检查与对抗审核工具。当前处于**手工触发、试点验证**阶段；检查与被测 Skill 执行全链路在 Docker 容器内完成，CI 仅做静态检查。

- 方案文档：`docs/Agent Skill 工程化检查方案与生产路线.md`（v2.13）
- 当前进度：`progress.md`
- Agent 工作约定：`AGENTS.md`

## 能做什么

- 校验 `SKILL.md` 结构与元数据
- 用 Promptfoo 做确定性回归（边界、PII、AI 腔、格式）
- 用 DeepEval 做指标化评分（相关性、忠实度、幻觉）
- 用 Garak 对 **Skill 包装端点**做发布前扫描
- 用 Semgrep / Ruff 做静态检查，用 gitleaks / Trivy 做供应链扫描
- 为脚本型与工具型 Skill 提供容器内执行环境
- 保存基线并对比回退
- 生成可审计的 Markdown/JSON 报告

## 推荐用法：让 Skill 助手做检查

先完成下面的 Docker 与模型网关配置，然后把 `assistant/skill-release-guide/` 加载到支持 Skill 的 Agent 环境，用自然语言说明目标，不需要自己拼命令：

```text
使用 skill-release-guide 检查 /data/skills/customer-reply。
名称 customer-reply，Owner cs-team，风险 S2，类型 prompt，检查 L2。
先做单次检查，通过后跑 3 轮基线。
```

Skill 会补问缺失信息，依次执行 `init → check → run`，并输出 `reports/<skill>/release-<timestamp>/summary.md`。
它不会自行决定 S 等级或 Owner，也不会编造业务测试用例。

- 完整案例：[`assistant/README.md`](assistant/README.md)
- 报告解读与排障：[`docs/Skill 检查使用指南.md`](docs/Skill%20检查使用指南.md)
- 流程定义：[`assistant/skill-release-guide/SKILL.md`](assistant/skill-release-guide/SKILL.md)

## 快速开始（Docker 唯一入口）

宿主机只需 Docker。Python、Node.js、Promptfoo、DeepEval、Semgrep、Garak、gitleaks、Trivy
和 harness SDK 都已固化在 `skill-checker:local` 镜像内。

### 1. 模型网关

使用 OpenAI-compatible 接口。默认地址：

```text
http://host.docker.internal:8086/v1
模型：qwen3
```

不是默认地址或需要鉴权时：

```bash
export SKILL_API_BASE=https://your-gateway.example/v1
export SKILL_API_KEY=your-key
export SKILL_MODEL=your-model
```

### 2. 命令

```bash
# 首次运行自动构建镜像；更新依赖后可用 REBUILD=1 重建
./scripts/check_in_docker.sh init --source /path/to/skill --name my-skill --owner my-team --risk S2 --type prompt --level L2 --targets targets
./scripts/check_in_docker.sh check --targets targets --skill my-skill
./scripts/check_in_docker.sh run --targets targets --skill my-skill --runs 3

# 发布前 L3
./scripts/check_in_docker.sh run --targets targets --skill my-skill --runs 3 --l3
```

每轮 `manual_check` 在容器内执行结构校验、完整性锁、权限/提示词审计、Semgrep、
供应链扫描（gitleaks/npm audit/Trivy/SBOM）、Promptfoo 与 DeepEval。

输出：

```text
reports/<skill>/release-<timestamp>/
├── summary.md              # Decision、失败项、轮次报告与证据清单
├── summary.json
├── round-1/
│   ├── report.md
│   ├── summary.json
│   ├── run.log
│   ├── promptfoo.json
│   ├── trivy.sarif
│   └── sbom.cdx.json
├── round-2/
├── round-3/
└── garak/                  # 启用 --l3 时
```

### 3. 独立能力（可选）

```bash
# 脚本执行沙箱（network none、只读根、非 root）
./scripts/run_sandboxed.sh -c "import docx; print('sandbox ok')"
./scripts/sandbox_escape_check.sh

# 完整性锁
docker run --rm -v "$PWD:/workspace" skill-checker:local \
  python scripts/skill_lock.py --targets /workspace/targets verify

# 密码学签名（私钥不入库）
python scripts/sign_skills.py keygen --private /secure/skills.pem --public evals/keys/public.pem
python scripts/sign_skills.py sign --key /secure/skills.pem
python scripts/sign_skills.py verify --public evals/keys/public.pem
```

容器外直接运行 `release_assistant.py` 或 `manual_check.py` 会被拒绝（要求 `SKILL_IN_DOCKER=1`）。

## 分级模型

- **S0-S3** 业务风险等级；**L0-L3** 检查深度；`agent: true` 是执行标志，不是等级。
- 最低检查：S2 纯提示词 L2、工具型 L2 + Agent、脚本型 L1；S3/高风险工具发布前 L3。
- 工具型示例：`./scripts/check_in_docker.sh check --targets targets --skill account-balance-query`

完整定义、最低检查矩阵、运行前置、报告解读与排障见
[`docs/Skill 检查使用指南.md`](docs/Skill%20检查使用指南.md)；流程入口见
[`assistant/skill-release-guide`](assistant/skill-release-guide/SKILL.md)。

## 已有 Skill

| Skill | 类型 | 说明 |
|---|---|---|
| `write-report` | 纯提示词 | 银行管理层汇报 |
| `system-specification` | 纯提示词 | 金融系统规格书 |
| `manager-report` | 纯提示词 | 算力申请汇报 |
| `expense-policy-qa` | 纯提示词 | 费用报销问答（示例） |
| `md-to-word` | 提示词 + 脚本 | Markdown 转 Word |
| `account-balance-query` | 提示词 + 工具 | Agent 工具调用测试 Skill |
| `service-ticket-update` | 提示词 + 工具 | 服务工单状态与备注更新（写操作、含权限边界） |
| `cross-skill-router` | 提示词 + 工具 | 跨 Skill 只读路由与委托（含提权防护） |

## 目录结构

```text
docs/                       方案、分级指南、扫描指南、模板
targets/                    目标包（8 个）
adapters/                   Promptfoo/Garak/DeepEval 适配层
adapters/sandbox/           Dockerfile.checks、脚本沙箱、模型端点沙箱
assistant/                  唯一用户入口 skill-release-guide
evals/                      用例、配置、基线
ci/                         校验、静态检查、测试
scripts/check_in_docker.sh  宿主机唯一入口
scripts/                    容器内检查与基线工具
reports/                    运行产物（不入库）
progress.md                 项目进度
AGENTS.md                   Agent 工作约定
```

## 当前结果

| 检查 | 结果 |
|---|---|
| Docker 全链路 | 自定义 Skill `init/check/run` 3 轮通过，Gate PASS |
| SKILL.md 结构校验 | 8 个全部通过 |
| 多轮基线 | 8 个 S2 各 3 轮，Delta Gate 全部 PASS |
| Promptfoo | write 8/8、system 8/8、manager 8/8、expense 5/5、md 5/5、account 15/15、ticket 10/10、cross 9/9 |
| DeepEval | account 7/7；write/system/ticket/cross 均通过 |
| Garak Release v2 | 7 个 LLM Skill，4 个 probe，true compliant 0 |
| Judge 校准 | 20 条，一致率 95% |
| Semgrep / Ruff | 0 findings / 0 errors |
| gitleaks / Trivy / SBOM | 容器内完成；SBOM 622 components |
| Skill 完整性锁 | 8 个全部匹配 |
| 密码学签名 | Ed25519 签名/验签通过，篡改检测符合预期 |

## 已知限制

- Garak Release v2 仍是约定的 4 个 probe，不是全部 Garak probe。
- 每个 S2 只有 3 轮基线，尚未累计 2-4 周稳定性数据。
- Agent 模式使用 Mock 工具，真实工具权限、副作用、回滚尚未验证。
- 网页/文件/RAG/记忆注入尚未覆盖。
- 输入护栏会拒绝编码/解码和训练数据复述请求；未来合法场景需要白名单。
- 私钥托管/轮换、模型网关按 Skill 隔离、可观测性、报告签名/归档仍未闭环。
- Trivy 发现的问题按告警处理，不阻断 PR。
- 目前是人工/半自动检查，不单独作为自动发布审批依据。

## 依赖锁定

检查镜像内固定：Python 3.12、Node 22、Promptfoo 0.125.1、Ruff 0.15.14、
DeepEval 4.3.2、Semgrep 1.85.0、Garak 0.16.0、gitleaks 8.21.2、Trivy 0.76.2。
harness-sdk 锁定 `0.1.0` 与 commit `c4cf29f`，使用独立虚拟环境。
禁止浮动分支或 `latest`；升级依赖后必须重建镜像并重跑基线与 Agent 用例。

## 安全约束

- 只使用合成数据，禁止真实 PII、密钥、生产凭证。
- 模型调用走可配置的 OpenAI-compatible 网关，禁止访问未授权 endpoint。
- 扫描目标必须获得授权，只允许白名单 endpoint。
- 未经验证不要声称测试通过。

## 相关文档

- [`docs/README.md`](docs/README.md)：文档索引
- [`Agent Skill 工程化检查方案与生产路线.md`](docs/Agent%20Skill%20工程化检查方案与生产路线.md)
- [`Skill 检查使用指南.md`](docs/Skill%20检查使用指南.md)：定级、运行前置、报告解读与排障
- [`对抗审核报告模板.md`](docs/对抗审核报告模板.md)
- [`assistant/skill-release-guide`](assistant/skill-release-guide/SKILL.md)：唯一用户入口，从放置目标到报告生成
- [`assistant/README.md`](assistant/README.md)：三种典型使用案例
- [`targets/README.md`](targets/README.md)：目标包结构与容器内命令
- [`evals/garak/README.md`](evals/garak/README.md)：发布前 L3 独立扫描
