/**
 * Simple token auth filter for separating operator vs agent API calls.
 */
package com.autocode.controlplane.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.HttpStatus;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;

@Component
@ConditionalOnProperty(prefix = "mvp.auth", name = "mode", havingValue = "token", matchIfMissing = true)
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

        if (isHostedArtifactSiteRequest(path, request.getMethod())) {
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
            // Best-effort identity wiring so method-security (@PreAuthorize) can work in token mode.
            // The token mode is intentionally minimal; we only distinguish agent vs operator roles.
            SecurityContextHolder.getContext().setAuthentication(new UsernamePasswordAuthenticationToken(
                    "agent",
                    token,
                    List.of(new SimpleGrantedAuthority("ROLE_AGENT"))
            ));
            filterChain.doFilter(request, response);
            return;
        }

        // B-stage artifact upload is performed by runner (agent) but lives under /api/v1/tasks/* per API plan.
        // We allow either operator bearer token OR agent token for this endpoint only.
        if (path.matches("^/api/v1/tasks/[^/]+/artifacts/?$") && "POST".equalsIgnoreCase(request.getMethod())) {
            String authHeader = request.getHeader("Authorization");
            if (isAllowedOperatorAuthHeader(authHeader)) {
                SecurityContextHolder.getContext().setAuthentication(new UsernamePasswordAuthenticationToken(
                        "operator",
                        authHeader,
                        List.of(new SimpleGrantedAuthority("ROLE_OPERATOR"))
                ));
                filterChain.doFilter(request, response);
                return;
            }
            String agentToken = request.getHeader("X-Agent-Token");
            if (isAllowedAgentToken(agentToken)) {
                SecurityContextHolder.getContext().setAuthentication(new UsernamePasswordAuthenticationToken(
                        "agent",
                        agentToken,
                        List.of(new SimpleGrantedAuthority("ROLE_AGENT"))
                ));
                filterChain.doFilter(request, response);
                return;
            }
            response.setStatus(HttpStatus.UNAUTHORIZED.value());
            response.getWriter().write("{\"ok\":false,\"error\":\"invalid token\"}");
            return;
        }

        String authHeader = request.getHeader("Authorization");
        if (!isAllowedOperatorAuthHeader(authHeader)) {
            response.setStatus(HttpStatus.UNAUTHORIZED.value());
            response.getWriter().write("{\"ok\":false,\"error\":\"invalid operator token\"}");
            return;
        }
        SecurityContextHolder.getContext().setAuthentication(new UsernamePasswordAuthenticationToken(
                "operator",
                authHeader,
                List.of(new SimpleGrantedAuthority("ROLE_OPERATOR"))
        ));
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

    private boolean isHostedArtifactSiteRequest(String path, String method) {
        if (!"GET".equalsIgnoreCase(method)) {
            return false;
        }
        return path.matches("^/api/v1/tasks/[^/]+/artifacts/[^/]+/site(?:/.*)?$");
    }
}
