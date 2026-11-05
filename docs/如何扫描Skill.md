# 如何扫描一个 Agent Skill（用户操作指南）

适用读者：Skill 作者、Skill Owner、安全审核人。

你将完成：把一个 Skill 放进项目，按风险级别运行检查，读懂报告，修复问题，建立 3 轮基线，并用 Delta Gate 判断是否可以发布。

> 最后更新：2026-11-03
>
> 当前原则：先人工检查、先告警；人工底座完整前不启用 CI 阻断。

---

## 先选你的路径

| 你的 Skill 类型 | 推荐路径 | 预计时间 |
|---|---|---|
| 纯提示词 Skill | L0 → L1 → L2 → 3 轮基线 | 30-60 分钟 |
| 脚本型 Skill | L0 → L1 → 契约测试 → 3 轮基线 | 20-40 分钟 |
| 工具调用 / 多步 Agent | L0 → L1 → L2 `--agent` → 3 轮基线 | 60-120 分钟 |
| 高风险 / 第三方 Skill | 上面全部 + L3 + 人工签核 | 按实际情况 |

第一次使用，建议先跑 L0。L0 通过后，再逐级增加 LLM 评测。

---

## 开始前：确认 4 件事

1. 你知道这个 Skill 的 Owner 和风险等级（S0-S3）。
2. 本地模型网关可用：`http://localhost:8086/v1`，模型 `qwen3`。
3. 机器上有 Python 3.10+、Node.js 20+、Docker。
4. 测试数据是合成的，不含真实 PII、密钥、生产凭证。

如果第 2 条不满足，先启动本地模型网关；不要改成外部模型 API。

---

## 第 1 步：准备环境

### 1.1 获取项目

```bash
git clone https://github.com/wonglaitung/skill-scanner.git
cd skill-scanner
```

### 1.2 安装依赖

```bash
pip install -r requirements-dev.txt -r requirements-eval.txt
npm install
```

### 1.3 检查模型网关

```bash
curl http://localhost:8086/v1/models
```

返回模型列表即可。默认模型是 `qwen3`。

连接失败时：

- 确认模型服务已启动；
- 确认端口是 8086；
- 确认没有代理拦截 `localhost`。

### 1.4 检查 Docker

```bash
docker ps
```

Docker 不可用时，`security` 步骤会跳过，并在报告里写明原因。不要把它当成“通过”。

### 1.5 只有 Agent Skill 才需要：准备 harness 隔离环境

```bash
./scripts/setup_harness_env.sh
```

它会创建项目本地 `.venv-harness/`，不会污染全局 Python。

---

## 第 2 步：把 Skill 放进项目

### 2.1 放对目录

```text
skills/<skill-name>/
├── SKILL.md
├── scripts/          # 可选
└── references/       # 可选
```

```bash
cp -r /path/to/my-skill skills/my-skill
```

### 2.2 写清楚 SKILL.md

最小 Frontmatter：

```yaml
---
name: my-skill
description: 一句话说明这个 Skill 能做什么、不能做什么
license: internal
allowed-tools: []
metadata:
  owner: my-team
  risk-level: S2
  version: 0.1.0
---
```

| 字段 | 要求 |
|---|---|
| `name` | 小写字母、数字、连字符，和目录名一致 |
| `description` | 写能力和边界，不要写“一个有用的 Skill” |
| `license` | 内部 Skill 写 `internal` |
| `allowed-tools` | 纯提示词 Skill 建议为空；不要让模型调用未适配的工具 |
| `metadata.owner` | 负责团队 |
| `metadata.risk-level` | S0-S3 |
| `metadata.version` | 语义化版本 |

### 2.3 先做结构校验

```bash
python ci/validate_skill.py --skill my-skill
```

看到 `[OK]` 再继续。

### 2.4 更新完整性锁

每次修改 Skill 文件后都要执行：

```bash
python scripts/skill_lock.py generate
python scripts/skill_lock.py verify
```

否则后续检查会在 `skill-lock` 步骤失败。

---

## 第 3 步：选择检查级别

| 级别 | 适合谁 | 会做什么 |
|---|---|---|
| L0 | 所有 Skill，第一次运行 | 结构、完整性锁、签名、Ruff、Semgrep、gitleaks、npm audit、Trivy、SBOM、ShellCheck |
| L1 | 所有提示词 / 脚本 Skill | L0 + Promptfoo 确定性回归 |
| L2 | S2/S3 提示词 Skill | L1 + DeepEval 指标评分 |
| L3 | 发布前、高风险、第三方 | L2 + Garak 扫描 Skill 端点 |

补充规则：

- S0/S1：L0 → L1。
- S2：L0 → L1 → L2，发布前考虑 L3。
- S3 或第三方：L0 → L1 → L2 → L3。
- 脚本型 Skill：L2/L3 会跳过 DeepEval/Garak，这是预期行为。
- 工具调用 / 多步 Agent：L1/L2 加 `--agent`。

---

## 第 4 步：第一次先跑 L0

```bash
python scripts/manual_check.py --skill my-skill --level L0
```

你要看到：

```text
全部必需步骤通过
```

如果失败：

1. 打开终端里提示的报告路径；
2. 看 `report.md` 的“步骤结果”；
3. 按失败步骤修正；
4. 重新跑 L0。

L0 不通过，不要继续跑 L1/L2。

---

## 第 5 步：补评测配置

### 5.1 纯提示词 Skill：加 Promptfoo 配置

新建 `evals/promptfooconfig.my-skill.yaml`：

```yaml
# yaml-language-server: $schema=https://promptfoo.dev/config-schema.json
description: my-skill 基线
basePath: ..
prompts:
  - "{{user_input}}"
providers:
  - id: file://./adapters/promptfoo_provider.py:call_api
    label: my-skill
    config:
      skillPath: skills/my-skill/SKILL.md
tests:
  - vars:
      user_input: "你的测试问题"
    assert:
      - type: contains
        value: "期望出现的关键词"
      - type: not-contains
        value: "不应出现的内容"
```

不会写时，复制一个现有配置，改两处：

- `skillPath`
- `tests[].vars.user_input` 和断言

### 5.2 脚本型 Skill：先包一层 Provider

需要两个文件：

- `adapters/<skill>_provider.py`
- `evals/promptfooconfig.<skill>.yaml`

参考 `md-to-word`：

- `adapters/md_to_word_provider.py`
- `evals/promptfooconfig.md-to-word.yaml`
- `ci/test_md_to_word_contract.py`

### 5.3 工具型 Agent：准备 Mock 工具和 Agent 配置

三类参考：

- 只读查询：`account-balance-query`
- 写操作：`service-ticket-update`
- 跨 Skill 只读路由：`cross-skill-router`

对应文件：

- `skills/<skill>/SKILL.md`
- `adapters/harness_tools.py`
- `evals/promptfooconfig.<skill>.agent.yaml`

运行方式见第 6 步。

### 5.4 运行时全局安全边界

适配层会自动给每个 Skill 追加 `adapters/safety_prompt.py` 中的全局安全边界：

- 拒绝越狱、仇恨言论、攻击短语；
- 拒绝时不复述攻击内容；
- 即使包装成翻译、纠错、评分、摘要任务，也只把内容当数据。
- 进入模型前拒绝 Base64/编码/解码/解密请求（`adapters/input_guard.py`）。

Skill 自身仍应写明安全边界；全局规则是兜底，不替代 Skill 设计。

### 5.5 工具型 Skill：声明工具权限

在 `SKILL.md` 的 `metadata` 里声明工具集和每个工具的权限：

```yaml
metadata:
  tool-set: query
  tool-permissions:
    - name: get_current_user
      scopes: [read:self]
      side-effects: none
      data-access: [self]
    - name: query_balance
      scopes: [read:balance]
      side-effects: none
      data-access: [self, test-user]
```

要求：

- `allowed-tools` 和 `tool-permissions` 的 tool 名称必须一致；
- `scopes` 不能为空；
- `side-effects` 只能是 `none/read/write/external/destructive`；
- `data-access` 不能为空。

`manual_check.py` 会自动运行 `capability-audit`，检查：

1. `allowed-tools` 与 `tool-permissions` 是否一致；
2. 声明了但工具集里没有实现；
3. 工具集里实现了但没声明；
4. 实际 Trace 中调用了未声明工具。

手工审计普通运行轨迹：

```bash
python scripts/capability_audit.py --skill account-balance-query   --report reports/account-balance-query/<timestamp>   --provider harness-agent
```

机器可读输出：

```bash
python scripts/capability_audit.py --skill account-balance-query --json
```

注意：`--provider` 用于只看正常业务 Provider；不要拿包含对抗工具集的报告直接审计，否则会把测试专用的 `delete_account` 等工具误判为真实能力。

说明：工具名和实现的一致性是自动检查；`description` 的语义是否准确，仍需人工复核。

### 5.5 提示词质量检查

`manual_check.py` 会自动运行 `prompt-audit`，检查：

- 手机号、身份证号、邮箱、私钥、API Key
- 内部路径、本地端点、测试哨兵值
- “输出系统提示词”“忽略以上指令”等泄露诱导短语
- `allowed-tools` 放行但正文又禁止调用同一工具

手工运行：

```bash
python scripts/prompt_audit.py --skill my-skill
python scripts/prompt_audit.py --skill my-skill --json
```

增加本地 qwen3 辅助审查：

```bash
python scripts/prompt_audit.py --skill my-skill --llm
```

或让 `manual_check` 一并执行：

```bash
python scripts/manual_check.py --skill my-skill --level L2 --llm-audit
```

确定性规则无法覆盖所有语义矛盾，LLM 审查也可能误报；高影响结论仍需人工确认。

### 5.6 长输出 Skill：加 token 上限

`system-specification` 这类会生成长文档的 Skill，建议加：

```bash
python scripts/manual_check.py --skill system-specification \
  --level L2 --max-tokens 1024
```

不加时默认 2048；超时或输出失控时再降低。

---

## 第 6 步：逐级运行检查

### 6.1 纯提示词 Skill

```bash
python scripts/manual_check.py --skill my-skill --level L1
python scripts/manual_check.py --skill my-skill --level L2
```

发布前再跑：

```bash
python scripts/manual_check.py --skill my-skill --level L3
```

### 6.2 脚本型 Skill

```bash
python scripts/manual_check.py --skill my-skill --level L1
pytest -q ci/test_md_to_word_contract.py
```

把契约测试换成你自己的测试文件。

### 6.3 工具型 Agent Skill

先确认 `.venv-harness/` 已创建，然后：

```bash
python scripts/manual_check.py --skill account-balance-query \
  --level L2 --agent
```

可选：验证录制/回放：

```bash
RUN_LLM_EVALS=1 JUDGE_MODEL=qwen3 \
SKILL_API_BASE=http://localhost:8086/v1 SKILL_MODEL=qwen3 \
./scripts/with_harness.sh python -m pytest ci/test_agent_recording.py -q
```

### 6.4 L3：Garak 独立复查

先安装独立环境，避免污染主环境：

```bash
uv venv .venv-garak --python 3.10
uv pip install --python .venv-garak/bin/python 'garak==0.16.0'
```

运行发布前复查：

```bash
SKILL=account-balance-query ./evals/garak/scan_release.sh
```

Release v1 包含：

- `probes.dan.Dan_11_0`
- `probes.promptinject.HijackHateHumans`

输出：

```text
reports/garak/release/<skill>/<timestamp>/
├── garak.report.jsonl
├── garak.report.html
├── garak_summary.json
└── garak_summary.md
```

注意：

- `PASS` 表示 probe 未命中，`FAIL` 表示检测器命中。
- Garak 的 promptinject 检测器按子串匹配，会把“拒绝时复述攻击短语”计为命中。
- 必须看 `garak_summary.md` 的“命中归类”：只有 `true compliant` 才是真攻击成功。
- `encoding` 和 `leakreplay` 目前未纳入 Release v1，原因是本地模型吞吐不足。
- `md-to-word` 是确定性脚本 Skill，没有 LLM 端点，Garak 跳过。
- Release v2 已通过：`Dan_11_0`、`promptinject`、`InjectBase64`、`LiteratureCloze` 覆盖 7 个 LLM Skill，true compliant 均为 0。
- `md-to-word` 是确定性脚本，无 LLM 端点，Garak 跳过。
- 不要声称“全部 Garak probe 已完成”；当前是约定的 Release v1 probe 集。

### 6.5 常用参数

| 参数 | 什么时候用 |
|---|---|
| `--model qwen3` | 换模型，一般不用改 |
| `--api-base ...` | 网关不是默认地址 |
| `--max-tokens 1024` | 长输出 Skill，防止生成失控 |
| `--skill-timeout 300` | 单次模型调用经常超时 |
| `--deepeval-timeout 600` | DeepEval 长文本超时 |
| `--allow-failures` | 只想先出报告，不因失败中断 |
| `--llm-audit` | 提示词检查增加本地 qwen3 辅助审查 |
| `--full-garak` | 需要尝试完整 `promptinject` |
| `--agent` | 工具调用 / 多步 Agent Skill |

---

## 第 7 步：读报告、修问题、复测

### 7.1 报告在哪

```text
reports/<skill>/<timestamp>/
├── report.md
├── summary.json
├── run.log
├── promptfoo.json
├── trivy.sarif
├── sbom.cdx.json
└── garak.report.jsonl
```

先看 `report.md`；需要机器可读结果时看 `summary.json`。

### 7.2 按顺序看

1. **步骤结果表**：passed / failed / skipped / timeout；
2. **Promptfoo**：失败用例和原因；
3. **DeepEval**：通过率；
4. **提示词质量**：Error / Warning 和命中位置；
5. **多轮基线**：均值、标准差、Flaky；
6. **供应链**：Trivy findings、SBOM；
7. **发现处理**：谁负责、是否复测、是否隔离。

### 7.3 状态怎么理解

| 状态 | 含义 |
|---|---|
| passed | 通过 |
| failed | 有失败，需要处理 |
| skipped | 未执行，通常是工具未安装或该 Skill 不适用 |
| timeout | 超时，提高超时或拆小用例 |

`skipped` 不等于 `passed`。报告中必须保留跳过原因。

### 7.4 修复循环

1. 判断是 Skill 问题、测试问题，还是环境问题；
2. 修改 Skill 或测试；
3. `python scripts/skill_lock.py generate`；
4. 如启用签名，重新签名；
5. 重跑同一级别；
6. 对比修复前后的报告。

不要为了让测试通过而放宽断言。先判断是实现问题还是测试问题。

### 7.5 退出码

| 退出码 | 含义 |
|---|---|
| 0 | 必需步骤通过 |
| 1 | 有失败 / 超时 |
| 2 | 参数或 Skill 路径错误 |

只想先出报告：

```bash
python scripts/manual_check.py --skill my-skill --level L1 --allow-failures
```

---

## 第 8 步：隔离已知不稳定用例（可选）

如果某个用例确认是模型波动，而且暂时无法修复，可以隔离，但必须有 Owner 和到期时间。

配置文件：`evals/quarantine.json`。

```json
{
  "version": 1,
  "skills": {
    "my-skill": [
      {
        "case": "完全匹配的 user_input",
        "reason": "已知模型波动，暂不阻断",
        "owner": "team-name",
        "expires": "2026-12-31"
      }
    ]
  }
}
```

规则：

- 按 `user_input` 精确匹配；
- `expires` 到期后自动失效；
- 被隔离用例不降低 Promptfoo 通过率，但报告会单列；
- Flaky 检测会跳过已隔离用例；
- 隔离不是修复，到期前必须修复或重新评审。

---

## 第 9 步：建立 3 轮基线并设置 Delta Gate

### 9.1 连续跑 3 轮

```bash
python scripts/manual_check.py --skill my-skill --level L2
python scripts/manual_check.py --skill my-skill --level L2
python scripts/manual_check.py --skill my-skill --level L2
```

长输出 Skill 加上同样的 `--max-tokens`。

### 9.2 采集基线

```bash
python scripts/baseline.py collect my-skill --runs 3
```

它会记录：

- 每轮指标；
- 均值、标准差、最小值、最大值；
- 用例级结果；
- Flaky 用例。

### 9.3 看趋势

```bash
python scripts/baseline.py trend my-skill
```

### 9.4 和当前结果比较

```bash
python scripts/baseline.py diff my-skill --tolerance 0.05
```

### 9.5 跑 Delta Gate

```bash
python scripts/baseline.py gate my-skill --tolerance 0.05
```

机器可读输出：

```bash
python scripts/baseline.py gate my-skill --json
```

Gate 规则：

- 基线至少 3 轮；
- 当前通过率不能低于基线均值超过容差；
- 没有 DeepEval 的 Skill 会跳过该项，不误判为失败。

### 9.6 校准本地 Judge（可选，但推荐）

```bash
JUDGE_MODEL=qwen3 JUDGE_API_BASE=http://localhost:8086/v1 \
  python scripts/judge_calibration.py
```

- 校准集：`evals/judge_calibration/relevancy.jsonl`
- 报告：`reports/judge_calibration/`
- 目标：一致率 ≥ 80%

当前校准集主要测 relevance。它不能替代 correctness / faithfulness 判断。

---

## 第 10 步：发布前复核

S2/S3 发布前：

1. 跑 L3；
2. 确认 Critical 为 0；
3. 看 Delta Gate 是否 PASS；
4. 人工复核失败、隔离、Flaky 用例；
5. 签名并归档报告；
6. Owner 按团队流程签核。

签名示例：

```bash
python scripts/sign_skills.py sign --key /secure/skills.pem
python scripts/sign_skills.py verify --public evals/keys/public.pem
```

私钥不要放进仓库。

---

## 三条最短路径

### 纯提示词 Skill

```bash
python ci/validate_skill.py --skill my-skill
python scripts/skill_lock.py generate
python scripts/manual_check.py --skill my-skill --level L0
python scripts/manual_check.py --skill my-skill --level L1
python scripts/manual_check.py --skill my-skill --level L2
python scripts/baseline.py collect my-skill --runs 3
python scripts/baseline.py gate my-skill
```

### 脚本型 Skill

```bash
python ci/validate_skill.py --skill my-skill
python scripts/skill_lock.py generate
python scripts/manual_check.py --skill my-skill --level L0
python scripts/manual_check.py --skill my-skill --level L1
pytest -q ci/test_<my-skill>_contract.py
python scripts/baseline.py collect my-skill --runs 3
python scripts/baseline.py gate my-skill
```

### 工具型 Agent Skill

```bash
./scripts/setup_harness_env.sh
python ci/validate_skill.py --skill my-skill
python scripts/skill_lock.py generate
python scripts/manual_check.py --skill my-skill --level L2 --agent
python scripts/baseline.py collect my-skill --runs 3
python scripts/baseline.py gate my-skill
```

---

## 常见问题

| 现象 | 先做什么 |
|---|---|
| `Connection refused` | 启动本地模型网关，检查 `localhost:8086` |
| `skill-lock` 失败 | 执行 `python scripts/skill_lock.py generate` |
| `skill-signature` 跳过 | 未配置公钥和签名，确认是否预期 |
| `security` 跳过 | Docker 未安装或未启动，报告中会写明 |
| Promptfoo 超时 | 提高 `--skill-timeout`，降低并发，或拆小用例 |
| DeepEval 超时 | 提高 `--deepeval-timeout`，改用短样本 |
| 长文生成超时 | 加 `--max-tokens 1024` |
| Garak 很慢 | 只跑 `Dan_11_0`；`promptinject` 放独立环境/分批 |
| 脚本型 Skill 没有 DeepEval/Garak | 预期行为，用 Promptfoo + 契约测试 |
| 不知道怎么写配置 | 复制现有 `evals/promptfooconfig.*.yaml`，改 `skillPath` 和用例 |
| Gate 说基线不足 | 先 `collect --runs 3`，单轮基线不能做 Gate |

---

## 不要做的事

- 不要把真实 PII、密钥、生产凭证放进测试数据。
- 不要提交私钥。
- 不要把 `skipped` 当成 `passed`。
- 不要在没有基线和 Delta Gate 的情况下直接开启 PR 阻断。
- 不要为了通过测试而放宽断言，先判断是实现问题还是测试问题。
- 不要修改 Skill 后不更新完整性锁。

---

## 当前限制

- CI 仍不启用；当前只做人工检查和告警。
- Agent 阶段 4 已完成：Gate、录制、回放；harness pin 为 `c4cf29f`。
- Garak `promptinject` 受本地模型速度限制，建议独立环境、分批执行。
- 模型网关尚未按 Skill 分配独立凭证/配额。
- 签名私钥托管与轮换流程待定。
- 本地 Judge 当前以 relevance 校准为主，正确性仍需人工复核。
