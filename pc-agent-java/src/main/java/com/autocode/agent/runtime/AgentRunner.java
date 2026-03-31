/**
 * Long-running agent loop: register/heartbeat, poll tasks, and delegate execution.
 */
package com.autocode.agent.runtime;

import com.autocode.agent.client.AgentApiClient;
import com.autocode.agent.config.AgentConfig;
import com.autocode.agent.config.AgentConfigFileLoader;
import com.autocode.protocol.model.TaskSummary;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.time.Instant;
import java.util.Optional;

public class AgentRunner {
    private static final Logger log = LoggerFactory.getLogger(AgentRunner.class);

    private volatile AgentConfig config;
    private final AgentApiClient apiClient;
    private final TaskExecutor taskExecutor;
    private final File configFile;
    private volatile long configFileLastModified = -1;
    private final AgentConfigFileLoader configFileLoader = new AgentConfigFileLoader();

    public AgentRunner(AgentConfig config) {
        this.config = config;
        this.apiClient = new AgentApiClient(config.getBaseUrl(), config.getAgentToken());
        this.taskExecutor = new TaskExecutor(apiClient, config);
        String path = System.getenv("MVP_AGENT_CONFIG_PATH");
        this.configFile = (path == null || path.isBlank()) ? null : new File(path.trim());
    }

    /**
     * Agent 主循环：注册 -> 心跳 -> 轮询任务 -> 执行 -> 上报事件。
     */
    public void start() throws IOException, InterruptedException {
        waitUntilRegistered();

        long lastHeartbeat = 0;
        long lastConfigCheck = 0;
        while (true) {
            long now = System.currentTimeMillis();
            try {
                if (now - lastConfigCheck > 3000) {
                    lastConfigCheck = now;
                    reloadConfigIfChanged();
                }
                if (now - lastHeartbeat > config.getHeartbeatIntervalMs()) {
                    // 定期心跳：用于控制平面判断节点在线状态
                    apiClient.heartbeat(config.getNodeId());
                    lastHeartbeat = now;
                    log.info("Heartbeat sent at {}", Instant.ofEpochMilli(now));
                }

                // 轮询领取任务：服务端会从队列中分配一个 QUEUED 任务给该节点
                Optional<TaskSummary> task = apiClient.pollNextTask(config.getNodeId());
                if (task.isPresent()) {
                    log.info("Received task {}", task.get().getTaskId());
                    try {
                        // 执行任务：会产生事件（输出/工具/审批/完成等）回传控制平面
                        taskExecutor.execute(task.get());
                        log.info("Task {} finished", task.get().getTaskId());
                    } catch (Exception ex) {
                        log.error("Task {} execution failed", task.get().getTaskId(), ex);
                    }
                    continue;
                }
            } catch (IOException ioException) {
                log.warn("Control plane unavailable, retrying: {}", ioException.getMessage());
                waitUntilRegistered();
            }

            Thread.sleep(config.getPollIntervalMs());
        }
    }

    private void reloadConfigIfChanged() {
        if (configFile == null) {
            return;
        }
        long modified = configFile.lastModified();
        if (modified <= 0 || modified == configFileLastModified) {
            return;
        }
        AgentConfig loaded = configFileLoader.loadOverrides(configFile);
        if (loaded == null) {
            return;
        }
        // Only support hot-updating runtime knobs; baseUrl/token/nodeId are pinned to env.
        this.config = loaded;
        this.taskExecutor.updateConfig(loaded);
        this.configFileLastModified = modified;
        log.info("Reloaded agent config from {} (pollMs={}, heartbeatMs={}, approvalTimeoutS={})",
                configFile.getAbsolutePath(),
                loaded.getPollIntervalMs(),
                loaded.getHeartbeatIntervalMs(),
                loaded.getApprovalTimeoutSeconds());
    }

    private void waitUntilRegistered() throws InterruptedException {
        while (true) {
            try {
                log.info("Registering node {} to {}", config.getNodeId(), config.getBaseUrl());
                // 注册节点：用于控制平面记录 nodeId/version/capabilities 等
                apiClient.register(config.getNodeId());
                return;
            } catch (IOException exception) {
                log.warn("Register failed, retrying in 2s: {}", exception.getMessage());
                Thread.sleep(2000);
            }
        }
    }
}
