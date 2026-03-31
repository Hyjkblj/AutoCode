/**
 * Registers and tracks agent nodes and their heartbeat-based online status.
 */
package com.autocode.controlplane.service;

import com.autocode.controlplane.api.AgentHeartbeatRequest;
import com.autocode.controlplane.api.AgentRegisterRequest;
import com.autocode.controlplane.model.AgentNode;
import com.autocode.controlplane.persistence.entity.AgentNodeEntity;
import com.autocode.controlplane.persistence.repo.AgentNodeEntityRepository;
import com.autocode.controlplane.service.mapper.ModelMapper;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.function.Consumer;

@Service
@Transactional
public class AgentRegistryService {
    private static final Duration OFFLINE_TIMEOUT = Duration.ofSeconds(30);

    private final AgentNodeEntityRepository agentNodeRepository;
    private final ModelMapper modelMapper;

    public AgentRegistryService(AgentNodeEntityRepository agentNodeRepository, ModelMapper modelMapper) {
        this.agentNodeRepository = agentNodeRepository;
        this.modelMapper = modelMapper;
    }

    public AgentNode register(AgentRegisterRequest request) {
        AgentNodeEntity saved = upsertNode(request.getNodeId(), node -> {
            node.setVersion(request.getVersion());
            node.setCapabilities(request.getCapabilities());
            node.setLastHeartbeatAt(Instant.now());
        });
        return modelMapper.toAgentNode(saved, true);
    }

    public AgentNode heartbeat(AgentHeartbeatRequest request) {
        AgentNodeEntity saved = upsertNode(request.getNodeId(), node -> node.setLastHeartbeatAt(Instant.now()));
        return modelMapper.toAgentNode(saved, true);
    }

    @Transactional(readOnly = true)
    public List<AgentNode> listAgents() {
        Instant now = Instant.now();
        return agentNodeRepository.findAll().stream()
                .map(entity -> modelMapper.toAgentNode(entity, isOnline(entity.getLastHeartbeatAt(), now)))
                .toList();
    }

    private boolean isOnline(Instant lastHeartbeatAt, Instant now) {
        if (lastHeartbeatAt == null) {
            return false;
        }
        return Duration.between(lastHeartbeatAt, now).compareTo(OFFLINE_TIMEOUT) <= 0;
    }

    /**
     * 幂等 upsert：在并发 register/heartbeat 下避免主键冲突。
     */
    private AgentNodeEntity upsertNode(String nodeId, Consumer<AgentNodeEntity> mutator) {
        AgentNodeEntity node = new AgentNodeEntity();
        node.setNodeId(nodeId);
        mutator.accept(node);
        try {
            // saveAndFlush：尽早触发唯一键冲突，便于捕获后走更新路径
            return agentNodeRepository.saveAndFlush(node);
        } catch (DataIntegrityViolationException ex) {
            AgentNodeEntity existing = agentNodeRepository.findById(nodeId).orElseThrow();
            mutator.accept(existing);
            return agentNodeRepository.save(existing);
        }
    }
}
