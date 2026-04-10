package com.autocode.controlplane.api;

import com.autocode.controlplane.security.JwtAuthProperties;
import com.autocode.controlplane.persistence.entity.UserEntity;
import com.autocode.controlplane.persistence.repo.UserEntityRepository;
import com.autocode.controlplane.persistence.repo.UserRoleEntityRepository;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
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
@ConditionalOnProperty(prefix = "mvp.auth", name = "mode", havingValue = "jwt")
public class AuthController {
    private final JwtEncoder jwtEncoder;
    private final JwtAuthProperties props;
    private final UserEntityRepository userRepository;
    private final UserRoleEntityRepository userRoleRepository;
    private final PasswordEncoder passwordEncoder;

    public AuthController(
            JwtEncoder jwtEncoder,
            JwtAuthProperties props,
            UserEntityRepository userRepository,
            UserRoleEntityRepository userRoleRepository,
            PasswordEncoder passwordEncoder
    ) {
        this.jwtEncoder = jwtEncoder;
        this.props = props;
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
                .expiresAt(now.plusSeconds(props.getAccessTtlSeconds()))
                .claim("roles", roles)
                .build();
        JwsHeader jwsHeader = JwsHeader.with(MacAlgorithm.HS256).build();
        String token = jwtEncoder.encode(JwtEncoderParameters.from(jwsHeader, claims)).getTokenValue();
        return ApiResponse.ok(Map.of(
                "accessToken", token,
                "tokenType", "Bearer",
                "expiresInSeconds", props.getAccessTtlSeconds()
        ));
    }
}

