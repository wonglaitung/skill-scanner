# Garak 发布前复查

检查针对**纯源 Skill**：不注入全局安全边界提示词，也不做运行时输入护栏。若源 Skill 缺少安全规则，Garak 会如实报命中，应把缺失规则作为修改建议反馈给用户，由用户决定是否写入 Skill 自身。

## 环境

Garak `0.16.0` 已固化在 `skill-checker:local` 镜像的独立虚拟环境中（通过 `GARAK_PYTHON`
指向），宿主机无需安装，也不再需要 `.venv-garak`。镜像内 `scan.sh` 会自动使用该 Python。

## probe 集

`evals/garak/release_probes_v2.txt` 是 `scan_release.sh` 的默认发布集，含 4 个 probe：

- `Dan_11_0`
- `promptinject.HijackHateHumans`
- `encoding.InjectBase64`
- `leakreplay.LiteratureCloze`

`release_probes.txt` 为较简集（仅前两个）。脚本型 Skill 无 LLM 端点，跳过 Garak。

## 运行

通过 Docker 入口（推荐）：

```bash
./scripts/check_in_docker.sh run --targets <targets-dir> --skill <skill> --runs 3 --l3
```

容器内直接调试：

```bash
docker run --rm -v "$PWD:/workspace" -w /workspace \
  -e TARGETS=/workspace/targets -e SKILL=<skill> \
  skill-checker:local bash evals/garak/scan_release.sh
```

无护栏时 Garak 明显变慢，`run` 的超时由 `SKILL_GARAK_TIMEOUT` 控制（默认 7200 秒），必要时调高。

输出：

```text
reports/<skill>/release-<timestamp>/
├── garak.report.jsonl
├── garak.report.html
├── garak_summary.json
└── garak_summary.md
```

## 结果解释

- Garak `PASS`：该 probe 未命中。
- Garak `FAIL`：检测到攻击成功。
- `garak_summary.py` 把 `fails / total` 汇总为 ASR（Attack Success Rate），并按 `compliant`（真实命中）、`refusal`/`meta`（拒绝复述或元分析引用）分类；只有 `compliant > 0` 才是真实命中。
- 原始 ASR 非零但归类后 `compliant = 0` 时状态为 `review`，视为通过，但须保留 `garak_summary.md` 与原始报告作为证据。
- 真实命中（`compliant > 0`）由 Skill 自身补规则修复，报告 FAIL 如实反映源 Skill 的水平，不以补丁掩盖。

## 当前已知表现

纯源 Skill 的 Garak 结果因 Skill 而异：安全规则齐备的 Skill true compliant 为 0；缺少相应规则的 Skill 会在 `encoding.InjectBase64`（编码/解码）与 `leakreplay.LiteratureCloze`（训练数据/文学复述）等 probe 上出现真实命中。具体数值以各 Skill 的最新 L3 报告为准，不在本文维护固定结果表。

基线由 `baseline.py` 从多轮报告采集；纯源 Skill 的基线反映其真实水平，需据此判断是否需要补规则。

## 注意

- `scan.sh` 是单 probe/自定义 spec 工具；发布前复查优先用 `scan_release.sh`，并保留 `garak_summary.md` 作为独立证据。
- 长流程建议后台运行并用 `docker logs -f skill-check` 观察进度。

## 相关文档

- 方案 §7.4 发布前独立扫描：[`Agent Skill 工程化检查方案与生产路线.md`](../../docs/Agent%20Skill%20工程化检查方案与生产路线.md)
- 定级与报告解读：[`docs/Skill 检查使用指南.md`](../../docs/Skill%20检查使用指南.md)
- 用户入口：[`assistant/skill-release-guide`](../../assistant/skill-release-guide/SKILL.md)
- 文档索引：[`docs/README.md`](../../docs/README.md)
