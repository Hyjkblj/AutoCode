package com.autocode.controlplane.artifacts.application;

public class ArtifactForbiddenException extends RuntimeException {
    public ArtifactForbiddenException(String message) {
        super(message);
    }
}

