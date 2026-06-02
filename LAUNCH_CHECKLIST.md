# AutoCode 上线前准备工作

> 基于 2026-06-02 仓库状态编写
> 当前完成度：~55% | 目标：100% P0 项完成即可上线

---

## 阶段一：数据层加固（Week 1）

### 1.1 为 3 个服务添加 Flyway 迁移

**当前问题**：approval-service、artifact-service、event-service 使用 `ddl-auto: update`，生产环境 schema 变更不可控。

**操作步骤**：

1. 为每个服务添加 Flyway 依赖：
```xml
<!-- pom.xml -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-data-jpa</artifactId>
</dependency>
<dependency>
    <groupId>org.flywaydb</groupId>
    <artifactId>flyway-core</artifactId>
</dependency>
<dependency>
    <groupId>org.flywaydb</groupId>
    <artifactId>flyway-mysql</artifactId>
</dependency>
```

2. 修改 `application.yml`：
```yaml
spring:
  jpa:
    hibernate:
      ddl-auto: validate    # 改 update → validate
  flyway:
    enabled: true
    locations: classpath:db/migration
```

3. 从现有 JPA Entity 生成初始迁移脚本 `V1__init_schema.sql`
4. 验证：启动服务确认 Flyway 迁移成功 + `ddl-auto: validate` 不报错

**验收标准**：3 个服务全部使用 Flyway 管理 schema，`ddl-auto: update` 从配置中移除。

---

### 1.2 数据库备份策略

**操作步骤**：

1. 编写 MySQL 备份脚本：
```bash
#!/bin/bash
# scripts/backup-mysql.sh
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/mysql"
mkdir -p $BACKUP_DIR

mysqldump -h ${DB_HOST} -u ${DB_USER} -p${DB_PASS} \
  --single-transaction --routines --triggers \
  mvp_codeops | gzip > ${BACKUP_DIR}/mvp_codeops_${DATE}.sql.gz

# 保留最近 30 天
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
```

2. 配置 cron 定时任务（每天凌晨 3 点）
3. 验证备份可恢复

**验收标准**：每日自动备份，保留 30 天，有恢复演练记录。

---

## 阶段二：容器化与 CI/CD（Week 1-2）

### 2.1 补全缺失的 Dockerfile

**当前状态**：5/7 服务有 Dockerfile，event-service 和 artifact-service 缺失。

为 event-service 创建 `Dockerfile`：
```dockerfile
FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY target/event-service-*.jar app.jar
EXPOSE 8082
ENTRYPOINT ["java", "-jar", "app.jar"]
```

为 artifact-service 创建 `Dockerfile`（同理）。

**验收标准**：7 个服务全部可通过 `docker build` 构建镜像。

---

### 2.2 CI/CD 流水线升级

**当前状态**：仅有 build + test，无 Docker 构建、无安全扫描、无部署。

**目标流水线**：

```
┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐
│ Lint │───►│ Test │───►│Build │───►│Scan  │───►│Push  │
│      │    │      │    │Docker│    │SAST  │    │Image │
└──────┘    └──────┘    └──────┘    └──────┘    └──────┘
                                                      │
                              ┌────────────────────────┘
                              ▼
                        ┌──────────┐    ┌──────────┐
                        │ Deploy   │───►│ Smoke    │
                        │ Staging  │    │ Test     │
                        └──────────┘    └──────────┘
                                              │
                        ┌─────────────────────┘
                        ▼
                  ┌──────────┐    ┌──────────┐
                  │ Manual   │───►│ Deploy   │
                  │ Approve  │    │ Prod     │
                  └──────────┘    └──────────┘
```

**`.github/workflows/ci.yml` 需增加**：

```yaml
jobs:
  # 现有 test job 保留
  test:
    # ... 现有内容 ...

  build-and-push:
    needs: test
    if: github.ref == 'refs/heads/master'
    runs-on: ubuntu-latest
    strategy:
      matrix:
        service:
          - control-plane-spring
          - pc-agent-java
          - python-agent
          - approval-service
          - artifact-service
          - event-service
          - gateway-service
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker image
        run: docker build -t ghcr.io/${{ github.repository }}/${{ matrix.service }}:${{ github.sha }} ./${{ matrix.service }}
      - name: Push to GHCR
        run: |
          echo ${{ secrets.GITHUB_TOKEN }} | docker login ghcr.io -u ${{ github.actor }} --password-stdin
          docker push ghcr.io/${{ github.repository }}/${{ matrix.service }}:${{ github.sha }}

  deploy-staging:
    needs: build-and-push
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - name: Deploy to staging
        run: |
          # kubectl apply 或 helm upgrade
          echo "Deploying to staging..."

  deploy-prod:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: production    # 需要手动审批
    steps:
      - name: Deploy to production
        run: echo "Deploying to production..."
```

**验收标准**：每次 master 推送自动构建镜像 → 推送 GHCR → 部署 staging → 手动审批 → 部署 prod。

---

### 2.3 安全扫描集成

在 CI 中添加：

```yaml
  security-scan:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # 依赖漏洞扫描
      - name: Trivy vulnerability scan
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          severity: 'CRITICAL,HIGH'
      # SAST 扫描
      - name: CodeQL Analysis
        uses: github/codeql-action/analyze@v3
```

**验收标准**：CRITICAL/HIGH 漏洞阻断流水线。

---

## 阶段三：环境配置（Week 2）

### 3.1 创建多环境配置

**当前状态**：仅有 `application.yml`（默认）和 `application-local.yml`（本地开发）。

**需要创建**：

```
control-plane-spring/src/main/resources/
├── application.yml              # 公共配置
├── application-local.yml        # ✅ 已有 (H2, 内存队列)
├── application-staging.yml      # 🔴 新增
└── application-prod.yml         # 🔴 新增
```

**application-staging.yml**：
```yaml
spring:
  datasource:
    url: ${MVP_DB_URL}          # 无默认值，强制环境变量
    username: ${MVP_DB_USERNAME}
    password: ${MVP_DB_PASSWORD}
  data:
    redis:
      host: ${MVP_REDIS_HOST}
      password: ${MVP_REDIS_PASSWORD}

mvp:
  auth:
    jwt:
      secret: ${MVP_JWT_SECRET}  # 无默认值，P0 校验会拦截
  scheduler:
    mode: db
    lease-recover-interval-ms: 3000

logging:
  level:
    com.autocode: INFO
    org.springframework.web: WARN
```

**application-prod.yml**：
```yaml
spring:
  datasource:
    url: ${MVP_DB_URL}
    hikari:
      maximum-pool-size: 30
      minimum-idle: 10
      connection-timeout: 5000

mvp:
  auth:
    jwt:
      secret: ${MVP_JWT_SECRET}
  mtls:
    required-for-agent: true     # 生产环境强制 mTLS

logging:
  level:
    com.autocode: WARN
```

**验收标准**：所有服务有 staging/prod 配置，无硬编码默认密码。

---

### 3.2 Kubernetes 清单

**需要创建** `k8s/` 目录：

```
k8s/
├── namespace.yml
├── secrets.yml.example
├── control-plane/
│   ├── deployment.yml
│   ├── service.yml
│   ├── ingress.yml
│   └── configmap.yml
├── gateway-service/
│   ├── deployment.yml
│   ├── service.yml
│   └── hpa.yml
├── approval-service/
├── artifact-service/
├── event-service/
├── pc-agent-java/
└── python-agent/
```

**control-plane deployment.yml 示例**：
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: control-plane
  namespace: autocode
spec:
  replicas: 2
  selector:
    matchLabels:
      app: control-plane
  template:
    metadata:
      labels:
        app: control-plane
    spec:
      containers:
        - name: control-plane
          image: ghcr.io/hyjkblj/autocode/control-plane-spring:latest
          ports:
            - containerPort: 8058
          env:
            - name: SPRING_PROFILES_ACTIVE
              value: "prod"
            - name: MVP_DB_URL
              valueFrom:
                secretKeyRef:
                  name: autocode-secrets
                  key: db-url
            - name: MVP_JWT_SECRET
              valueFrom:
                secretKeyRef:
                  name: autocode-secrets
                  key: jwt-secret
          livenessProbe:
            httpGet:
              path: /actuator/health/liveness
              port: 8058
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /actuator/health/readiness
              port: 8058
            initialDelaySeconds: 15
            periodSeconds: 5
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
```

**验收标准**：所有服务有 K8s 清单，含健康检查、资源限制、Secret 引用。

---

## 阶段四：可观测性补全（Week 2-3）

### 4.1 JSON 结构化日志

**当前问题**：所有服务用纯文本日志，无法被日志系统解析。

为每个 Java 服务添加 `logback-spring.xml`：

```xml
<!-- src/main/resources/logback-spring.xml -->
<configuration>
    <springProperty scope="context" name="APP_NAME" source="spring.application.name"/>

    <appender name="JSON" class="ch.qos.logback.core.ConsoleAppender">
        <encoder class="net.logstash.logback.encoder.LogstashEncoder">
            <includeMdcKeyName>traceId</includeMdcKeyName>
            <includeMdcKeyName>spanId</includeMdcKeyName>
            <customFields>{"service":"${APP_NAME}"}</customFields>
        </encoder>
    </appender>

    <root level="INFO">
        <appender-ref ref="JSON"/>
    </root>
</configuration>
```

添加依赖：
```xml
<dependency>
    <groupId>net.logstash.logback</groupId>
    <artifactId>logstash-logback-encoder</artifactId>
    <version>7.4</version>
</dependency>
```

**验收标准**：所有服务输出 JSON 格式日志，含 traceId、service 字段。

---

### 4.2 Prometheus 采集全部服务

**修改** `ops/observability/prometheus.yml`：

```yaml
scrape_configs:
  - job_name: 'control-plane'
    metrics_path: '/actuator/prometheus'
    static_configs:
      - targets: ['control-plane:8058']

  # 新增
  - job_name: 'gateway-service'
    metrics_path: '/actuator/prometheus'
    static_configs:
      - targets: ['gateway-service:8080']

  - job_name: 'approval-service'
    metrics_path: '/actuator/prometheus'
    static_configs:
      - targets: ['approval-service:8064']

  - job_name: 'artifact-service'
    metrics_path: '/actuator/prometheus'
    static_configs:
      - targets: ['artifact-service:8081']

  - job_name: 'event-service'
    metrics_path: '/actuator/prometheus'
    static_configs:
      - targets: ['event-service:8082']
```

**验收标准**：Prometheus 采集 7 个服务的指标。

---

### 4.3 告警规则补全

在 `ops/observability/alert_rules.yml` 中新增：

```yaml
  - name: autocode-services
    rules:
      - alert: ApprovalServiceDown
        expr: up{job="approval-service"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Approval Service is down"

      - alert: ArtifactServiceDown
        expr: up{job="artifact-service"} == 0
        for: 1m
        labels:
          severity: critical

      - alert: EventServiceDown
        expr: up{job="event-service"} == 0
        for: 1m
        labels:
          severity: critical

      - alert: HighApprovalTimeoutRate
        expr: rate(approval_timeout_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High approval timeout rate detected"

      - alert: EventDeduplicationBacklog
        expr: event_deduplication_pending > 1000
        for: 5m
        labels:
          severity: warning
```

**验收标准**：每个服务至少有 Down + 关键业务指标告警。

---

## 阶段五：可靠性加固（Week 3）

### 5.1 控制平面 CircuitBreaker

**当前问题**：控制平面调用 Redis/MySQL 无熔断保护。

添加 Resilience4j 依赖：
```xml
<dependency>
    <groupId>io.github.resilience4j</groupId>
    <artifactId>resilience4j-spring-boot3</artifactId>
    <version>2.2.0</version>
</dependency>
```

配置：
```yaml
resilience4j:
  circuitbreaker:
    instances:
      redis:
        slidingWindowSize: 10
        failureRateThreshold: 50
        waitDurationInOpenState: 30s
        permittedNumberOfCallsInHalfOpenState: 3
      database:
        slidingWindowSize: 10
        failureRateThreshold: 50
        waitDurationInOpenState: 30s
```

**验收标准**：Redis/MySQL 故障时控制平面降级而非崩溃。

---

### 5.2 全局任务并发限制

在 `TaskService` 中添加：
```java
private final Semaphore concurrentTasks;

public TaskService(...,
    @Value("${mvp.task.max-concurrent:50}") int maxConcurrent) {
    this.concurrentTasks = new Semaphore(maxConcurrent);
}

public TaskSummary createTask(...) {
    if (!concurrentTasks.tryAcquire(1, TimeUnit.SECONDS)) {
        throw new TooManyRequestsException("Task queue full");
    }
    try {
        // ... existing logic
    } finally {
        // 注意：这里不能 release，要在任务完成时 release
    }
}
```

**验收标准**：系统并发任务数不超过配置上限。

---

### 5.3 优雅停机

在每个服务的 `application.yml` 中添加：
```yaml
server:
  shutdown: graceful

spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s
```

在 K8s deployment 中配置：
```yaml
spec:
  terminationGracePeriodSeconds: 60
```

**验收标准**：服务收到 SIGTERM 后完成正在处理的请求再退出。

---

## 阶段六：安全收尾（Week 3）

### 6.1 HTTPS 强制

在 Nginx/Gateway 配置中：
```nginx
server {
    listen 80;
    server_name autocode.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    ssl_certificate /etc/ssl/certs/autocode.pem;
    ssl_certificate_key /etc/ssl/private/autocode.key;

    # 安全头
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

**验收标准**：HTTP 自动跳转 HTTPS，安全头全部配置。

---

### 6.2 WebSocket 认证

修改 `WebSocketConfig`，在 STOMP CONNECT 帧中验证 JWT：

```java
@Override
public void configureClientInboundChannel(ChannelRegistration registration) {
    registration.interceptors(new ChannelInterceptor() {
        @Override
        public Message<?> preSend(Message<?> message, MessageChannel channel) {
            StompHeaderAccessor accessor = MessageHeaderAccessor
                .getAccessor(message, StompHeaderAccessor.class);
            if (StompCommand.CONNECT.equals(accessor.getCommand())) {
                String authHeader = accessor.getFirstNativeHeader("Authorization");
                if (authHeader == null || !authHeader.startsWith("Bearer ")) {
                    throw new AccessDeniedException("Missing auth token");
                }
                // 验证 JWT...
            }
            return message;
        }
    });
}
```

**验收标准**：WebSocket 连接必须携带有效 JWT。

---

## 阶段七：上线验证（Week 4）

### 7.1 冒烟测试清单

```markdown
## 部署后冒烟测试

### 基础设施
- [ ] 所有 Pod 状态为 Running
- [ ] 所有 /actuator/health 返回 UP
- [ ] Prometheus 能采集所有服务指标
- [ ] Grafana 仪表盘数据正常

### 核心流程
- [ ] 用户登录 → 获取 JWT
- [ ] 创建任务 → 状态为 QUEUED
- [ ] Agent 领取任务 → 状态变为 RUNNING
- [ ] Agent 上报事件 → 事件流实时推送
- [ ] 任务完成 → 状态变为 DONE
- [ ] 审批流程 → APPROVAL_REQUIRED → 批准/拒绝
- [ ] 制品上传/下载
- [ ] 制品在线预览

### 安全
- [ ] 默认 JWT Secret 无法启动（P0 已验证）
- [ ] Actuator 端点需要 ROLE_ADMIN
- [ ] Event Service 需要 Agent Token
- [ ] 无权限请求返回 404（不泄露任务存在性）

### 可靠性
- [ ] 模拟 Redis 宕机 → 控制平面降级到内存队列
- [ ] 模拟 Agent 崩溃 → Lease 过期后任务自动回收
- [ ] 模拟网络断开 → Agent 重连 + 事件回填
```

### 7.2 回滚方案

```bash
# K8s 回滚到上一版本
kubectl rollout undo deployment/control-plane -n autocode
kubectl rollout undo deployment/gateway-service -n autocode
# ... 其他服务

# 验证回滚
kubectl rollout status deployment/control-plane -n autocode
```

---

## 检查清单总览

| 阶段 | 工作项 | 工作量 | 优先级 |
|------|--------|--------|--------|
| 1.1 | 3 服务添加 Flyway | 24h | P0 |
| 1.2 | 数据库备份策略 | 8h | P0 |
| 2.1 | 补全 Dockerfile (2 个) | 2h | P0 |
| 2.2 | CI/CD 流水线升级 | 16h | P0 |
| 2.3 | 安全扫描集成 | 8h | P0 |
| 3.1 | 多环境配置 | 8h | P0 |
| 3.2 | Kubernetes 清单 | 16h | P0 |
| 4.1 | JSON 结构化日志 | 8h | P0 |
| 4.2 | Prometheus 采集全服务 | 4h | P1 |
| 4.3 | 告警规则补全 | 4h | P1 |
| 5.1 | 控制平面 CircuitBreaker | 8h | P1 |
| 5.2 | 全局任务并发限制 | 4h | P1 |
| 5.3 | 优雅停机 | 2h | P1 |
| 6.1 | HTTPS 强制 + 安全头 | 2h | P1 |
| 6.2 | WebSocket 认证 | 4h | P0 |
| 7.1 | 冒烟测试执行 | 4h | P0 |
| 7.2 | 回滚方案验证 | 2h | P0 |
| **合计** | | **~126h** | |

**P0 工作量**：~88h（11 人天）
**P0+P1 工作量**：~126h（16 人天）
