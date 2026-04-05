package com.autocode.agent.runtime.skill;

import com.autocode.agent.runtime.skill.impl.CodeExecSkill;
import com.autocode.agent.runtime.skill.impl.DeployExecuteSkill;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class SkillRegistryTest {

    @Test
    void resolvesExactAndAlias() {
        SkillRegistry registry = new SkillRegistry()
                .clear()
                .register(new CodeExecSkill(), "command.exec")
                .register(new DeployExecuteSkill(), "deploy.execute")
                .setDefaultSkill(CodeExecSkill.NAME);

        assertEquals(CodeExecSkill.NAME, registry.resolve(CodeExecSkill.NAME).name());
        assertEquals(CodeExecSkill.NAME, registry.resolve("command.exec").name());
        assertEquals(DeployExecuteSkill.NAME, registry.resolve("deploy.execute").name());
    }

    @Test
    void deployHintFallsToDeploySkill() {
        SkillRegistry registry = new SkillRegistry()
                .clear()
                .register(new CodeExecSkill(), "command.exec")
                .register(new DeployExecuteSkill(), "deploy.execute")
                .setDefaultSkill(CodeExecSkill.NAME);

        assertEquals(DeployExecuteSkill.NAME, registry.resolve("skill.deploy.pipeline").name());
    }

    @Test
    void unknownSkillFallsBackToDefault() {
        SkillRegistry registry = new SkillRegistry()
                .clear()
                .register(new CodeExecSkill(), "command.exec")
                .register(new DeployExecuteSkill(), "deploy.execute")
                .setDefaultSkill(CodeExecSkill.NAME);

        assertEquals(CodeExecSkill.NAME, registry.resolve("skill.unknown").name());
        assertEquals(CodeExecSkill.NAME, registry.resolve(null).name());
    }
}

