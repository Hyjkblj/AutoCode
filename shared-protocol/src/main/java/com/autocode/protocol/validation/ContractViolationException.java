package com.autocode.protocol.validation;

/**
 * Thrown when a DTO violates the shared protocol contract.
 *
 * This module intentionally avoids heavy schema validation dependencies; validation is kept lightweight and
 * focuses on required fields and versioning invariants.
 */
public class ContractViolationException extends RuntimeException {
    public ContractViolationException(String message) {
        super(message);
    }
}

