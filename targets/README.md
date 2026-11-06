# targets 目标包

当前是迁移试点，只包含 3 个自包含目标包：

| 目标 | 类型 | 状态 |
|---|---|---|
| `write-report` | prompt | Promptfoo 3/3，DeepEval 1/1 |
| `md-to-word` | script | Promptfoo 5/5，adapter 可用 |
| `account-balance-query` | tool | Promptfoo 15/15，adapter 可用 |

## 目标包结构

```text
targets/<skill>/
├── SKILL.md
├── manifest.yaml
├── adapter.py
├── tools.yaml              # 工具型才有
├── evals/
│   ├── promptfoo.yaml
│   ├── test_deepeval.py    # 按需
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

目标包内部测试：

```bash
SKILL_API_BASE=http://localhost:8086/v1 SKILL_MODEL=qwen3 \
  npx promptfoo eval -c targets/write-report/evals/promptfoo.yaml --max-concurrency 1

RUN_LLM_EVALS=1 python -m pytest targets/account-balance-query/evals/test_agent.py -q
```

## 剩余迁移

`system-specification`、`manager-report`、`expense-policy-qa`、`service-ticket-update`、`cross-skill-router` 仍留在旧 `skills/` 布局，待这 3 个样板稳定后迁移。
