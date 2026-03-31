package com.autocode.controlplane.artifacts.application;

public class ArtifactNotFoundException extends RuntimeException {
    public ArtifactNotFoundException(String message) {
        super(message);
    }
}

