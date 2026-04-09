package com.autocode.agent.runtime.skill;

import com.autocode.agent.runtime.intent.RoutedIntent;
import com.autocode.protocol.model.TaskSummary;

import java.io.IOException;

public interface Skill {
    String name();

    void execute(Context context) throws IOException, InterruptedException;

    interface Context {
        TaskSummary task();

        RoutedIntent intent();

        void runCodeExecution() throws IOException, InterruptedException;

        void runDeployExecution() throws IOException, InterruptedException;
    }
}

