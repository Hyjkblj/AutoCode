# P2 平台化运行手册

## 目标

本手册用于启动 P2 平台化最小闭环，包括：

1. Gateway
2. Control Plane
3. Java Sandbox Agent
4. Python Agent
5. Prometheus
6. Alertmanager
7. Grafana

## 目录映射

1. Gateway 配置：`ops/gateway/nginx.conf`
2. Prometheus 配置：`ops/observability/prometheus.yml`
3. 告警规则：`ops/observability/alert_rules.yml`
4. Alertmanager 配置：`ops/observability/alertmanager.yml`
5. Grafana 仪表盘：`ops/observability/grafana/dashboards/autocode-platform.json`

## 启动前准备

1. 确认 Docker / Docker Compose 可用
2. 确认 `.env` 中至少设置以下变量：
   `MYSQL_ROOT_PASSWORD`
   `MVP_DB_PASSWORD`
   `MVP_REDIS_PASSWORD`
   `MVP_JWT_SECRET`
3. 若需真实 LLM 联调，补充：
   `OPENAI_API_KEY` 或相应配置文件

## 启动步骤

启动基础业务与平台层：

```powershell
docker compose --profile fullstack --profile platform up -d
```

只启动平台扩展层（依赖基础服务已起）：

```powershell
docker compose --profile platform up -d
```

## 访问地址

1. Gateway: `http://localhost:8080`
2. Control Plane: `http://localhost:8058`
3. Control Plane Health: `http://localhost:8058/actuator/health`
4. Control Plane Prometheus: `http://localhost:8058/actuator/prometheus`
5. Prometheus: `http://localhost:9090`
6. Alertmanager: `http://localhost:9093`
7. Grafana: `http://localhost:3000`

## 验收检查

### 1. Gateway

```powershell
curl http://localhost:8080/healthz
curl http://localhost:8080/actuator/health
```

预期：

1. `/healthz` 返回 `ok`
2. `/actuator/health` 能经由网关代理到 Control Plane

### 2. Prometheus 抓取

在 Prometheus UI 检查：

1. `up{job="control-plane"}`
2. `http_server_requests_seconds_count`
3. `jvm_memory_used_bytes`

### 3. Grafana 仪表盘

登录 Grafana 后确认 `AutoCode Platform Overview` 已自动加载。

## 常见运维动作

### 重载 Prometheus 配置

```powershell
curl -X POST http://localhost:9090/-/reload
```

### 查看某个容器日志

```powershell
docker logs mvp-control-plane --tail 200
docker logs mvp-python-agent --tail 200
docker logs mvp-gateway --tail 200
```

### 停止平台环境

```powershell
docker compose --profile fullstack --profile platform down
```

## 告警处理原则

1. 先判断是入口故障、Control Plane 故障还是依赖故障
2. 先恢复可用性，再做根因分析
3. 若 P95 持续恶化或 5xx 升高，优先回退到 `legacy` 执行路径

## P2 回退建议

如果出现以下情况，优先关闭增量能力并回退：

1. LangGraph 灰度后成功率下降超过 1%
2. P95 上升超过 20%
3. 事件重复执行率异常
4. 插件导致稳定性下降

回退手段：

1. `AGENT_ENGINE=legacy`
2. 暂时不启用 `platform` profile
3. 关闭对应插件或恢复 allowlist 到最小集
