package com.autocode.controlplane;

import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.assertTrue;

class FlywayMigrationVersionUniquenessTest {

    private static final Pattern VERSIONED_MIGRATION = Pattern.compile("^V(\\d+)__.+\\.sql$");

    @Test
    void flywayVersionNumbersMustBeUnique() throws IOException {
        String basedir = System.getProperty("basedir", ".");
        Path migrationsDir = Path.of(basedir, "src", "main", "resources", "db", "migration");
        Map<String, List<String>> byVersion = new LinkedHashMap<>();

        try (Stream<Path> files = Files.list(migrationsDir)) {
            files.filter(Files::isRegularFile)
                    .map(path -> path.getFileName().toString())
                    .sorted()
                    .forEach(name -> {
                        Matcher matcher = VERSIONED_MIGRATION.matcher(name);
                        if (!matcher.matches()) {
                            return;
                        }
                        byVersion.computeIfAbsent(matcher.group(1), ignored -> new ArrayList<>()).add(name);
                    });
        }

        List<String> duplicates = byVersion.entrySet().stream()
                .filter(entry -> entry.getValue().size() > 1)
                .map(entry -> "V" + entry.getKey() + ": " + entry.getValue())
                .sorted()
                .toList();

        assertTrue(duplicates.isEmpty(), "Duplicate Flyway migration versions detected: " + duplicates);
    }
}
