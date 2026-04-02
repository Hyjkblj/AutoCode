package com.autocode.agent.security;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class WorkspacePrefixGuardTest {

    @Test
    void emptyAllowlistAllowsAny() {
        assertTrue(WorkspacePrefixGuard.isPathUnderAllowedPrefixes("D:/any/path", List.of()));
    }

    @Test
    void pathMustMatchNormalizedPrefix() {
        List<String> prefixes = List.of("D:/repo");
        assertTrue(WorkspacePrefixGuard.isPathUnderAllowedPrefixes("D:/repo/sub/a.zip", prefixes));
        assertFalse(WorkspacePrefixGuard.isPathUnderAllowedPrefixes("C:/other/a.zip", prefixes));
    }

    @Test
    void backslashNormalized() {
        List<String> prefixes = List.of("D:/repo");
        assertTrue(WorkspacePrefixGuard.isPathUnderAllowedPrefixes("D:\\repo\\out\\x.zip", prefixes));
    }
}
