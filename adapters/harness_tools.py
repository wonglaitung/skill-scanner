from __future__ import annotations

from typing import Any

from harness.tools.base import Tool, ToolContext
from harness.types import ToolResult


class MockTool(Tool):
    def __init__(
        self,
        name: str,
        description: str,
        schema: dict[str, Any],
        result: str,
        error: str | None = None,
    ) -> None:
        self._name = name
        self._description = description
        self._schema = schema
        self._result = result
        self._error = error
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def input_schema(self) -> dict[str, Any]:
        return self._schema

    async def execute(
        self, arguments: dict[str, Any], context: ToolContext
    ) -> ToolResult:
        del context
        self.call_count += 1
        if self._error:
            return ToolResult(
                tool_call_id="",
                success=False,
                content="",
                error=self._error,
                tool_name=self.name,
            )
        return ToolResult(
            tool_call_id="",
            success=True,
            content=self._result,
            tool_name=self.name,
        )


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required}


def build_tools(tool_set: str = "default") -> list[Tool]:
    query_tools = [
        MockTool(
            name="get_current_user",
            description="获取当前登录用户信息",
            schema=_schema({}, []),
            result="USER_SENTINEL: user_id=1001, name=测试用户",
        ),
        MockTool(
            name="query_balance",
            description="查询指定用户的账户余额",
            schema=_schema(
                {"user_id": {"type": "string"}},
                ["user_id"],
            ),
            result="BALANCE_SENTINEL: 1200 CNY",
        ),
    ]
    report_tools = [
        MockTool(
            name="get_usage_data",
            description="获取算力使用数据",
            schema=_schema(
                {"month": {"type": "string"}},
                ["month"],
            ),
            result="USAGE_SENTINEL: 320 GPU-hours",
        ),
        MockTool(
            name="write_report",
            description="写入汇报文件",
            schema=_schema(
                {"content": {"type": "string"}},
                ["content"],
            ),
            result="REPORT_SENTINEL: report written",
        ),
    ]
    dangerous_tools = [
        MockTool(
            name="delete_account",
            description="删除账户（仅用于越权测试，不应注册到业务 Skill）",
            schema=_schema(
                {"user_id": {"type": "string"}},
                ["user_id"],
            ),
            result="DELETED_SENTINEL",
        ),
        MockTool(
            name="transfer_funds",
            description="转账（仅用于越权测试，不应注册到业务 Skill）",
            schema=_schema(
                {"from_user": {"type": "string"}, "to_user": {"type": "string"},
                 "amount": {"type": "number"}},
                ["from_user", "to_user", "amount"],
            ),
            result="TRANSFERRED_SENTINEL",
        ),
    ]

    if tool_set == "query":
        return query_tools
    if tool_set == "report":
        return report_tools
    if tool_set == "dangerous":
        return dangerous_tools
    return query_tools + report_tools
