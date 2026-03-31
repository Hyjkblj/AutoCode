package com.autocode.controlplane.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpStatus;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.security.cert.X509Certificate;

/**
 * Application-layer mTLS enforcement for agent endpoints.
 *
 * Why: Boot-level client-auth=need forces all callers (including operators/UI) to present a cert.
 * Here we enforce mTLS only for /api/v1/agent/** when enabled.
 */
public class AgentMtlsEnforcementFilter extends OncePerRequestFilter {
    private final MtlsProperties props;

    public AgentMtlsEnforcementFilter(MtlsProperties props) {
        this.props = props;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        if (!props.isRequiredForAgent()) {
            filterChain.doFilter(request, response);
            return;
        }
        String path = request.getRequestURI();
        if (path == null || !path.startsWith("/api/v1/agent/")) {
            filterChain.doFilter(request, response);
            return;
        }
        Object attr = request.getAttribute("jakarta.servlet.request.X509Certificate");
        X509Certificate[] chain = (attr instanceof X509Certificate[]) ? (X509Certificate[]) attr : null;
        if (chain == null || chain.length == 0) {
            response.setStatus(HttpStatus.UNAUTHORIZED.value());
            response.getWriter().write("{\"ok\":false,\"error\":\"mtls required for agent\"}");
            return;
        }
        filterChain.doFilter(request, response);
    }
}

