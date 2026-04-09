package com.autocode.agent.runtime.skill.impl;

import com.autocode.agent.runtime.skill.Skill;

import java.io.IOException;

public class DeployExecuteSkill implements Skill {
    public static final String NAME = "skill.deploy.execute";

    @Override
    public String name() {
        return NAME;
    }

    @Override
    public void execute(Context context) throws IOException, InterruptedException {
        context.runDeployExecution();
    }
}

