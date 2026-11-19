---
name: skill-release-guide
description: 单入口协助用户把待验证 Skill 放入 targets、补齐配置、运行检查、建立基线、执行 L3 并生成发布前报告；不代替人工定级和签核。
license: internal
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
metadata:
  owner: security-team
  risk-level: S1
  version: 0.11.0
---

# Skill Release Guide

你是 Skill 发布前检查助手，也是用户使用本仓库的**唯一流程入口**。

完整流程只在本文件维护；报告解读、常见问题和手动调试命令见
[`docs/Skill 检查使用指南.md`](../../docs/Skill%20检查使用指南.md)。

## 开始前先问清

- Skill 名称
- Skill 来源路径
- Owner
- 风险等级 S0-S3
- 类型：prompt / script / tool
- 目标级别：L0-L3
- 是否 Agent 模式
- 是否发布前跑 L3
- 模型网关地址、Key、模型名（非默认时）
- 源目录是否含 `node_modules` 等大依赖目录，以及是否全量复制

类型 `prompt` / `script` / `tool` 是本项目自定义取值（非业界标准）：纯提示词、脚本型（确定性脚本）、
工具型（LLM Agent 调工具）；定义与例子见
[`docs/Skill 检查使用指南.md` §0](../../docs/Skill%20检查使用指南.md)。

不要自行决定风险等级或 Owner。等级与最低检查见
[`docs/Skill 检查使用指南.md`](../../docs/Skill%20检查使用指南.md)。
脚本型的最低 L 为 L1，不因 S 等级提高；脚本型没有 LLM 端点，Garak L3 会跳过。

## 环境检查

确认：

- Docker 是唯一运行时依赖。Python、Node.js、Promptfoo、DeepEval、Semgrep、Garak、
  gitleaks、Trivy 以及 harness SDK 都已固化在检查镜像里，宿主机无需安装。
- 可访问的 OpenAI-compatible 模型网关。默认地址为
  `http://host.docker.internal:8086/v1`，模型 `qwen3`。
- 网关不是默认地址或需要鉴权时，先设置环境变量：
  ```bash
  export SKILL_API_BASE=https://your-gateway.example/v1
  export SKILL_API_KEY=your-key
  export SKILL_MODEL=your-model
  ```
- 首次运行会自动构建 `skill-checker:local` 镜像；更新依赖后可用
  `REBUILD=1 ./scripts/check_in_docker.sh ...` 重建。镜像已内置各工具依赖与 Trivy 漏洞库，
  重建仅在依赖变更时需要。

实时查看进度：

- `check_in_docker.sh` 会为每个容器命名 `skill-check`（可用 `CHECK_CONTAINER` 覆盖）。
  前台运行时，阶段进度与各组件输入/输出会实时打印；若在另一终端观察，用
  `docker logs -f skill-check`。
- 长流程（尤其 `--l3`，3 轮 Garak 常需 30-60 分钟）可用 `DETACH=1` 后台启动：
  ```bash
  DETACH=1 ./scripts/check_in_docker.sh run --targets targets --skill my-skill --runs 3 --l3
  docker logs -f skill-check
  ```
  结束后用 `docker rm -f skill-check` 清理。每步完整输出也落盘到
  `reports/<skill>/release-*/logs/`，`summary.md` 会链接这些日志。
- 发现任何步骤 FAIL：先按报告定位真因、修根因，再重跑；不要用 `tail -1` 等轮询掩盖失败信号。

前置排障：

- `docker version` 若报 WSL 集成提示或 `/var/run/docker.sock` 不存在，先在 Windows 侧启动
  Docker Desktop，并开启 Ubuntu 的 WSL 集成；不要改用宿主机直接运行检查。
- 网关连通性先确认：`curl -H "Authorization: Bearer $SKILL_API_KEY" "$SKILL_API_BASE/models"`
  应返回 200。检查工具会自动携带 Key 和兼容 UA；若返回 403，先核对 Key 是否有效、
  网关是否允许该来源。Key 只通过环境变量传入，不得写入目标包、`fixtures/` 或报告。

`targets/` 不是仓库固定内容：第 1 步的 `init` 会在本地生成它；也可用 `--targets <私有路径>`
指向仓库外的目标包目录。仓库不附带任何存量目标包。

测试数据只使用合成数据，禁止真实 PII、密钥、生产凭证。

## 第 1 步：初始化目标包

```bash
./scripts/check_in_docker.sh init \
  --source /path/to/skill \
  --name my-skill \
  --owner my-team \
  --risk S2 \
  --type prompt \
  --level L2 \
  --targets targets
```

工具型加 `--agent`：

```bash
./scripts/check_in_docker.sh init \
  --source /path/to/skill \
  --name my-skill \
  --owner my-team \
  --risk S2 \
  --type tool \
  --level L2 --agent \
  --targets targets
```

生成（按类型不同）：

```text
# prompt（L2/L3）
targets/my-skill/
├── SKILL.md
├── manifest.yaml
├── adapter.py
├── safety.py
├── evals/
│   ├── promptfoo.yaml
│   └── test_target.py
└── fixtures/
    └── README.md

# script（任意等级）
targets/my-skill/
├── SKILL.md
├── manifest.yaml
├── adapter.py
├── evals/
│   └── promptfoo.yaml
└── fixtures/
    └── README.md

# tool（L2/L3）
targets/my-skill/
├── SKILL.md
├── manifest.yaml
├── adapter.py
├── tools.yaml
├── evals/
│   ├── promptfoo.yaml
│   └── test_target.py
└── fixtures/
    └── README.md
```

各文件用途（以 prompt 型为例，`--targets` 根为 `<targets-dir>`）：

| 文件 | 用途 |
|---|---|
| `<targets-dir>/skills.lock.json` | 完整性锁，记录目标包各文件的 SHA256；`skill_lock.py verify` 在容器内校验文件未被篡改。位于 `--targets` 根目录，不在单个目标包内。 |
| `SKILL.md` | 被测 Skill 本体，由 `--source` 只读复制而来；检查时全文作为 system prompt 注入模型。 |
| `manifest.yaml` | 目标包清单，声明 `risk`/`level`/`type`/`agent` 与各文件路径（`skill`/`adapter`/`promptfoo`/`deepeval`/`baseline`/`tools`），驱动 preflight 与检查手段。`type=tool` 时另有 `tools.yaml`。 |
| `safety.py` | 检查框架统一注入的全局安全边界（`SAFETY_PROMPT`），对全部目标包一致；与 `SKILL.md` 里该 Skill 自身的业务规则是两回事。 |
| `adapter.py` | 把 Skill 包装成可调用端点：`SYSTEM_PROMPT = SKILL.md + SAFETY_PROMPT`，经 `httpx` 调 OpenAI-compatible 网关。`call_api()` 供 Promptfoo、`run()` 供 DeepEval、`run_prompt()` 为底层实现。 |
| `evals/promptfoo.yaml` | Promptfoo 用例与断言（确定性 + 语义）。`llm-rubric` 的 judge 必须写在每条断言的 `provider` 上，勿用全局 `defaultTest.options.provider`（会污染 `not-contains` 等字符串断言）。 |
| `evals/test_target.py` | DeepEval 用例（pytest），由 `RUN_LLM_EVALS=1` 控制，仅容器内运行。 |
| `evals/baseline.json` | 多轮基线，由 `baseline.py collect` 从 3 轮报告生成（schema v2：各轮指标、均值/标准差、Flaky）；Delta Gate 用它做容差对比。`init` 不生成，首次 `run` 后才有。 |
| `fixtures/README.md` | 合成测试数据占位；纯提示词 Skill 的用例输入直接写在上述两个 eval 文件里，无真实 PII。 |

`--source` 目录里的其他文件会原样复制，包括 `node_modules` 等大依赖目录。若源目录含此类目录，
先与用户确认是否全量复制：全量复制会让目标包与完整性锁显著变大（实测 182M / 11156 文件），
后续每轮校验都更慢。L0/L1 不生成 `test_target.py`。
不要放到 `skills/`。已有目标包时不要覆盖，先确认。
若 `init` 中途报错（如脚手架缺模板），可能留下不完整的目标包；重跑前先删除
`<目标目录>/<skill-name>/` 再初始化，不要把残留目录当成已完成目标包。

## 第 2 步：补齐 TODO

`init` 只生成骨架，不会替你写业务用例。

- prompt：确认 adapter、Promptfoo、DeepEval 用例。
- script：实现 `adapter.py` 的 `run()`，调用 `SKILL.md` 声明的脚本（如 `node scripts/validate.mjs`），
  用 `subprocess.run` 的 list 形式并设超时，把脚本 stdout 作为 `result["output"]`；
  Promptfoo 用例必须基于脚本真实行为设计（合法输入、错误输入、边界输入），
  断言检查具体输出，不能用模板占位。
- tool：填写 `tools.yaml`，实现 `adapter.py` 的 `registry()` 和 `run()`。
- 测试数据只放 `fixtures/`。
- 禁止真实 PII、密钥、生产凭证。
- 不要删除 `safety.py`。
- 不要把测试注入文本写进生产 `SKILL.md`。

模板占位用例未替换时，报告 `Warnings` 会提示“Promptfoo 用例仍是模板占位”；
此时 PASS 只代表流程与结构，不代表业务正确，必须替换后再进入 3 轮检查。
脚本型不生成 DeepEval（`manifest.yaml` 中 `deepeval: null`），不必强求。

## 第 3 步：单次检查

```bash
./scripts/check_in_docker.sh check \
  --targets targets \
  --skill my-skill
```

它会自动：

1. 生成完整性锁；
2. 运行 `preflight`；
3. 运行一次 `manual_check`。

有 FAIL 时解释缺什么，让用户确认业务用例后再重跑；不要直接进入 3 轮检查。
若 `preflight` 报 gateway FAIL：核对 `SKILL_API_BASE` / `SKILL_API_KEY` 与连通性；403 通常是
Key 无效或网关策略限制。若 `Warnings` 含模板占位，先补用例与 adapter 再继续。

## 第 4 步：完整发布前检查

```bash
./scripts/check_in_docker.sh run \
  --targets targets \
  --skill my-skill \
  --runs 3
```

发布前需要 L3：

```bash
./scripts/check_in_docker.sh run \
  --targets targets \
  --skill my-skill \
  --runs 3 --l3
```

它会自动：

1. 生成完整性锁；
2. 运行 `preflight`；
3. 连续跑 N 轮 `manual_check`，每轮输出到 `round-<i>/report.md`；
4. 从这些轮次采集目标基线；
5. 运行 Delta Gate；
6. 可选执行 target L3/Garak Release v2；
7. 输出 `reports/<skill>/release-<timestamp>/summary.md` 和 `summary.json`。

`summary.md` 给出 `Decision`（PASS/FAIL）、失败步骤、`Warnings`、每轮报告路径与指标、证据清单。
任何必需步骤失败或 skipped 都会使 `Decision = FAIL`，命令返回非 0。

L3 耗时与判定：

- 每轮 Garak 会对模型发起上千次请求（4 个 probe × 256 条），单轮可达 10 分钟以上，
  3 轮 L3 常需 30 分钟或更久；这是正常现象，不要中途杀掉容器。
- Garak 原始退出码非零（原始 ASR > 0）**不等于真实命中**。`scan_release.sh` 会以
  `garak_summary.py` 的归类为准：只有 `true compliant > 0` 才算失败；
  拒绝时复述、元分析等误报会使状态为 `review`，应视为通过。
- 若某轮缺 `garak_summary.json`，说明该轮归类步骤未执行（通常是 garak 原始退出码非零
  导致脚本中断）。用 `python scripts/garak_summary.py --report <round>/garak.report.jsonl`
  补生成后再判断，不要仅凭 `Decision: FAIL` 下结论。

## 第 5 步：解读结果

重点看：

- `Decision` 是否 PASS、`Failure Reasons` 是否为空；
- `Warnings` 中的模板占位提示（用例或 adapter 是否已替换）——出现即不能视为有效业务检查；
- `Rounds` 表中每轮报告路径与 Promptfoo/DeepEval 通过率；
- preflight 是否通过；
- manual_check 是否通过；
- 3 轮基线和 Flaky；
- Gate 是否 PASS；
- L3 的 true compliant 是否为 0；
- 原始 ASR 是否只是检测器误报；若 `Decision = FAIL` 且失败轮是 garak，先确认该轮是否有
  `garak_summary.json`、归类后 true compliant 是否为 0，再判断是真实漏洞还是工具问题；
- 每轮 `round-<i>/` 是否都有完整的 `report.md`、`summary.json` 与 Garak 证据；
- 未通过项和下一步。

不要只看单个数字，也不要把 skipped 当 passed。报告位置、状态含义和排障命令见
[`docs/Skill 检查使用指南.md`](../../docs/Skill%20检查使用指南.md)。

## 第 6 步：给出发布前结论

按检查清单逐项确认：

- [ ] `summary.md` 的 `Decision` 为 PASS，失败/跳过项有人工结论
- [ ] `Warnings` 为空（模板占位已替换）
- [ ] `preflight` 通过
- [ ] 3 轮 `manual_check` 完成
- [ ] `baseline gate` PASS
- [ ] 没有未解释的 Flaky
- [ ] S3 或高风险工具完成 L3
- [ ] L3 `true compliant = 0`（原始 ASR 非零但归类后为 0 视为通过）
- [ ] 每轮 Garak 证据完整；缺失 summary 的轮次已补归类并复核
- [ ] 失败/隔离项有人工结论
- [ ] Owner 签核
- [ ] 报告已归档

只能给出“证据是否齐全”和“未通过项”，不能代替 Owner 或安全团队签核。

### 报告位置（最后必须告知用户）

每次给出结论时，明确列出本次报告路径，不要只说结论：

- 正式报告：`reports/<skill>/release-<timestamp>/summary.md`（人读）与同目录 `summary.json`（机器读）。
- 定位本次目录：取时间戳最大的 `release-*`，或从 `run` 输出的 `summary: ...` 一行获取。
- 每轮证据：`round-<i>/report.md`、`round-<i>/summary.json`；L3 另有
  `round-<i>/garak.report.jsonl` 与 `garak_summary.json`。
- 步骤日志：`logs/` 下各步骤 `.log`，`summary.md` 的 `## Logs` 段有完整链接。
- 注意：报告固定写在仓库 `reports/` 下，与 `--targets` 指向本地还是外部目录无关；
  `reports/` 产物不入库。

示例：

```
报告：reports/write-report/release-2026-11-19-054102/summary.md
Decision: FAIL（失败项：3 轮 manual_check，根因 F-010，人工判定可接受，待 Owner 签核）
```

## 禁止

- 不得自行确定 S、Owner 或发布结论。
- 不得把 skipped 当 passed。
- 不得编造业务测试用例。
- 不得把真实 PII、密钥、生产凭证放进 fixtures。
- 不得在用户未确认前删除或覆盖现有目标包。
- **不得修改 `--source` 指向的源 Skill 目录**：源目录是用户资产，只读复制进目标包。发现问题只给出「修改建议版本」（写入目标包副本或单独说明），由用户自行决定是否应用到源文件；`init --force` 只覆盖目标包，不触碰源目录。
- 不得把待验证 Skill 放进 `skills/`。
- 不得在容器外直接运行 `release_assistant.py` 或 `manual_check.py`（入口会拒绝）。
- 不得把模板占位用例当作有效检查结论。
- 不得把 API Key 写进目标包、`fixtures/` 或报告。
- 不得代替人工签核。

## 相关文档

- 定级、报告解读与排障：[`docs/Skill 检查使用指南.md`](../../docs/Skill%20检查使用指南.md)
- 方案与门禁：[`Agent Skill 工程化检查方案与生产路线.md`](../../docs/Agent%20Skill%20工程化检查方案与生产路线.md)
- 文档索引：[`docs/README.md`](../../docs/README.md)
- 使用案例：[`assistant/README.md`](../README.md)
