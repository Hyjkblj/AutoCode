# 贡献指南

感谢你对 AutoCode 项目的关注！本文档将帮助你了解如何参与项目开发。

## 行为准则

- 尊重所有贡献者
- 保持专业和友好的交流
- 接受建设性批评

## 如何贡献

### 报告问题

如果你发现了 bug 或有功能建议：

1. 在 GitHub Issues 中搜索是否已有相关问题
2. 如果没有，创建新的 Issue，包含：
   - 清晰的标题
   - 问题描述
   - 复现步骤（如果是 bug）
   - 期望行为
   - 实际行为
   - 环境信息（操作系统、Java版本等）

### 提交代码

1. **Fork 仓库**
   ```bash
   git clone https://github.com/your-username/AutoCode.git
   cd AutoCode
   ```

2. **创建分支**
   ```bash
   git checkout -b feature/your-feature-name
   # 或
   git checkout -b fix/your-bug-fix
   ```

3. **编写代码**
   - 遵循现有代码风格
   - 添加必要的测试
   - 更新相关文档

4. **提交更改**
   ```bash
   git add .
   git commit -m "feat: 添加新功能描述"
   # 或
   git commit -m "fix: 修复问题描述"
   ```

   提交信息格式：
   - `feat:` 新功能
   - `fix:` Bug 修复
   - `docs:` 文档更新
   - `refactor:` 代码重构
   - `test:` 测试相关
   - `chore:` 构建/工具相关

5. **推送分支**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **创建 Pull Request**
   - 在 GitHub 上创建 PR
   - 描述你的更改
   - 关联相关 Issue

## 开发环境设置

### 前置条件

- JDK 17+（推荐 JDK 21）
- Docker 和 Docker Compose
- Python 3.11+（用于 Python Agent 开发）
- Node.js（可选，用于前端开发）

### 本地运行

```bash
# 1. 复制环境变量配置
cp .env.example .env
# 编辑 .env 文件

# 2. 启动基础设施
docker compose up -d

# 3. 构建项目
mvn -DskipTests install

# 4. 运行测试
mvn test
```

## 代码规范

### Java

- 遵循 Google Java Style Guide
- 使用 4 空格缩进
- 类名使用 PascalCase
- 方法名和变量名使用 camelCase
- 常量使用 UPPER_SNAKE_CASE

### Python

- 遵循 PEP 8
- 使用 4 空格缩进
- 函数和变量使用 snake_case
- 类名使用 PascalCase

### 提交规范

- 每个提交应该是一个独立的、原子性的更改
- 提交信息应该清晰描述更改内容
- 避免提交无关的更改

## 测试

- 所有新功能必须包含单元测试
- Bug 修复应该包含回归测试
- 确保所有测试通过后再提交 PR

```bash
# 运行所有测试
mvn test

# 运行特定模块测试
cd control-plane-spring && mvn test
```

## 文档

- 更新 README.md 如果有功能变更
- 更新 API 文档如果有接口变更
- 添加代码注释解释复杂逻辑

## 安全问题

如果你发现安全漏洞，请不要公开提交 Issue。请发送邮件到安全团队进行报告。

## 许可证

通过贡献代码，你同意你的代码将根据 MIT 许可证授权。
