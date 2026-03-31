package com.autocode.controlplane.service.ws;

import com.autocode.protocol.model.TaskEvent;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

@Component
public class TaskEventPublisher {
    private final SimpMessagingTemplate messagingTemplate;

    public TaskEventPublisher(SimpMessagingTemplate messagingTemplate) {
        this.messagingTemplate = messagingTemplate;
    }

    public void publishAfterCommit(String taskId, TaskEvent event) {
        if (TransactionSynchronizationManager.isActualTransactionActive()) {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    messagingTemplate.convertAndSend("/topic/tasks/" + taskId, event);
                }
            });
        } else {
            messagingTemplate.convertAndSend("/topic/tasks/" + taskId, event);
        }
    }
}

