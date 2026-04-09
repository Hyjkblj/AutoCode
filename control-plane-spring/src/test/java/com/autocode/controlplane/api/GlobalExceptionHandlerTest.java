package com.autocode.controlplane.api;

import org.junit.jupiter.api.Test;
import org.slf4j.MDC;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class GlobalExceptionHandlerTest {

    private final GlobalExceptionHandler handler = new GlobalExceptionHandler();

    @Test
    void handleUnknownShouldHideSensitiveMessageAndExposeTraceRequestId() {
        MDC.put("traceId", "trace-test-123");
        try {
            ResponseEntity<ApiResponse<Object>> response =
                    handler.handleUnknown(new RuntimeException("sensitive-db-password"));

            assertEquals(HttpStatus.INTERNAL_SERVER_ERROR, response.getStatusCode());
            assertEquals("internal error (requestId=trace-test-123)", response.getBody().getError());
            assertFalse(response.getBody().getError().contains("sensitive-db-password"));
        } finally {
            MDC.clear();
        }
    }

    @Test
    void handleUnknownShouldGenerateRequestIdWhenTraceMissing() {
        MDC.clear();
        ResponseEntity<ApiResponse<Object>> response =
                handler.handleUnknown(new RuntimeException("secret-token-value"));

        assertEquals(HttpStatus.INTERNAL_SERVER_ERROR, response.getStatusCode());
        assertTrue(response.getBody().getError().startsWith("internal error (requestId="));
        assertFalse(response.getBody().getError().contains("secret-token-value"));
    }
}
