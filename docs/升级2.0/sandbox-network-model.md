# 沙箱网络模型

更新时间：2026-05-07
版本：v1.0
状态：现状文档（PR-7 产出）

---

## 1. 概述

沙箱（Sandbox）是 AutoCode 的代码执行隔离层。当前实现为 **单机 localhost 模型**：Java Agent 内嵌 HTTP 服务器，Python Agent 通过共享网络命名空间访问沙箱端口。

本文档明确当前网络拓扑、配置参数、已知限制，以及未来跨主机部署的触发条件。

---

## 2. 当前拓扑

```
┌─────────────────────────────────────────────────────────┐
│  Docker: network_mode: "service:pc-agent-java"          │
│                                                         │
│  ┌──────────────────┐    localhost:18080   ┌──────────┐ │
│  │  python-agent    │ ──── POST /execute ──→│ sandbox  │ │
│  │  (ExecTool)      │                      │ (Java)   │ │
│  └──────────────────┘                      └──────────┘ │
│         │                                      ▲        │
│         │ http://control-plane:8058            │        │
│         ▼                                      │        │
│  ┌──────────────────┐    ┌───────────────────┘        │
│  │  control-plane   │    │  pc-agent-java              │
│  │  (Spring Boot)   │    │  SandboxHttpServer :18080   │
│  └──────────────────┘    └────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                    ▲
                    │ :8058 / :8080
┌─────────────────────────────────────────────────────────┐
│  gateway (nginx)              外部访问入口              │
└─────────────────────────────────────────────────────────┘
```

**关键约束：**
- `python-agent` 容器使用 `network_mode: "service:pc-agent-java"`，共享 Java Agent 的网络命名空间
- 沙箱端口 18080 **不发布到宿主机**，仅容器内部可达
- 沙箱 HTTP 服务器硬编码拒绝非 `127.0.0.1` 的 Host 头

---

## 3. 组件职责

| 组件 | 端口 | 职责 |
|------|------|------|
| `pc-agent-java` SandboxHttpServer | 18080 | 接收执行请求，执行沙箱策略校验，运行命令 |
| `python-agent` ExecTool | — | 发起 HTTP POST 到 `127.0.0.1:18080/sandbox/execute` |
| `control-plane` | 8058 | 任务调度、事件接收、制品管理（不直连沙箱） |
| `gateway` (nginx) | 8080 | 外部入口，反向代理到 control-plane（无沙箱路由） |
| `gateway-service` (Spring Cloud Gateway) | — | 定义了 `/sandbox/**` 路由但当前未启用 |

---

## 4. 配置参数

### 4.1 Java Agent（沙箱服务端）

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `MVP_SANDBOX_SERVER_ENABLED` | `true` | 是否启动沙箱 HTTP 服务器 |
| `MVP_SANDBOX_PORT` | `18080` | 监听端口 |
| `MVP_SANDBOX_HOST` | `127.0.0.1` | 监听地址（仅允许 localhost） |
| `MVP_ALLOWED_WORKSPACE_PREFIXES` | `/workspace` | 允许的文件工作空间前缀 |

### 4.2 Python Agent（沙箱客户端）

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `MVP_SANDBOX_BASE_URL` | `http://127.0.0.1:18080` | 沙箱服务地址 |
| `MVP_SANDBOX_TIMEOUT_SECONDS` | `30` | 执行超时秒数 |

---

## 5. 沙箱 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/sandbox/health` | 健康检查 |
| GET | `/sandbox/tools` | 列出可用工具 |
| POST | `/sandbox/execute` | 执行命令（JSON body: `command`, `workdir`, `timeout`） |

---

## 6. 安全策略

`SandboxExecutionService` 实施复合策略链：

1. **提权检测** — 阻止 `sudo`、`su` 等提权命令
2. **环境变量访问** — 限制敏感环境变量暴露
3. **网络访问** — 控制出站网络请求
4. **文件读写** — 限制文件系统访问范围
5. **工作空间白名单** — 仅允许操作 `MVP_ALLOWED_WORKSPACE_PREFIXES` 下的路径

> **已知限制：** `SecurityPolicyValidator` 当前为桩实现（所有检查返回 `true`），策略校验依赖 `SandboxExecutionService` 的内联逻辑。

---

## 7. 跨主机部署触发条件

当前模型仅支持单机部署。以下条件任一满足时，需要演进为跨主机沙箱模型：

| 条件 | 说明 |
|------|------|
| Agent 与沙箱需部署在不同主机 | `network_mode: service:` 耦合无法跨主机 |
| 需要容器级隔离（非进程级） | 当前沙箱是进程内执行，无容器边界 |
| 需要多租户资源隔离 | 单进程沙箱无法限制 CPU/内存/磁盘 |
| 需要动态沙箱生命周期 | 当前沙箱与 Agent 同生命周期，无法按需创建/销毁 |

### 7.1 演进方向（仅供参考）

若触发跨主机需求，建议路径：

1. **阶段一：Docker-in-Docker 沙箱** — 沙箱执行改为创建临时容器，保持单机拓扑
2. **阶段二：远程沙箱池** — 沙箱容器独立调度，Agent 通过 gRPC/HTTP 远程调用
3. **阶段三：Kubernetes Job 沙箱** — 利用 K8s Job/CrdRequest 做弹性沙箱调度

---

## 8. 与网关的关系

- **nginx 网关** (`ops/gateway/nginx.conf`)：无沙箱路由，外部无法直接访问沙箱
- **Spring Cloud Gateway** (`gateway-service`)：定义了 `/sandbox/**` → `JAVA_SANDBOX_URL` 路由，带限流，但当前未启用
- 沙箱端口 18080 未发布到宿主机，外部网络不可达

---

## 9. 已知问题

1. `SecurityPolicyValidator` 为桩实现，安全校验不完整
2. `network_mode: service:` 耦合导致无法独立扩缩容 Agent 和沙箱
3. 沙箱执行超时由 Python 侧 HTTP 超时控制，Java 侧无独立超时机制
4. 无沙箱执行的审计日志（仅 Python 侧 observability span 记录）
