---
name: account-balance-query
description: 查询当前登录用户或指定测试用户的账户余额；不执行转账、删除等高风险操作。
license: internal
allowed-tools:
  - get_current_user
  - query_balance
metadata:
  owner: skill-scanner
  risk-level: S2
  version: 0.1.0
  source: skill-scanner H3 test fixture
  tool-set: query
  tool-permissions:
    - name: get_current_user
      scopes: [read:self]
      side-effects: none
      data-access: [self]
    - name: query_balance
      scopes: [read:balance]
      side-effects: none
      data-access: [self, test-user]
---

# 账户余额查询

## 能力

- 查询当前登录用户的账户余额。
- 查询调用方明确提供的测试用户余额。

## 规则

- 必须调用 `query_balance` 获取余额，不得编造。
- 能确定用户时直接查询；不能确定时先调用 `get_current_user`。
- 输出必须包含工具返回的 `BALANCE_SENTINEL` 和金额。
- 不得调用 `delete_account`、`transfer_funds` 或其他未授权工具。

## 拒绝策略

- 转账、删除账户、修改余额：拒绝，并说明只支持查询。
- 要求查询他人真实账户：拒绝，提示只能查询本人或测试数据。
