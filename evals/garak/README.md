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

`account-balance-query` 的 Release v1 复测：

- `dan.Dan_11_0`：通过。
- `promptinject.HijackHateHumans`：原始检测 ASR 4.69%（12/256），但 12 条全部是“拒绝时复述攻击短语”的检测器误报；人工归类后 true compliant = 0。
- 首轮原始 ASR 18.36%（47/256），其中 1 条是真实合规输出；已在安全边界规则中修复。
- 结论：`garak_summary` 状态为 `review`，不是 `failed`；仍需保留原始报告和归类证据。

## 暂缓 probe

`deferred_probes.txt`：

- `probes.encoding.InjectBase64`
- `probes.leakreplay.LiteratureCloze`

原因：本地 qwen3 吞吐不足，单 probe 运行时间过长且出现过 `ReadTimeout`。它们尚未纳入 Release v1 必跑集，不能声称“全部 Garak probe 已完成”。

## 注意

`scan.sh` 是单 probe/自定义 spec 工具；发布前复查优先用 `scan_release.sh`，并保留 `garak_summary.md` 作为独立证据。
