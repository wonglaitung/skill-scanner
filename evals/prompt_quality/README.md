# 提示词质量种子集

用于回归 `scripts/prompt_audit.py` 的已知缺陷样本：

| 目录 | 期望 |
|---|---|
| `clean` | 无 error |
| `pii_phone` | 命中 `pii.phone` |
| `private_key` | 命中 `secret.private_key` |
| `prompt_leak` | 命中 `prompt.leak_phrase` |
| `permission_conflict` | 命中 `permission.contradiction` |
| `internal_path` | 命中 `internal.path` 警告 |

这些样本只用于测试规则，不要放进 `skills/`。
