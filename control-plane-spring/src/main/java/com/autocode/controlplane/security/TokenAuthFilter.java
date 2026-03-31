/**
 * Simple token auth filter for separating operator vs agent API calls.
 */
package com.autocode.controlplane.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

@Component
public class TokenAuthFilter extends OncePerRequestFilter {
    private final AuthProperties authProperties;

    public TokenAuthFilter(AuthProperties authProperties) {
        this.authProperties = authProperties;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        String path = request.getRequestURI();
        if (!path.startsWith("/api/v1")) {
            filterChain.doFilter(request, response);
            return;
        }

        if (path.startsWith("/api/v1/agent")) {
            String token = request.getHeader("X-Agent-Token");
            if (!isAllowedAgentToken(token)) {
                response.setStatus(HttpStatus.UNAUTHORIZED.value());
                response.getWriter().write("{\"ok\":false,\"error\":\"invalid agent token\"}");
                return;
            }
            filterChain.doFilter(request, response);
            return;
        }

        String authHeader = request.getHeader("Authorization");
        if (!isAllowedOperatorAuthHeader(authHeader)) {
            response.setStatus(HttpStatus.UNAUTHORIZED.value());
            response.getWriter().write("{\"ok\":false,\"error\":\"invalid operator token\"}");
            return;
        }
        filterChain.doFilter(request, response);
    }

    private boolean isAllowedAgentToken(String token) {
        if (token == null || token.isBlank()) {
            return false;
        }
        if (authProperties.revokedTokenList().contains(token)) {
            return false;
        }
        return authProperties.agentTokenList().contains(token);
    }

    private boolean isAllowedOperatorAuthHeader(String authHeader) {
        if (authHeader == null || authHeader.isBlank()) {
            return false;
        }
        if (!authHeader.startsWith("Bearer ")) {
            return false;
        }
        String token = authHeader.substring("Bearer ".length());
        if (authProperties.revokedTokenList().contains(token)) {
            return false;
        }
        return authProperties.operatorTokenList().contains(token);
    }
}
