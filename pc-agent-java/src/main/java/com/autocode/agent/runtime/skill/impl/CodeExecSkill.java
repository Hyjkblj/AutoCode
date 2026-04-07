package com.autocode.agent.runtime.skill.impl;

import com.autocode.agent.runtime.skill.Skill;

import java.io.IOException;

public class CodeExecSkill implements Skill {
    public static final String NAME = "skill.code.exec";

    @Override
    public String name() {
        return NAME;
    }

    @Override
    public void execute(Context context) throws IOException, InterruptedException {
        context.runCodeExecution();
    }
}

