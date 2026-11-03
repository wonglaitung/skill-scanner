# 如何扫描一个 Agent Skill（用户操作指南）

适用读者：Skill 作者、Skill Owner、安全审核人。

目标：从一个 Skill 目录开始，生成一份可复核的检查报告，并决定是否修复、复测或发布。

---

## 你只需要记住 6 步

```text
1. 准备环境
2. 把 Skill 放进项目
3. 补齐元数据与评测配置
4. 选择级别并运行
5. 看报告、处理问题
6. 保存基线，发布前复核
```

第一次使用建议先跑 L0，确认环境和结构没问题，再逐级到 L1、L2、L3。

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

需要：

- Python 3.10+
- Node.js 20+
- Docker（用于供应链扫描和沙箱）

### 1.3 确认本地模型网关

```bash
curl http://localhost:8086/v1/models
```

返回模型列表即可。默认模型是 `qwen3`。

如果连接失败：

- 确认本地模型服务已启动
- 确认端口是 8086
- 不要改成外部模型 API

### 1.4 确认 Docker

```bash
docker ps
```

Docker 不可用时，`security` 和沙箱步骤会跳过，报告中会记录原因。

---

## 第 2 步：把 Skill 放进项目

### 2.1 目录结构

```text
skills/<skill-name>/
├── SKILL.md
├── scripts/          # 可选
└── references/       # 可选
```

如果 Skill 已经在 `skills/` 下，跳过复制。

```bash
cp -r /path/to/my-skill skills/my-skill
```

### 2.2 检查 SKILL.md

`SKILL.md` 必须包含 Frontmatter：

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

字段说明：

| 字段 | 说明 |
|---|---|
| `name` | 只能小写字母、数字、连字符 |
| `description` | 说明能力和边界，不要只写“一个有用的 Skill” |
| `license` | 内部 Skill 写 `internal` |
| `allowed-tools` | 没有工具就写空列表 |
| `metadata.owner` | 负责团队 |
| `metadata.risk-level` | S0-S3 |
| `metadata.version` | 语义化版本 |

### 2.3 先做一次结构校验

```bash
python ci/validate_skill.py --skill my-skill
```

看到 `[OK]` 再继续。失败时按提示修正 Frontmatter、目录名或引用文件。

---

## 第 3 步：补齐元数据与评测配置

### 3.1 纯提示词 Skill

需要一个 Promptfoo 配置：

```text
evals/promptfooconfig.my-skill.yaml
```

最小示例：

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

不会写配置时：

- 复制 `evals/promptfooconfig.manager-report.yaml`
- 把 `skillPath` 改成你的 Skill
- 把测试问题换成你的业务场景

### 3.2 脚本型 Skill

需要：

- 一个 provider，把脚本的输入输出包装成 Promptfoo 可调用接口
- 一个对应的 `evals/promptfooconfig.<skill>.yaml`

可以参考 `md-to-word`：

- `adapters/md_to_word_provider.py`
- `evals/promptfooconfig.md-to-word.yaml`
- `ci/test_md_to_word_contract.py`

### 3.3 更新完整性锁

每次修改 Skill 文件后都必须执行：

```bash
python scripts/skill_lock.py generate
python scripts/skill_lock.py verify
```

否则扫描会在 `skill-lock` 步骤失败。

### 3.4 可选：签名

如果团队启用了签名：

```bash
python scripts/sign_skills.py sign --key /secure/skills.pem
python scripts/sign_skills.py verify --public evals/keys/public.pem
```

私钥不要放进仓库。

---

## 第 4 步：选择级别并运行

### 4.1 选择级别

| Skill 类型 / 风险 | 建议级别 |
|---|---|
| S0/S1 纯提示词 | L0 → L1 |
| S2 纯提示词 | L0 → L1 → L2，发布前 L3 |
| S3 或第三方 Skill | L0 → L1 → L2 → L3 |
| 确定性脚本 Skill | L0 → L1；L2/L3 会跳过 |
| 工具调用 / 多步 Agent | L0 → L1 → L2，L1/L2 加 `--agent`；H3 C4 |

### 4.2 一条命令运行

```bash
python scripts/manual_check.py --skill my-skill --level L0
```

工具型 Skill：

```bash
python scripts/manual_check.py --skill account-balance-query --level L2 --agent
```

逐级运行：

```bash
python scripts/manual_check.py --skill my-skill --level L1
python scripts/manual_check.py --skill my-skill --level L2
python scripts/manual_check.py --skill my-skill --level L3
```

常用参数：

| 参数 | 什么时候用 |
|---|---|
| `--model qwen3` | 换模型，一般不用改 |
| `--api-base ...` | 网关不是默认地址时 |
| `--skill-timeout 300` | Promptfoo 经常超时 |
| `--deepeval-timeout 600` | DeepEval 长文本超时 |
| `--full-garak` | 需要尝试完整 `promptinject` |
| `--allow-failures` | 只想先出报告，不因失败中断 |

### 4.3 每一级会做什么

| 级别 | 做什么 |
|---|---|
| L0 | 结构、完整性锁、签名、Ruff、Semgrep、gitleaks、npm audit、Trivy、SBOM、ShellCheck |
| L1 | L0 + Promptfoo 确定性回归 |
| L2 | L1 + DeepEval 指标评分 |
| L3 | L2 + Garak 扫描 Skill 端点 |

说明：

- 脚本型 Skill 在 L2/L3 会跳过 DeepEval/Garak，这是预期行为。
- 没有 Docker 时，`security` 会跳过。
- 没有配置签名时，`skill-signature` 会跳过。

---

## 第 5 步：看报告、处理问题

### 5.1 报告位置

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

先看 `report.md`，需要机器可读结果时看 `summary.json`。

### 5.2 怎么读

`report.md` 里重点看：

1. **步骤结果表**：哪些 passed / failed / skipped / timeout
2. **Promptfoo**：哪些用例失败，失败原因是什么
3. **DeepEval**：通过率
4. **供应链**：Trivy findings、SBOM components
5. **证据**：原始报告路径

状态含义：

| 状态 | 含义 |
|---|---|
| passed | 通过 |
| failed | 有失败，需要处理 |
| skipped | 未执行，通常是工具未安装或该 Skill 不适用 |
| timeout | 超时，需要提高超时或拆小用例 |

### 5.3 处理问题

1. 打开失败用例，判断是测试问题还是 Skill 问题。
2. Critical/High 建工单。
3. 修改 Skill。
4. 重新生成完整性锁。
5. 重新签名（如启用）。
6. 重跑同一级别。

### 5.4 命令退出码

- `0`：必需步骤通过
- `1`：有失败/超时
- `2`：参数或 Skill 路径错误

如果只想生成报告：

```bash
python scripts/manual_check.py --skill my-skill --level L1 --allow-failures
```

---

## 第 6 步：保存基线，发布前复核

### 6.1 保存基线

首次通过后：

```bash
python scripts/baseline.py save my-skill
```

后续对比：

```bash
python scripts/baseline.py diff my-skill
```

如果希望回退时返回非零：

```bash
python scripts/baseline.py diff my-skill --fail-on-regression
```

### 6.2 发布前

S2/S3 发布前：

1. 跑 L3。
2. 确认 Critical 为 0。
3. 人工复核报告。
4. 签名并归档报告。
5. 按团队流程签核。

---

## 最短路径

```bash
python ci/validate_skill.py --skill my-skill
python scripts/manual_check.py --skill my-skill --level L1
python scripts/baseline.py save my-skill
```

通过后再进入 L2/L3。

---

## 常见问题

| 现象 | 处理 |
|---|---|
| `Connection refused` | 本地模型网关未启动，检查 `localhost:8086` |
| `skill-lock` 失败 | 执行 `python scripts/skill_lock.py generate` |
| `skill-signature` 跳过 | 未配置 `evals/keys/public.pem` 和 `evals/skills.lock.sig` |
| `security` 跳过 | Docker 未安装或未启动 |
| Promptfoo 超时 | 提高 `--skill-timeout`，降低并发，或拆小用例 |
| DeepEval 超时 | 提高 `--deepeval-timeout`，改用短样本 |
| Garak 很慢 | 只跑 `Dan_11_0`；`promptinject` 分批/独立环境 |
| 脚本型 Skill 没有 DeepEval/Garak | 预期行为，用 Promptfoo + 契约测试 |
| 不知道怎么写配置 | 复制现有 `evals/promptfooconfig.*.yaml`，改 `skillPath` 和用例 |

---

## 不要做的事

- 不要把真实 PII、密钥、生产凭证放进测试数据。
- 不要提交私钥。
- 不要把 `skipped` 当成 `passed`。
- 不要在没有基线的情况下直接开启 PR 阻断。
- 不要为了通过测试而放宽断言，先判断是实现问题还是测试问题。

---

## 当前限制

- H3 C4 本地验证通过：确定性 Gate、录制、回放；上游 harness 修复待提交。
- Garak `promptinject` 受本地模型速度限制。
- 模型网关尚未按 Skill 分配独立凭证/配额。
- 签名私钥托管与轮换流程待定。

---

## 11. 新增 Skill 时怎么复用 SOP

不需要重新设计流程，按同一套模板做：

1. 复制一个同类 Skill 的 `SKILL.md` 结构，改 `name`、`description`、`metadata`。
2. 复制 `evals/promptfooconfig.<old-skill>.yaml`，改 `skillPath` 和用例。
3. 脚本型 Skill 复用现有 provider 模式，补一个 `adapters/<skill>_provider.py`。
4. 执行 `python scripts/skill_lock.py generate`。
5. 需要签名时执行 `python scripts/sign_skills.py sign --key ...`。
6. 先跑 L0，再跑 L1；高风险 Skill 再跑 L2/L3。
7. 通过后 `python scripts/baseline.py save <skill-name>`。

新增 Skill 的边际成本主要是补元数据、评测配置和用例，不是重写流程。
