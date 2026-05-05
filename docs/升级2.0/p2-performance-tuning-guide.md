# P2 性能调优指南

## 目标

P2 的性能调优不是追求极限吞吐，而是先建立稳定、可验证、可回退的优化路径。

## 当前已具备的性能抓手

1. Python Agent LLM 响应缓存（LRU + TTL）
2. 插件熔断与 fallback
3. LangGraph 灰度执行路径
4. Prometheus 指标采集

## 建议优先级

### P0 先做稳定性收益最大的

1. 打开 LLM Cache
   关键变量：
   `MVP_LLM_CACHE_ENABLED`
   `MVP_LLM_CACHE_MAX_SIZE`
   `MVP_LLM_CACHE_TTL_SECONDS`

2. 控制 fix-loop 次数
   关键变量：
   `MVP_FIX_LOOP_MAX_ATTEMPTS`

3. 先按意图灰度 LangGraph
   例如：
   `AGENT_ENGINE=langgraph`
   并仅迁移 `analyze` / `test`

### P1 再做吞吐调优

1. 优化数据库与 Redis 连接池
2. 减少长路径同步阻塞
3. 对热点任务类型做模板化和缓存化

## LLM Cache 调优建议

### 适合增大 TTL 的场景

1. 意图识别提示词稳定
2. 规划结果高度重复
3. Web 模板生成存在大量相似请求

### 不适合盲目增大 TTL 的场景

1. 提示词中包含强上下文差异
2. 结构化输出质量不稳定
3. 频繁出现坏缓存命中

### 建议起步值

1. `MVP_LLM_CACHE_MAX_SIZE=128`
2. `MVP_LLM_CACHE_TTL_SECONDS=300`

### 观测指标

1. `llm_cache_requests_total`
2. `llm_cache_hits_total`
3. `llm_cache_misses_total`
4. `llm_cache_discards_total`
5. `llm_cache_failures_total`

如果 `discard` 明显升高，说明结构化输出质量不足，不能只靠增大缓存解决。

## 网关层调优建议

1. 保持合理 `proxy_read_timeout`
2. 针对长任务接口区分超时时间
3. 后续可加入限流与连接数保护

## Control Plane 调优建议

1. 优先观察 P95 而不是平均值
2. 结合 JVM heap 与 5xx 一起看，避免只看单点指标
3. 为任务创建、事件发布、任务分发补充业务级 metrics

## 回退策略

出现以下任一情况应停止继续放量：

1. P95 上升超过 20%
2. 错误率持续升高
3. fix-loop 次数异常增多
4. breaker 频繁打开

回退动作：

1. 缩小灰度
2. 切回 `legacy`
3. 关闭问题插件
4. 下调并发与缓存 TTL
