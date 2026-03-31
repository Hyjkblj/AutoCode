package com.autocode.agent.runtime.tool;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ToolRegistryTest {
    @Test
    void getRequiredThrowsWhenMissing() {
        ToolRegistry registry = new ToolRegistry();
        IllegalArgumentException ex = assertThrows(IllegalArgumentException.class, () -> registry.getRequired("missing"));
        assertTrue(ex.getMessage().contains("unknown tool"));
    }
}

