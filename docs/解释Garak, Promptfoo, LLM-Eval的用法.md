在上一节提到的 Agent Skill 提示词与安全治理层中，**Garak**、**Promptfoo** 和 **LLM-Eval** 是业界最常用的三大核心工具。它们分工明确，分别对应**大模型漏洞扫描（红队测试）**、**提示词回归测试（CI/CD 单元测试）**以及**多维度语义评估（LLM-as-a-Judge）**。

以下是这三个工具的核心定位与具体用法解析：

---

### 一、 Garak (LLM Vulnerability Scanner)

* **定位**：“大模型世界的 Nmap / 漏洞扫描器”。它专注于安全红队测试（Red Teaming）和漏洞探测。
* **核心作用**：自动化测试模型或 Skill 是否容易受到提示词注入、越狱（Jailbreak）、数据泄露、毒化（Data Poisoning）等安全攻击。

#### 1. 工作原理

Garak 内置了上百种攻击模块（Probes），主动向目标大模型发送各种恶意构造的 Prompt，然后通过检测模块（Detectors）分析模型的回复，判断防御是否被攻破。

#### 2. 基本用法

通常通过命令行或 Python API 直接对你的 Agent 接口（或大模型网关）发起扫描：

* **安装**：
```bash
pip install garak

```


* **运行全量/指定扫描**：
```bash
# 针对特定模型或 API 接口运行所有扫描模块
python -m garak --model_type rest --model_name http://localhost:8000/v1/chat/completions --probes promptinject,jailbreak

```


* **查看报告**：扫描结束后，Garak 会在本地生成详细的 HTML/JSON 报告，列出哪些漏洞被触发、成功率是多少，方便你修补 Skill 提示词中的边界防御漏洞。

---

### 二、 Promptfoo (LLM CI/CD Testing & Eval)

* **定位**：“大模型世界的 Jest / PyTest”。它专注于**提示词回归测试、功能断言（Assertions）和 CI/CD 流水线集成**。
* **核心作用**：验证 Skill 在面对特定输入时，输出是否符合业务预期，防止 Prompt 修改导致“负向回归”。

#### 1. 工作原理

通过编写声明式的 YAML/JSON 配置文件（`promptfoo.yaml`），定义一组测试用例（Test Cases）——包含输入（Input）、期望输出（Assertions，如包含某些关键词、结构必须是 JSON、不能包含敏感词等），然后在 CI 中自动化跑通。

#### 2. 基本用法

* **安装**：
```bash
npm install -g promptfoo
# 或者通过 npx 直接运行
npx promptfoo@latest init

```


* **配置文件示例 (`promptfoo.yaml`)**：
```yaml
prompts:
  - file: ./skills/my_skill/SKILL.md  # 指向你的 Skill 提示词文件
providers:
  - id: openai:gpt-4o  # 或指向你的企业内部网关模型
tests:
  - vars:
      user_input: "帮我查询张三的账户余额"
    assert:
      - type: contains
        value: "权限校验失败"
      - type: not-contains
        value: "余额"

```


* **运行测试**：
```bash
npx promptfoo eval
# 在 Web 界面中直观查看测试对比
npx promptfoo view

```



---

### 三、 LLM-Eval (LLM Evaluation Frameworks)

* **定位**：“大模型世界的质量打分与裁判系统”。通常指以 **LLM-as-a-Judge（大模型作为裁判）** 为核心理念的评估框架（如 Ragas、DeepEval、Promptfoo 内置的 LLM-Eval 机制等）。
* **核心作用**：针对 Agent Skill 的复杂输出，从准确性（Faithfulness）、相关性（Relevance）、格式对齐（Correctness）和幻觉率（Hallucination）等维度进行定量打分。

#### 1. 工作原理

由于 Agent Skill 的输出往往是自由文本或结构化指令，传统正则无法完全覆盖。LLM-Eval 会引入一个更强或专用的裁判模型（如 GPT-4），根据预设的评分标准（Rubric）和提示词模版，对被测 Skill 的输出给出 1-5 分的评分或通过/不通过判定。

#### 2. 经典工具选型（以 DeepEval 或 Ragas 为例）

* **安装**（以 DeepEval 为例）：
```bash
pip install deepeval

```


* **编写评测脚本 (`test_skill_eval.py`)**：
```python
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import HallucinationMetric, AnswerRelevanceMetric

def test_skill_output():
    # 定义测试用例：输入、Agent实际输出、检索上下文
    test_case = LLMTestCase(
        input="提取财报中的净利润数据",
        actual_output="该公司2025年净利润为 1.2 亿元人民币。",
        retrieval_context=["2025年财务报表显示，归属于母公司所有者的净利润为120,000,000元。"]
    )

    # 定义评估指标（幻觉度、相关性）
    hallucination_metric = HallucinationMetric(threshold=0.5)
    relevance_metric = AnswerRelevanceMetric(threshold=0.7)

    # 断言执行
    assert_test(test_case, [hallucination_metric, relevance_metric])

```


* **集成到 CI/CD**：直接在流水线中执行 `deepeval test run test_skill_eval.py`，只有当评分达到阈值时才允许合并代码和发布 Skill。

---

### 💡 三者在工程中的协同组合

在实际大模型研发规范中，这三者通常按阶段串联：

1. **日常开发阶段**：使用 **Promptfoo** 做本地单元测试和格式回归，确保 Prompt 改动不破坏原有逻辑。
2. **代码合入前（CI 流水线）**：引入 **LLM-Eval** 对关键业务场景进行幻觉与质量门禁校验。
3. **版本发布前（安全审计）**：运行 **Garak** 进行全方位的红队漏洞扫描，防御提示词注入和越狱风险。