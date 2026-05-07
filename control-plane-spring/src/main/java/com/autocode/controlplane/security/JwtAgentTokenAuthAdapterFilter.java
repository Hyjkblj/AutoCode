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
 * <p>This keeps Python/Java agent traffic working without forcing the agent to mint JWT itself.
 * The adapter reads {@code X-Agent-Token} from the request header, validates it against
 * {@link AuthProperties#agentTokenList()}, and sets {@code ROLE_AGENT} authentication
 * if no JWT-based authentication is already present.</p>
 *
 * <h3>Deprecation plan</h3>
 * <p>This adapter is a <strong>temporary compatibility bridge</strong>. The target state is:</p>
 * <ol>
 *   <li>Agents obtain short-lived JWT via {@code POST /api/v1/auth/agent/token} (to be added)</li>
 *   <li>Agents send {@code Authorization: Bearer <jwt>} instead of {@code X-Agent-Token}</li>
 *   <li>This filter and the static agent token config are removed</li>
 * </ol>
 * <p>Until the agent JWT endpoint exists, this filter remains the supported path for agent auth.</p>
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

