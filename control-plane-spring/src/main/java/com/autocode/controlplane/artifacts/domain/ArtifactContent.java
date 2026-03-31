package com.autocode.controlplane.artifacts.domain;

import java.io.InputStream;

public record ArtifactContent(
        ArtifactRecord record,
        InputStream stream
) {
}

