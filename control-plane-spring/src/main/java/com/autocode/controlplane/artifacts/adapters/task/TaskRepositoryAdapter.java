package com.autocode.controlplane.artifacts.adapters.task;

import com.autocode.controlplane.artifacts.ports.TaskReadPort;
import com.autocode.controlplane.persistence.repo.TaskEntityRepository;
import org.springframework.stereotype.Component;

@Component
public class TaskRepositoryAdapter implements TaskReadPort {
    private final TaskEntityRepository taskRepository;

    public TaskRepositoryAdapter(TaskEntityRepository taskRepository) {
        this.taskRepository = taskRepository;
    }

    @Override
    public boolean exists(String taskId) {
        if (taskId == null || taskId.isBlank()) {
            return false;
        }
        return taskRepository.existsById(taskId);
    }
}

