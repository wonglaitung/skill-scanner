# targets 目标包

所有 8 个 Skill 已迁移为自包含目标包。

| 目标 | 类型 |
|---|---|
| `write-report` | prompt |
| `system-specification` | prompt |
| `manager-report` | prompt |
| `expense-policy-qa` | prompt |
| `md-to-word` | script |
| `account-balance-query` | tool |
| `service-ticket-update` | tool |
| `cross-skill-router` | tool |

## 目标包结构

```text
targets/<skill>/
├── SKILL.md
├── manifest.yaml
├── adapter.py
├── tools.yaml              # 工具型才有
├── evals/
│   ├── promptfoo.yaml
│   ├── test_*.py           # 按需
│   └── baseline.json
└── fixtures/
```

`manifest.yaml` 是扫描器唯一事实源。扫描器不 import 目标代码。

## 运行

```bash
python scripts/preflight.py --targets targets --skill write-report --risk S2 --level L2
python scripts/preflight.py --targets targets --skill md-to-word --risk S2 --level L1
python scripts/preflight.py --targets targets --skill account-balance-query --risk S2 --level L2 --agent
```

扫描器执行：

```bash
python scripts/manual_check.py --targets targets --skill write-report --level L2
python scripts/manual_check.py --targets targets --skill account-balance-query --level L2 --agent
```

批量运行：

```bash
python scripts/scan_all.py --targets targets
python scripts/scan_all.py --targets targets --mode check
```

发布前 L3：

```bash
TARGETS=targets SKILL=account-balance-query ./evals/garak/scan_release.sh
```

目标包内部测试：

```bash
SKILL_API_BASE=http://localhost:8086/v1 SKILL_MODEL=qwen3 \
  npx promptfoo eval -c targets/write-report/evals/promptfoo.yaml --max-concurrency 1

RUN_LLM_EVALS=1 python -m pytest targets/account-balance-query/evals/test_account_balance.py -q
```

## Target L3（Release v2）

7 个 LLM 目标已完成，true compliant 全为 0。

| 目标 | true compliant |
|---|---:|
| write-report | 0 |
| system-specification | 0 |
| manager-report | 0 |
| expense-policy-qa | 0 |
| account-balance-query | 0 |
| service-ticket-update | 0 |
| cross-skill-router | 0 |
| md-to-word | 跳过（无 LLM 端点） |

## 当前结果

| 目标 | Promptfoo | 测试 |
|---|---|---|
| write-report | 3/3 | DeepEval 1/1 |
| system-specification | 8/8 | DeepEval 1/1 |
| manager-report | 8/8 | DeepEval 1/1 |
| expense-policy-qa | 6/6 | DeepEval 1/1 |
| md-to-word | 5/5 | adapter 可用 |
| account-balance-query | 15/15 | 工具测试 1/1 |
| service-ticket-update | 10/10 | 工具测试 1/1 |
| cross-skill-router | 9/9 | 工具测试 1/1 |
