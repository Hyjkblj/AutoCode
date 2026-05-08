# ADR-003: 事件处理逻辑边界提取为 EventIngressService

## 状态

已采纳，落地于 PR-10。

## 背景

控制面的 `TaskService` 承担了任务生命周期管理的全部职责，包括事件接收、去重、seq 分配、状态机驱动、持久化和 WS 广播。事件入口（`EventController`）直接调用 `TaskService.ingestAgentEvent()`，导致：

1. HTTP/ACK 协议层与业务逻辑层没有明确边界
2. 事件验证（`TaskEventValidator`）在 `TaskService` 内部调用，调用方无法控制验证时机
3. 审批上下文漂移的审计逻辑混在事件摄取流程中

## 决策

在 `service/protocol` 包中创建 `EventIngressService`，作为事件摄取的边界层：

- `EventIngressService` 负责事件验证和审计
- `TaskService.ingestAgentEvent()` 负责状态机和持久化
- `EventController` 通过 `EventIngressService` 而非直接调用 `TaskService`

## 为什么这样做

1. 职责分离
   HTTP/ACK 层（EventController）→ 验证边界（EventIngressService）→ 状态管理（TaskService）

2. 可测试性
   EventIngressService 可独立测试事件验证和审计逻辑，不需要 mock 整个 TaskService

3. 未来扩展
   如果需要添加新的事件预处理（如速率限制、事件转换），可以集中在 EventIngressService 中

## 后果

### 正面

- 事件摄取的入口和出口职责清晰
- TaskService 不再直接依赖 TaskEventValidator（由 EventIngressService 持有）
- 审批上下文漂移审计集中在 EventIngressService

### 负面

- 增加一层间接调用（EventController → EventIngressService → TaskService）
- 需要保持 EventIngressService 和 TaskService 之间的接口稳定

### 风险

- 如果未来 EventController 直接调用 TaskService 绕过 EventIngressService，边界会失效
  缓解：在代码审查中确保所有事件摄取经过 EventIngressService
