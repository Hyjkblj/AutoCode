# P2 故障排查指南

## 1. Gateway 无法访问

### 现象

1. `http://localhost:8080/healthz` 不通
2. `curl http://localhost:8080/actuator/health` 返回 502 / 504

### 排查步骤

1. 查看 `mvp-gateway` 是否在运行
2. 查看 `mvp-control-plane` 健康状态
3. 查看 `ops/gateway/nginx.conf` 是否加载成功

```powershell
docker ps
docker logs mvp-gateway --tail 100
docker logs mvp-control-plane --tail 100
```

### 常见原因

1. Control Plane 未启动完成
2. 网关 upstream 配置错误
3. 容器依赖关系未满足

## 2. Prometheus 无数据

### 现象

1. Grafana 面板全空
2. Prometheus 中 `up{job="control-plane"}` 为 0

### 排查步骤

1. 访问 `http://localhost:8058/actuator/prometheus`
2. 检查 `prometheus.yml` 抓取目标
3. 检查网络连通性

```powershell
docker logs mvp-prometheus --tail 100
curl http://localhost:8058/actuator/prometheus
```

### 常见原因

1. Control Plane 未暴露 actuator
2. Prometheus job 名称或地址写错
3. 应用启动但指标端点被依赖故障拖慢

## 3. Grafana 无法登录或看不到面板

### 排查步骤

1. 检查 `GF_SECURITY_ADMIN_USER` / `GF_SECURITY_ADMIN_PASSWORD`
2. 检查 provisioning 目录是否挂载成功
3. 检查 dashboard JSON 是否有效

```powershell
docker logs mvp-grafana --tail 100
```

## 4. Python Agent 任务失败

### 重点看什么

1. `TASK_FAILED` 终态原因
2. `observability.metrics`
3. `observability.spans`
4. 插件 breaker 状态

### 排查路径

1. 看是否是 `llm_key_missing`
2. 看是否是 `sandbox_request_failed`
3. 看是否是插件执行失败后 fallback
4. 看 `llm_cache_*` 指标判断是否反复命中坏缓存

## 5. 插件能力异常

### 现象

1. 插件未生效
2. 插件执行一次后持续被跳过

### 排查步骤

1. 检查插件 manifest 是否在 allowlist 中
2. 检查 entrypoint 是否在 `python-agent/plugins/` 且命名符合 `*_agent.py`
3. 检查 breaker 是否已 open

### 处理建议

1. 先修复插件异常
2. 观察 breaker 恢复窗口
3. 必要时回退到内建实现

## 6. 高延迟或 5xx 告警

### 先确认

1. 是否是数据库或 Redis 引起
2. 是否是 LLM 调用慢
3. 是否是 Java Sandbox 执行阻塞

### 快速动作

1. 降低灰度流量
2. 切回 `legacy`
3. 暂停高风险插件
4. 缩小任务并发
