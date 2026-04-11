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

    @Test
    void siblingPrefixMustNotMatch() {
        List<String> prefixes = List.of("D:/repo");
        assertFalse(WorkspacePrefixGuard.isPathUnderAllowedPrefixes("D:/repo2/out.txt", prefixes));
    }

    @Test
    void dotSegmentsAreNormalizedBeforePrefixCheck() {
        List<String> prefixes = List.of("D:/repo");
        assertTrue(WorkspacePrefixGuard.isPathUnderAllowedPrefixes("D:/repo/sub/../out.txt", prefixes));
        assertFalse(WorkspacePrefixGuard.isPathUnderAllowedPrefixes("D:/repo/sub/../../outside.txt", prefixes));
    }

    @Test
    void windowsDrivePathsAreComparedCaseInsensitively() {
        List<String> prefixes = List.of("D:/Develop/Project/AutoCode");
        assertTrue(WorkspacePrefixGuard.isPathUnderAllowedPrefixes("D:/develop/project/autocode/python-agent", prefixes));
    }
}
