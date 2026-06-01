package com.autocode.controlplane.api;

import com.autocode.controlplane.security.AuthProperties;
import com.autocode.controlplane.security.JwtAuthProperties;
import com.autocode.controlplane.persistence.entity.UserEntity;
import com.autocode.controlplane.persistence.repo.UserEntityRepository;
import com.autocode.controlplane.persistence.repo.UserRoleEntityRepository;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import org.springframework.security.crypto.password.PasswordEncoder;

/**
 * MVP auth endpoints for JWT mode.
 *
 * In production, replace with enterprise IdP integration.
 */
@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {
    private final JwtEncoder jwtEncoder;
    private final JwtAuthProperties jwtProps;
    private final AuthProperties authProps;
    private final UserEntityRepository userRepository;
    private final UserRoleEntityRepository userRoleRepository;
    private final PasswordEncoder passwordEncoder;

    public AuthController(
            JwtEncoder jwtEncoder,
            JwtAuthProperties jwtProps,
            AuthProperties authProps,
            UserEntityRepository userRepository,
            UserRoleEntityRepository userRoleRepository,
            PasswordEncoder passwordEncoder
    ) {
        this.jwtEncoder = jwtEncoder;
        this.jwtProps = jwtProps;
        this.authProps = authProps;
        this.userRepository = userRepository;
        this.userRoleRepository = userRoleRepository;
        this.passwordEncoder = passwordEncoder;
    }

    public record LoginRequest(String username, String password) {
    }

    @PostMapping("/login")
    public ApiResponse<Map<String, Object>> login(@RequestBody LoginRequest request) {
        if (request == null || request.username() == null || request.password() == null) {
            return ApiResponse.error("invalid login request");
        }
        Optional<UserEntity> userOpt = userRepository.findByUsername(request.username().trim());
        if (userOpt.isEmpty()) {
            return ApiResponse.error("invalid credentials");
        }
        UserEntity user = userOpt.get();
        if (!user.isEnabled()) {
            return ApiResponse.error("user disabled");
        }
        if (!passwordEncoder.matches(request.password(), user.getPasswordHash())) {
            return ApiResponse.error("invalid credentials");
        }

        List<String> roles = userRoleRepository.findByUserId(user.getUserId()).stream()
                .map(r -> r.getRoleName())
                .distinct()
                .toList();
        if (roles.isEmpty()) {
            roles = List.of("VIEWER");
        }

        Instant now = Instant.now();
        JwtClaimsSet claims = JwtClaimsSet.builder()
                .subject(user.getUsername())
                .issuedAt(now)
                .expiresAt(now.plusSeconds(jwtProps.getAccessTtlSeconds()))
                .claim("roles", roles)
                .build();
        JwsHeader jwsHeader = JwsHeader.with(MacAlgorithm.HS256).build();
        String token = jwtEncoder.encode(JwtEncoderParameters.from(jwsHeader, claims)).getTokenValue();
        return ApiResponse.ok(Map.of(
                "accessToken", token,
                "tokenType", "Bearer",
                "expiresInSeconds", jwtProps.getAccessTtlSeconds()
        ));
    }

    /**
     * Issue a short-lived JWT for an agent, authenticated by static X-Agent-Token.
     *
     * <p>This endpoint enables agents to transition from static token auth to JWT.
     * The agent presents its static token and receives a short-lived JWT with ROLE_AGENT.</p>
     *
     * <p>Once all agents use this endpoint, {@link JwtAgentTokenAuthAdapterFilter} and
     * the static agent token config can be removed.</p>
     */
    public record AgentTokenRequest(String agentToken) {
    }

    @PostMapping("/agent/token")
    public ApiResponse<Map<String, Object>> agentToken(@RequestBody AgentTokenRequest request) {
        if (request == null || request.agentToken() == null || request.agentToken().isBlank()) {
            return ApiResponse.error("agentToken is required");
        }

        String token = request.agentToken().trim();
        if (authProps.revokedTokenList().contains(token)) {
            return ApiResponse.error("agent token revoked");
        }
        if (!authProps.agentTokenList().contains(token)) {
            return ApiResponse.error("invalid agent token");
        }

        Instant now = Instant.now();
        long ttlSeconds = Math.min(jwtProps.getAccessTtlSeconds(), 3600);
        JwtClaimsSet claims = JwtClaimsSet.builder()
                .subject("agent")
                .issuedAt(now)
                .expiresAt(now.plusSeconds(ttlSeconds))
                .claim("roles", List.of("AGENT"))
                .claim("tokenType", "agent")
                .build();
        JwsHeader jwsHeader = JwsHeader.with(MacAlgorithm.HS256).build();
        String jwt = jwtEncoder.encode(JwtEncoderParameters.from(jwsHeader, claims)).getTokenValue();
        return ApiResponse.ok(Map.of(
                "accessToken", jwt,
                "tokenType", "Bearer",
                "expiresInSeconds", ttlSeconds
        ));
    }
}

