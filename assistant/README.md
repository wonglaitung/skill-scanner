# assistant

内部辅助 Skill，不属于 `targets/` 目标包，不参与目标检查。`skill-release-guide` 是唯一用户入口。

| Skill | 用途 |
|---|---|
| `skill-release-guide` | 从放置 Skill 到生成报告的用户旅程助手 |

使用方式：把 `assistant/skill-release-guide/` 加载到支持 Skill 的 Agent 环境，或让 Agent 直接读取
[`skill-release-guide/SKILL.md`](skill-release-guide/SKILL.md)。它负责完整流程；报告解读和排障见
[`docs/Skill 检查使用指南.md`](../docs/Skill%20检查使用指南.md)。

## 怎么触发

不需要自己拼命令。把 Skill 来源、名称、Owner、风险等级、类型、检查深度告诉 Agent，例如：

```text
使用 skill-release-guide 检查 /data/skills/customer-reply。
名称 customer-reply，Owner cs-team，风险 S2，类型 prompt，检查 L2。
先初始化和单次检查；通过后再跑 3 轮基线，不跑 L3。
```

Agent 会先补问缺失信息，然后按 `init → check → run` 执行。S 等级和 Owner 必须由人给出，Agent 不能自行决定。

## 案例 1：新导入纯提示词 Skill

用户输入：

```text
使用 skill-release-guide 把 /data/skills/customer-reply 导入 targets。
名称 customer-reply，Owner cs-team，风险 S2，类型 prompt，检查 L2。
先跑一次检查，通过后跑 3 轮基线。
```

Agent 实际执行：

```bash
python scripts/release_assistant.py init \
  --source /data/skills/customer-reply \
  --name customer-reply \
  --owner cs-team \
  --risk S2 \
  --type prompt \
  --level L2 \
  --targets targets

python scripts/release_assistant.py check \
  --targets targets \
  --skill customer-reply

python scripts/release_assistant.py run \
  --targets targets \
  --skill customer-reply \
  --runs 3
```

真实检查时，`init` 只生成骨架。Agent 会指出还缺哪些 Promptfoo、DeepEval 或 fixtures；
业务用例必须由用户确认，不能由 Agent 编造。单次 `check` 有 FAIL 时不会直接进入 3 轮。

结果在：

```text
reports/customer-reply/release-<timestamp>/summary.md
reports/customer-reply/release-<timestamp>/summary.json
```

## 案例 2：工具型 Skill，L2 + Agent

工具型 Skill 会真实调用工具，必须用 Agent 模式检查越权、参数注入和数据外泄。

用户输入：

```text
检查 targets/service-ticket-update，风险 S2，类型 tool，L2 + Agent。
这是写操作，发布前还要跑 L3。
```

Agent 实际执行：

```bash
python scripts/release_assistant.py check \
  --targets targets \
  --skill service-ticket-update

python scripts/release_assistant.py run \
  --targets targets \
  --skill service-ticket-update \
  --runs 3 --l3
```

如果目标包还不存在，先初始化并带 `--agent`：

```bash
python scripts/release_assistant.py init \
  --source /path/to/service-ticket-update \
  --name service-ticket-update \
  --owner owner-team \
  --risk S2 \
  --type tool \
  --level L2 --agent \
  --targets targets
```

Agent 会检查 `tools.yaml`、权限声明、工具调用轨迹、未授权工具、参数注入和外泄用例。
L3 结果放在 `reports/garak/release/service-ticket-update/<timestamp>/`。

## 案例 3：已有目标包复检

不改目标包，只重新跑检查和基线：

```text
复检 targets/write-report，L2，跑 3 轮，不跑 L3。
先告诉我上次失败项，再开始。
```

Agent 实际执行：

```bash
python scripts/release_assistant.py check \
  --targets targets \
  --skill write-report

python scripts/release_assistant.py run \
  --targets targets \
  --skill write-report \
  --runs 3
```

重点看 `summary.md` 中的 preflight、manual_check、3 轮 Flaky、baseline Gate 和未通过项。
`skipped` 不能当 `passed`。

## 使用边界

- 用户必须提供 S 等级和 Owner；Agent 只解释和检查，不代替定级。
- Agent 不编造业务测试用例，不把 skipped 当通过，不代替 Owner 或安全团队签核。
- 检查使用合成数据，禁止真实 PII、密钥、生产凭证。
- 本地模型网关默认 `http://localhost:8086/v1`，模型 `qwen3`。
- 目标包统一放 `targets/`，不要放回 `skills/`。
