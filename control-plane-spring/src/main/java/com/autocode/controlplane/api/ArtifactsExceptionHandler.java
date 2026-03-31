package com.autocode.controlplane.api;

import com.autocode.controlplane.artifacts.application.ArtifactForbiddenException;
import com.autocode.controlplane.artifacts.application.ArtifactNotFoundException;
import com.autocode.controlplane.artifacts.application.TaskNotFoundException;
import com.autocode.protocol.model.GatewayResponse;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.authorization.AuthorizationDeniedException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@Order(Ordered.HIGHEST_PRECEDENCE)
@RestControllerAdvice(assignableTypes = ArtifactsController.class)
public class ArtifactsExceptionHandler {

    @ExceptionHandler(TaskNotFoundException.class)
    public ResponseEntity<GatewayResponse> handleTaskNotFound(TaskNotFoundException ex) {
        return ResponseEntity.status(404).contentType(MediaType.APPLICATION_JSON).body(GatewayResponses.error(ex.getMessage()));
    }

    @ExceptionHandler(ArtifactNotFoundException.class)
    public ResponseEntity<GatewayResponse> handleArtifactNotFound(ArtifactNotFoundException ex) {
        return ResponseEntity.status(404).contentType(MediaType.APPLICATION_JSON).body(GatewayResponses.error(ex.getMessage()));
    }

    @ExceptionHandler(ArtifactForbiddenException.class)
    public ResponseEntity<GatewayResponse> handleForbidden(ArtifactForbiddenException ex) {
        return ResponseEntity.status(403).contentType(MediaType.APPLICATION_JSON).body(GatewayResponses.error(ex.getMessage()));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<GatewayResponse> handleIllegalArgument(IllegalArgumentException ex) {
        return ResponseEntity.badRequest().contentType(MediaType.APPLICATION_JSON).body(GatewayResponses.error(ex.getMessage()));
    }

    /**
     * Method-security failures for artifacts endpoints are surfaced as 404 to avoid leaking
     * whether a task/artifact exists to non-members.
     */
    @ExceptionHandler({AuthorizationDeniedException.class, AccessDeniedException.class})
    public ResponseEntity<GatewayResponse> handleAccessDenied(Exception ex) {
        return ResponseEntity.status(404).contentType(MediaType.APPLICATION_JSON).body(GatewayResponses.error("not found"));
    }
}

