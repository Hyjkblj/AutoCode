dia# 移动端 PR 规划（2026-04-09）

本文档从架构分析文档中抽离，仅保留移动端 PR 执行计划，便于独立跟踪与推进。

## 目标

在现有可用基础上，补齐移动端产品化闭环：真实发布、项目同步、可观测 UI、质量门禁、通知与离线能力。

## 范围说明

- 主要代码范围：`mobile-app/**`
- 协同范围（按需）：`control-plane-spring/**`
- 责任主体：Agent-4（移动端），Agent-1（控制面接口配合）

## Phase A（P0，本周）

### 1) `feat/a4-mob-real-publish-flow`

- 责任：Agent-4，Agent-1 配合控制面接口
- 范围：`mobile-app/**`（必要时 `control-plane-spring/**`）
- 内容：
  - 将发布入口从 `recordPublishEntry()` 本地 mock 记录改为真实 API 调用。
  - 发布历史优先读取服务端，失败回落本地缓存。
- 验收：
  - 移动端可以发起真实发布流程。
  - 收到 deploy 事件后，发布历史自动更新。

### 2) `feat/a4-mob-projects-api-sync-v2`

- 责任：Agent-4，依赖 Agent-1 项目列表 API
- 范围：`mobile-app/**`
- 内容：
  - 对接 `/api/v1/projects`（或统一项目列表接口）。
  - 任务派生项目逻辑下沉为 fallback。
- 验收：
  - 登录后项目列表来自服务端。
  - 离线时可使用 fallback 降级展示。

## Phase B（P1，1-2 周）

### 3) `feat/a4-mob-review-fixloop-cards`

- 责任：Agent-4
- 范围：`mobile-app/**`
- 内容：
  - 新增结构化事件卡片：`riskLevel/issues/errorCode/fixLoopAttempt/maxAttempts`。
  - 任务详情页增加“修复进度时间线”。
- 验收：
  - 失败原因、重试次数、修复进度在移动端可快速定位。

### 4) `test/a4-mob-critical-ui-regression`

- 责任：Agent-4
- 范围：`mobile-app/**`
- 内容：
  - 补齐关键 UI 自动化：语音输入、审批弹层、事件流展示、产物预览。
- 验收：
  - `androidTest` 稳定通过并覆盖核心路径。

## Phase C（P2，2-4 周）

### 5) `feat/a4-mob-push-notification`

- 责任：Agent-4，Agent-1 配合通知触发
- 范围：`mobile-app/**`（必要时 `control-plane-spring/**`）
- 内容：
  - 增加任务完成/失败、审批待处理推送通知。
- 验收：
  - App 在后台或锁屏状态可收到关键任务通知。

### 6) `feat/a4-mob-offline-room-event-cache`

- 责任：Agent-4
- 范围：`mobile-app/**`
- 内容：
  - 引入 Room，支持任务事件缓存、离线浏览、重连补偿。
- 验收：
  - 弱网/离线状态可查看最近任务和事件，恢复后自动对齐服务端。

## 建议合并顺序

1. `feat/a4-mob-real-publish-flow`
2. `feat/a4-mob-projects-api-sync-v2`
3. `feat/a4-mob-review-fixloop-cards`
4. `test/a4-mob-critical-ui-regression`
5. `feat/a4-mob-push-notification`
6. `feat/a4-mob-offline-room-event-cache`

## 关联文档

- `docs/architecture-analysis-2026-04.md`（移动端复核与全局架构上下文）
