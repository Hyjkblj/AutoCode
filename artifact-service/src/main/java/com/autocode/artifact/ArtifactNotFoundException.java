package com.autocode.artifact;

/**
 * Thrown when a requested artifact does not exist or the caller does not have access.
 */
public class ArtifactNotFoundException extends RuntimeException {

    public ArtifactNotFoundException(String message) {
        super(message);
    }
}
