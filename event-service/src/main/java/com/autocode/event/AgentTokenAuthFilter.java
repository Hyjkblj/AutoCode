package com.autocode.event;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.Arrays;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Lightweight token-based auth filter for event-service.
 * Validates X-Agent-Token or Authorization: Bearer on non-health endpoints.
 *
 * <p>This avoids pulling in spring-security as a dependency for a single-service auth check.</p>
 */
@Component
public class AgentTokenAuthFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(AgentTokenAuthFilter.class);

    private final Set<String> allowedTokens;
    private final boolean enabled;

    public AgentTokenAuthFilter(
            @Value("${event-service.auth.agent-tokens:agent-dev-token}") String agentTokens,
            @Value("${event-service.auth.enabled:true}") boolean enabled
    ) {
        this.enabled = enabled;
        this.allowedTokens = Arrays.stream(agentTokens.split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .collect(Collectors.toUnmodifiableSet());
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain
    ) throws ServletException, IOException {
        if (!enabled) {
            filterChain.doFilter(request, response);
            return;
        }

        // Allow health check without auth
        String path = request.getRequestURI();
        if (path.endsWith("/health") || path.endsWith("/actuator/health")) {
            filterChain.doFilter(request, response);
            return;
        }

        // Check X-Agent-Token header first
        String token = request.getHeader("X-Agent-Token");

        // Fall back to Authorization: Bearer
        if (token == null || token.isBlank()) {
            String authHeader = request.getHeader("Authorization");
            if (authHeader != null && authHeader.startsWith("Bearer ")) {
                token = authHeader.substring(7).trim();
            }
        }

        if (token == null || token.isBlank()) {
            log.warn("Rejected {} {} — missing agent token", request.getMethod(), path);
            response.setStatus(HttpStatus.UNAUTHORIZED.value());
            response.setContentType("application/json");
            response.getWriter().write("{\"ok\":false,\"error\":\"missing agent token\"}");
            return;
        }

        if (!allowedTokens.contains(token)) {
            log.warn("Rejected {} {} — invalid agent token", request.getMethod(), path);
            response.setStatus(HttpStatus.FORBIDDEN.value());
            response.setContentType("application/json");
            response.getWriter().write("{\"ok\":false,\"error\":\"invalid agent token\"}");
            return;
        }

        filterChain.doFilter(request, response);
    }
}
