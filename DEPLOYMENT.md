# AutoCode 部署指南

## 快速启动

```bash
# 1. 准备环境变量
cp .env.prod.example .env.prod
vim .env.prod  # 填入真实密码和密钥

# 2. 生成 JWT Secret
openssl rand -base64 48

# 3. 启动所有服务
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

# 4. 查看状态
docker compose -f docker-compose.prod.yml ps

# 5. 查看日志
docker compose -f docker-compose.prod.yml logs -f control-plane

# 6. 冒烟测试
BASE_URL=http://localhost:8080 ./scripts/smoke-test.sh
```

## 停止与重启

```bash
# 停止所有服务
docker compose -f docker-compose.prod.yml down

# 停止并删除数据卷（危险！会丢失数据）
docker compose -f docker-compose.prod.yml down -v

# 重启单个服务
docker compose -f docker-compose.prod.yml restart control-plane
```

## 数据备份

```bash
# 手动备份
DB_HOST=localhost DB_USER=root DB_PASS=xxx ./scripts/backup-mysql.sh

# 自动备份（每天凌晨 3 点）
crontab -e
# 添加: 0 3 * * * DB_HOST=localhost DB_USER=root DB_PASS=xxx /path/to/scripts/backup-mysql.sh
```

## 回滚

```bash
# 回滚单个服务到上一版本镜像
docker compose -f docker-compose.prod.yml pull control-plane
docker compose -f docker-compose.prod.yml up -d control-plane

# 或使用回滚脚本
./scripts/rollback-k8s.sh  # K8s 环境
```

## GitHub Actions CI/CD Secrets 配置

在 GitHub 仓库 Settings → Secrets and variables → Actions 中添加：

| Secret 名称 | 说明 | 示例 |
|-------------|------|------|
| `DOCKER_REGISTRY` | 镜像仓库地址 | `ghcr.io` |
| `STAGING_HOST` | Staging 服务器 IP | `192.168.1.100` |
| `STAGING_SSH_KEY` | Staging SSH 私钥 | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `PROD_HOST` | 生产服务器 IP | `10.0.0.50` |
| `PROD_SSH_KEY` | 生产 SSH 私钥 | `-----BEGIN OPENSSH PRIVATE KEY-----...` |

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| gateway-service | 8080 | 主入口（对外暴露） |
| control-plane | 8058 | 控制平面（内部） |
| approval-service | 8064 | 审批服务（内部） |
| artifact-service | 8081 | 制品服务（内部） |
| event-service | 8082 | 事件服务（内部） |
| mysql | 3306 | 数据库（内部） |
| redis | 6379 | 缓存（内部） |
| prometheus | 9090 | 监控（内部） |
| grafana | 3000 | 仪表盘（可选对外） |
