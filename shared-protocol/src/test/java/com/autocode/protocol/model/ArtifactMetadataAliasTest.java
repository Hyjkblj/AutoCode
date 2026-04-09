package com.autocode.protocol.model;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class ArtifactMetadataAliasTest {

    @Test
    void legacy_fields_backfill_nl2web_aliases() {
        ArtifactMetadata metadata = new ArtifactMetadata();
        metadata.setName("export.zip");
        metadata.setHash("sha256:abc");
        metadata.setMime("application/zip");

        assertEquals("export.zip", metadata.getFileName());
        assertEquals("sha256:abc", metadata.getSha256());
        assertEquals("application/zip", metadata.getMimeType());
    }

    @Test
    void nl2web_aliases_backfill_legacy_fields() {
        ArtifactMetadata metadata = new ArtifactMetadata();
        metadata.setFileName("export.zip");
        metadata.setSha256("sha256:def");
        metadata.setMimeType("application/zip");

        assertEquals("export.zip", metadata.getName());
        assertEquals("sha256:def", metadata.getHash());
        assertEquals("application/zip", metadata.getMime());
    }
}

