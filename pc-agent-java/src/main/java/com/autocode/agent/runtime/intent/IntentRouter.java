package com.autocode.agent.runtime.intent;

import com.autocode.protocol.model.TaskSummary;

public interface IntentRouter {
    RoutedIntent route(TaskSummary task);
}

