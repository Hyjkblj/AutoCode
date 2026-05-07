/**
 * Unit tests for EventController - explicit ACK protocol implementation.
 */
package com.autocode.event;

import com.autocode.controlplane.api.AgentEventRequest;
import com.autocode.controlplane.service.AgentRegistryService;
import com.autocode.controlplane.service.TaskService;
import com.autocode.controlplane.service.observability.ControlPlaneMetrics;
import com.autocode.protocol.model.EventType;
import com.autocode.protocol.model.TaskEvent;
import com.autocode.protocol.model.TaskSummary;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.MediaType;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;
import java.util.HashMap;
import java.util.Optional;

import static org.hamcrest.Matchers.containsString;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest
@AutoConfigureMockMvc(addFilters = false)
@ContextConfiguration(classes = EventController.class)
@Import(EventControllerTest.TestConfig.class)
class EventControllerTest {

    @TestConfiguration
    static class TestConfig {
        @Bean
        public ControlPlaneMetrics controlPlaneMetrics() {
            return new ControlPlaneMetrics(new SimpleMeterRegistry());
        }
    }

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private TaskService taskService;

    @MockBean
    private StringRedisTemplate redisTemplate;

    @MockBean
    private EventDeduplicationService deduplicationService;

    @MockBean
    private AgentRegistryService agentRegistryService;

    private TaskEvent testEvent;
    private AgentEventRequest testRequest;
    private TaskSummary testTaskSummary;

    @BeforeEach
    void setUp() {
        testEvent = new TaskEvent();
        testEvent.setEventId("evt_test123");
        testEvent.setTaskId("tsk_test123");
        testEvent.setType(EventType.TASK_STARTED);
        testEvent.setTimestamp(Instant.now());
        testEvent.setSeq(1L);
        testEvent.setPayload(new HashMap<>());

        testRequest = new AgentEventRequest();
        testRequest.setEvent(testEvent);

        testTaskSummary = new TaskSummary();
        testTaskSummary.setTaskId("tsk_test123");
    }

    @Test
    void ingestEventWithAck_Success() throws Exception {
        when(agentRegistryService.isNodeRegistered("node123")).thenReturn(true);
        when(deduplicationService.isDuplicate("evt_test123")).thenReturn(false);
        when(taskService.ingestAgentEvent(eq("tsk_test123"), any(TaskEvent.class), eq("node123")))
                .thenReturn(Optional.of(new TaskService.IngestResult(testTaskSummary, 1L, false)));

        mockMvc.perform(post("/api/v1/events/ingest")
                        .param("taskId", "tsk_test123")
                        .param("nodeId", "node123")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(testRequest)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.seq").value(1))
                .andExpect(jsonPath("$.payload.accepted").value(true))
                .andExpect(jsonPath("$.payload.duplicate").value(false))
                .andExpect(jsonPath("$.payload.errorCode").doesNotExist());

        verify(deduplicationService).markProcessed("evt_test123", 1L);
    }

    @Test
    void ingestEventWithAck_DuplicateEvent() throws Exception {
        when(agentRegistryService.isNodeRegistered("node123")).thenReturn(true);
        when(deduplicationService.isDuplicate("evt_test123")).thenReturn(true);
        when(deduplicationService.getOriginalSequence("evt_test123")).thenReturn(1L);

        mockMvc.perform(post("/api/v1/events/ingest")
                        .param("taskId", "tsk_test123")
                        .param("nodeId", "node123")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(testRequest)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.seq").value(1))
                .andExpect(jsonPath("$.payload.accepted").value(true))
                .andExpect(jsonPath("$.payload.duplicate").value(true))
                .andExpect(jsonPath("$.payload.errorCode").doesNotExist());

        verify(taskService, never()).ingestAgentEvent(any(), any(), any());
    }

    @Test
    void ingestEventWithAck_NodeNotRegistered() throws Exception {
        when(agentRegistryService.isNodeRegistered("node123")).thenReturn(false);

        mockMvc.perform(post("/api/v1/events/ingest")
                        .param("taskId", "tsk_test123")
                        .param("nodeId", "node123")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(testRequest)))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.seq").value(0))
                .andExpect(jsonPath("$.payload.accepted").value(false))
                .andExpect(jsonPath("$.payload.duplicate").value(false))
                .andExpect(jsonPath("$.payload.errorCode").value("NODE_NOT_REGISTERED"));

        verify(taskService, never()).ingestAgentEvent(any(), any(), any());
    }

    @Test
    void ingestEventWithAck_TaskNotFound() throws Exception {
        when(agentRegistryService.isNodeRegistered("node123")).thenReturn(true);
        when(deduplicationService.isDuplicate("evt_test123")).thenReturn(false);
        when(taskService.ingestAgentEvent(eq("tsk_test123"), any(TaskEvent.class), eq("node123")))
                .thenReturn(Optional.empty());

        mockMvc.perform(post("/api/v1/events/ingest")
                        .param("taskId", "tsk_test123")
                        .param("nodeId", "node123")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(testRequest)))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.seq").value(0))
                .andExpect(jsonPath("$.payload.accepted").value(false))
                .andExpect(jsonPath("$.payload.duplicate").value(false))
                .andExpect(jsonPath("$.payload.errorCode").value("TASK_NOT_FOUND"));
    }

    @Test
    void ingestEventWithAck_MissingEventId() throws Exception {
        testEvent.setEventId(null);
        testRequest.setEvent(testEvent);

        mockMvc.perform(post("/api/v1/events/ingest")
                        .param("taskId", "tsk_test123")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(testRequest)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.seq").value(0))
                .andExpect(jsonPath("$.payload.accepted").value(false))
                .andExpect(jsonPath("$.payload.duplicate").value(false))
                .andExpect(jsonPath("$.payload.errorCode").value("MISSING_EVENT_ID"));
    }

    @Test
    void ingestEventWithAck_WithoutNodeId() throws Exception {
        when(deduplicationService.isDuplicate("evt_test123")).thenReturn(false);
        when(taskService.ingestAgentEvent(eq("tsk_test123"), any(TaskEvent.class), isNull()))
                .thenReturn(Optional.of(new TaskService.IngestResult(testTaskSummary, 1L, false)));

        mockMvc.perform(post("/api/v1/events/ingest")
                        .param("taskId", "tsk_test123")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(testRequest)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.seq").value(1))
                .andExpect(jsonPath("$.payload.accepted").value(true))
                .andExpect(jsonPath("$.payload.duplicate").value(false))
                .andExpect(jsonPath("$.payload.errorCode").doesNotExist());

        verify(agentRegistryService, never()).isNodeRegistered(any());
    }

    @Test
    void ingestEventWithAck_DBDuplicate() throws Exception {
        when(agentRegistryService.isNodeRegistered("node123")).thenReturn(true);
        when(deduplicationService.isDuplicate("evt_test123")).thenReturn(false);
        when(taskService.ingestAgentEvent(eq("tsk_test123"), any(TaskEvent.class), eq("node123")))
                .thenReturn(Optional.of(new TaskService.IngestResult(testTaskSummary, 5L, true)));

        mockMvc.perform(post("/api/v1/events/ingest")
                        .param("taskId", "tsk_test123")
                        .param("nodeId", "node123")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(testRequest)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.seq").value(5))
                .andExpect(jsonPath("$.payload.accepted").value(true))
                .andExpect(jsonPath("$.payload.duplicate").value(true))
                .andExpect(jsonPath("$.payload.errorCode").doesNotExist());

        verify(deduplicationService).markProcessed("evt_test123", 5L);
    }

    @Test
    void health_Success() throws Exception {
        when(redisTemplate.opsForValue()).thenReturn(mock(org.springframework.data.redis.core.ValueOperations.class));
        when(redisTemplate.opsForValue().get("health:check")).thenReturn("ok");

        mockMvc.perform(get("/api/v1/events/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload").value("Event processing healthy"));
    }

    @Test
    void health_RedisFailure() throws Exception {
        when(redisTemplate.opsForValue()).thenThrow(new RuntimeException("Redis connection failed"));

        mockMvc.perform(get("/api/v1/events/health"))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value(containsString("Event processing unhealthy")));
    }
}
