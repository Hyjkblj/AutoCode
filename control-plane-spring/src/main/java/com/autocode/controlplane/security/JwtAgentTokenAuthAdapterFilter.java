package com.autocode.controlplane.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;

/**
 * In JWT mode, adapts legacy X-Agent-Token calls to an authenticated ROLE_AGENT context.
 *
 * This keeps Python agent traffic working without forcing the agent to mint JWT itself.
 */
@Component
@ConditionalOnProperty(prefix = "mvp.auth", name = "mode", havingValue = "jwt")
public class JwtAgentTokenAuthAdapterFilter extends OncePerRequestFilter {

    private final AuthProperties authProperties;

    public JwtAgentTokenAuthAdapterFilter(AuthProperties authProperties) {
        this.authProperties = authProperties;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        if (supportsPath(request)
                && SecurityContextHolder.getContext().getAuthentication() == null) {
            String token = request.getHeader("X-Agent-Token");
            if (isAllowedAgentToken(token)) {
                SecurityContextHolder.getContext().setAuthentication(
                        new UsernamePasswordAuthenticationToken(
                                "agent",
                                token,
                                List.of(new SimpleGrantedAuthority("ROLE_AGENT"))
                        )
                );
            }
        }
        filterChain.doFilter(request, response);
    }

    private boolean supportsPath(HttpServletRequest request) {
        String path = request.getRequestURI();
        if (path == null || path.isBlank()) {
            return false;
        }
        if (path.startsWith("/api/v1/agent")) {
            return true;
        }
        return "POST".equalsIgnoreCase(request.getMethod())
                && path.matches("^/api/v1/tasks/[^/]+/artifacts/?$");
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
}

