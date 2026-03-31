/**
 * Wrapper payload for posting a task event from an agent.
 */
package com.autocode.controlplane.api;

import com.autocode.protocol.model.TaskEvent;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;

public class AgentEventRequest {
    @Valid
    @NotNull
    private TaskEvent event;

    public TaskEvent getEvent() {
        return event;
    }

    public void setEvent(TaskEvent event) {
        this.event = event;
    }
}
