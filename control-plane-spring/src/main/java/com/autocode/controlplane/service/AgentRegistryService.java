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
        String nodeId = normalizeRequired(request.getNodeId(), "nodeId");
        String version = normalizeOptional(request.getVersion());
        String capabilities = normalizeOptional(request.getCapabilities());
        AgentNodeEntity saved = upsertNode(nodeId, node -> {
            node.setVersion(version);
            node.setCapabilities(capabilities);
            node.setLastHeartbeatAt(Instant.now());
        });
        return modelMapper.toAgentNode(saved, true);
    }

    public AgentNode heartbeat(AgentHeartbeatRequest request) {
        String nodeId = normalizeRequired(request.getNodeId(), "nodeId");
        AgentNodeEntity saved = upsertNode(nodeId, node -> node.setLastHeartbeatAt(Instant.now()));
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
     * Idempotent upsert to avoid duplicate key failures under concurrent register/heartbeat.
     */
    private AgentNodeEntity upsertNode(String nodeId, Consumer<AgentNodeEntity> mutator) {
        AgentNodeEntity existing = agentNodeRepository.findById(nodeId).orElse(null);
        if (existing != null) {
            mutator.accept(existing);
            return agentNodeRepository.save(existing);
        }

        AgentNodeEntity created = new AgentNodeEntity();
        created.setNodeId(nodeId);
        mutator.accept(created);
        try {
            return agentNodeRepository.saveAndFlush(created);
        } catch (DataIntegrityViolationException ex) {
            // Another concurrent writer inserted same nodeId first; update that row.
            AgentNodeEntity collided = agentNodeRepository.findById(nodeId).orElseThrow();
            mutator.accept(collided);
            return agentNodeRepository.save(collided);
        }
    }

    private static String normalizeRequired(String value, String fieldName) {
        String normalized = normalizeOptional(value);
        if (normalized == null) {
            throw new IllegalArgumentException(fieldName + " must not be blank");
        }
        return normalized;
    }

    private static String normalizeOptional(String value) {
        if (value == null) {
            return null;
        }
        String normalized = value.trim();
        return normalized.isEmpty() ? null : normalized;
    }
}
