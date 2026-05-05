# ADR-002: P2 平台化增强采用 Gateway First + 统一观测基线

## 状态

已采纳，落地于 P2 阶段。

## 背景

根据 `backend-upgrade-master-plan-2026-04.md`，P2-3 需要补齐三项平台化能力：

1. API Gateway 统一入口
2. 告警与运行手册（Prometheus / Grafana / Alertmanager）
3. ADR、故障排查、性能调优文档体系

当前仓库在 P2 之前已有以下基础：

1. `control-plane-spring` 已开放 `/actuator/prometheus`
2. `docker-compose.yml` 已能启动 MySQL / Redis / Control Plane / Java Agent / Python Agent
3. Python Agent 已在 P2-1 / P2-2 完成缓存、插件与终态 observability 基础能力

缺口主要在于：

1. 缺少统一入口层，未来做鉴权、限流、超时、灰度会分散在多个服务
2. 缺少开箱即用的监控栈配置，运行时观测只能靠人工临时查看
3. 缺少值班视角的运行文档，故障响应和性能治理不可复制

## 决策

P2 采用“最小可运行平台化”策略，而不是一次性引入完整 APISIX / Kong / Istio：

1. 使用 `nginx` 作为 P2 的统一 Gateway 骨架，承担反向代理、转发头补齐、基础健康检查
2. 使用 `Prometheus + Alertmanager + Grafana` 形成最小观测闭环
3. 通过 `docker-compose` 的 `platform` profile 交付可启动的本地平台环境
4. 文档体系采用 ADR + Runbook + Troubleshooting + Tuning 四件套

## 为什么这样做

1. 成本可控
P2 的目标是“平台化增强”，不是“云原生网关重构”。Nginx 足以承接统一入口和后续迁移锚点。

2. 与现有架构耦合最小
不要求 Control Plane 和 Agent 立刻重构协议，即可先把入口、指标、告警接起来。

3. 方便后续 P3 演进
后续如果需要更强的认证、限流、WebSocket、多租户隔离，可平滑迁移到 APISIX / Kong / Envoy。

## 范围

本 ADR 覆盖：

1. `ops/gateway/nginx.conf`
2. `ops/observability/*`
3. `docker-compose.yml` 的 `platform` profile
4. P2 文档体系

本 ADR 不覆盖：

1. API 管理平台
2. 细粒度流量治理
3. 分布式 tracing 后端（Tempo / Jaeger）
4. 生产级告警通知集成（钉钉 / 企业微信 / PagerDuty）

## 结果

P2 完成后，项目具备以下最小平台能力：

1. 统一入口：`http://localhost:8080`
2. 指标采集：`Prometheus -> Control Plane actuator/prometheus`
3. 告警规则：服务存活、5xx 比率、P95 延迟、堆内存压力
4. 可视化：Grafana 预置仪表盘
5. 值班文档：运行、排障、性能调优均有落地说明

## 后续演进建议

1. Gateway 增加鉴权透传、限流、静态资源托管与 WebSocket 专项配置
2. Control Plane 补充业务指标，如任务派发、重试、租约恢复、事件投递耗时
3. 告警通知接入企业 IM / On-call 平台
4. 增加压测脚本与容量基线
