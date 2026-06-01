package com.autocode.controlplane.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class EmailService {
    private static final Logger log = LoggerFactory.getLogger(EmailService.class);

    @Value("${mvp.auth.email.smtp-host:}")
    private String smtpHost;

    @Value("${mvp.auth.email.from-address:noreply@autocode.dev}")
    private String fromAddress;

    public void sendVerificationCode(String email, String code) {
        // In dev mode (no SMTP configured), just log
        if (smtpHost == null || smtpHost.isBlank()) {
            log.info("[DEV] Verification code for {}: {}", email, code);
            return;
        }
        // TODO: Implement SMTP sending with JavaMailSender
        log.info("Verification code for {}: {}", email, code);
    }
}
