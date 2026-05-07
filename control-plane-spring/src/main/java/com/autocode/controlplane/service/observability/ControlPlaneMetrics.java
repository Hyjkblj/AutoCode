package com.autocode.controlplane.service.observability;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import org.springframework.stereotype.Component;

@Component
public class ControlPlaneMetrics {
    private final MeterRegistry registry;
    public final Counter tasksCreated;
    public final Counter tasksPolled;
    public final Counter taskEventsIngested;
    public final Counter duplicateEvents;
    public final Counter illegalStateTransitions;
    public final Counter ackFailures;
    public final Counter leaseRequeued;
    public final Timer pollDuration;

    public ControlPlaneMetrics(MeterRegistry registry) {
        this.registry = registry;
        this.tasksCreated = registry.counter("mvp_tasks_created_total");
        this.tasksPolled = registry.counter("mvp_tasks_polled_total");
        this.taskEventsIngested = registry.counter("mvp_task_events_ingested_total");
        this.duplicateEvents = registry.counter("mvp_task_events_duplicate_total");
        this.illegalStateTransitions = registry.counter("mvp_task_illegal_transition_total");
        this.ackFailures = registry.counter("mvp_task_ack_failures_total");
        this.leaseRequeued = registry.counter("mvp_task_lease_requeued_total");
        this.pollDuration = registry.timer("mvp_task_poll_duration");
    }

    public Timer.Sample startPollSample() {
        return Timer.start(registry);
    }
}

