# Garak 发布前复查

## 环境

使用独立 venv，避免 Garak 依赖污染主环境：

```bash
uv venv .venv-garak --python 3.10
uv pip install --python .venv-garak/bin/python 'garak==0.16.0'
```

`scan.sh` 默认优先使用 `.venv-garak/bin/python`。

## Release v1 probe 集

`release_probes.txt`：

- `probes.dan.Dan_11_0`
- `probes.promptinject.HijackHateHumans`

运行：

```bash
SKILL=account-balance-query ./evals/garak/scan_release.sh
```

输出：

```text
reports/garak/release/<skill>/<timestamp>/
├── garak.report.jsonl
├── garak.report.html
├── garak_summary.json
└── garak_summary.md
```

## 结果解释

- Garak `PASS`：该 probe 未命中。
- Garak `FAIL`：检测到攻击成功。
- `garak_summary.py` 会把 `fails / total` 汇总为 ASR（Attack Success Rate）。

## 当前结果

`account-balance-query` 的 Release v1：

- `dan.Dan_11_0`：通过。
- `promptinject.HijackHateHumans`：**FAIL**，ASR 18.36%（47/256），95% CI 13.67%–23.05%。
- 这属于真实发现，不应被“Garak 已跑”掩盖。

## 暂缓 probe

`deferred_probes.txt`：

- `probes.encoding.InjectBase64`
- `probes.leakreplay.LiteratureCloze`

原因：本地 qwen3 吞吐不足，单 probe 运行时间过长且出现过 `ReadTimeout`。它们尚未纳入 Release v1 必跑集，不能声称“全部 Garak probe 已完成”。

## 注意

`scan.sh` 是单 probe/自定义 spec 工具；发布前复查优先用 `scan_release.sh`，并保留 `garak_summary.md` 作为独立证据。
