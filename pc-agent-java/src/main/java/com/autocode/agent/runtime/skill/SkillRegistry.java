package com.autocode.agent.runtime.skill;

import com.autocode.agent.runtime.skill.impl.CodeExecSkill;
import com.autocode.agent.runtime.skill.impl.DeployExecuteSkill;

import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

public class SkillRegistry {
    private final Map<String, Skill> skills = new HashMap<>();
    private String defaultSkillKey = normalize(CodeExecSkill.NAME);

    public SkillRegistry register(Skill skill, String... aliases) {
        if (skill == null || isBlank(skill.name())) {
            throw new IllegalArgumentException("skill name required");
        }
        Skill s = skill;
        skills.put(normalize(skill.name()), s);
        if (aliases != null) {
            for (String alias : aliases) {
                if (!isBlank(alias)) {
                    skills.put(normalize(alias), s);
                }
            }
        }
        return this;
    }

    public SkillRegistry clear() {
        skills.clear();
        return this;
    }

    public SkillRegistry setDefaultSkill(String defaultSkillName) {
        if (!isBlank(defaultSkillName)) {
            this.defaultSkillKey = normalize(defaultSkillName);
        }
        return this;
    }

    public Skill resolve(String requestedSkill) {
        Skill exact = skills.get(normalize(requestedSkill));
        if (exact != null) {
            return exact;
        }
        String normalized = normalize(requestedSkill);
        if (!isBlank(normalized) && normalized.contains("deploy")) {
            Skill deploy = skills.get(normalize(DeployExecuteSkill.NAME));
            if (deploy != null) {
                return deploy;
            }
        }
        Skill fallback = skills.get(defaultSkillKey);
        if (fallback == null) {
            throw new IllegalStateException("default skill is not registered: " + defaultSkillKey);
        }
        return fallback;
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }

    private static String normalize(String value) {
        if (value == null) {
            return null;
        }
        String normalized = value.trim().toLowerCase(Locale.ROOT);
        return normalized.isEmpty() ? null : normalized;
    }
}

