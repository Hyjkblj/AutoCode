package com.autocode.controlplane.artifacts.ports;

import com.autocode.controlplane.artifacts.domain.ArtifactContent;
import com.autocode.controlplane.artifacts.domain.ArtifactRecord;

import java.io.InputStream;
import java.util.List;

public interface ArtifactsPort {
    ArtifactRecord store(String taskId, String name, String contentType, InputStream data);

    List<ArtifactRecord> listByTask(String taskId);

    ArtifactContent open(String taskId, String artifactId);
}

