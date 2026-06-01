package com.autocode.controlplane.api;

import com.autocode.controlplane.security.AuthProperties;
import com.autocode.controlplane.security.JwtAuthProperties;
import com.autocode.controlplane.security.OAuthProperties;
import com.autocode.controlplane.persistence.entity.EmailVerificationEntity;
import com.autocode.controlplane.persistence.entity.UserEntity;
import com.autocode.controlplane.persistence.repo.EmailVerificationRepository;
import com.autocode.controlplane.persistence.repo.UserEntityRepository;
import com.autocode.controlplane.persistence.repo.UserRoleEntityRepository;
import com.autocode.controlplane.service.EmailService;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.web.bind.annotation.*;

import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

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
    private static final Logger log = LoggerFactory.getLogger(AuthController.class);

    private final JwtEncoder jwtEncoder;
    private final JwtAuthProperties jwtProps;
    private final AuthProperties authProps;
    private final OAuthProperties oauthProps;
    private final UserEntityRepository userRepository;
    private final UserRoleEntityRepository userRoleRepository;
    private final EmailVerificationRepository emailVerificationRepository;
    private final PasswordEncoder passwordEncoder;
    private final EmailService emailService;
    private final HttpClient httpClient = HttpClient.newHttpClient();

    private static final long CODE_TTL_SECONDS = 300;       // 5 minutes
    private static final long RATE_LIMIT_SECONDS = 60;       // 60 seconds between sends
    private static final int MAX_VERIFY_ATTEMPTS = 5;
    private static final long LOCKOUT_SECONDS = 900;         // 15 minutes
    private static final SecureRandom SECURE_RANDOM = new SecureRandom();

    public AuthController(
            JwtEncoder jwtEncoder,
            JwtAuthProperties jwtProps,
            AuthProperties authProps,
            OAuthProperties oauthProps,
            UserEntityRepository userRepository,
            UserRoleEntityRepository userRoleRepository,
            EmailVerificationRepository emailVerificationRepository,
            PasswordEncoder passwordEncoder,
            EmailService emailService
    ) {
        this.jwtEncoder = jwtEncoder;
        this.jwtProps = jwtProps;
        this.authProps = authProps;
        this.oauthProps = oauthProps;
        this.userRepository = userRepository;
        this.userRoleRepository = userRoleRepository;
        this.emailVerificationRepository = emailVerificationRepository;
        this.passwordEncoder = passwordEncoder;
        this.emailService = emailService;
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
        String accessToken = generateAccessToken(user.getUsername(), roles, now);
        String refreshToken = generateRefreshToken();

        user.setRefreshToken(refreshToken);
        user.setRefreshTokenExpiresAt(now.plusSeconds(jwtProps.getRefreshTtlSeconds()));
        user.setLastLoginAt(now);
        userRepository.save(user);

        return ApiResponse.ok(Map.of(
                "accessToken", accessToken,
                "refreshToken", refreshToken,
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

    // ─── Email verification endpoints ───────────────────────────────────────

    @PostMapping("/email/send-code")
    public ApiResponse<Map<String, Object>> sendVerificationCode(@RequestBody Map<String, String> body) {
        String email = body.getOrDefault("email", "").trim();
        if (email.isEmpty()) {
            return ApiResponse.error("邮箱不能为空");
        }

        // Rate limit: 60 seconds between sends
        Instant since = Instant.now().minusSeconds(RATE_LIMIT_SECONDS);
        long recentCount = emailVerificationRepository.countByEmailAndPurposeAndCreatedAtAfter(email, "LOGIN", since);
        if (recentCount > 0) {
            return ApiResponse.error("请 60 秒后再试");
        }

        // Generate 6-digit code
        String code = String.format("%06d", SECURE_RANDOM.nextInt(1000000));

        EmailVerificationEntity verification = new EmailVerificationEntity();
        verification.setId(UUID.randomUUID().toString().replace("-", ""));
        verification.setEmail(email);
        verification.setCode(code);
        verification.setPurpose("LOGIN");
        verification.setExpiresAt(Instant.now().plusSeconds(CODE_TTL_SECONDS));
        emailVerificationRepository.save(verification);

        emailService.sendVerificationCode(email, code);

        return ApiResponse.ok(Map.of("message", "验证码已发送"));
    }

    @PostMapping("/email/verify")
    public ApiResponse<Map<String, Object>> verifyEmail(@RequestBody Map<String, String> body) {
        String email = body.getOrDefault("email", "").trim();
        String code = body.getOrDefault("code", "").trim();
        if (email.isEmpty() || code.isEmpty()) {
            return ApiResponse.error("邮箱和验证码不能为空");
        }

        // Rate limit on failed attempts: 5 failures in 15 minutes
        Instant lockoutSince = Instant.now().minusSeconds(LOCKOUT_SECONDS);
        long failedCount = emailVerificationRepository.countByEmailAndPurposeAndCreatedAtAfter(email, "LOGIN", lockoutSince);
        if (failedCount >= MAX_VERIFY_ATTEMPTS) {
            return ApiResponse.error("验证码错误次数过多，请 15 分钟后再试");
        }

        Optional<EmailVerificationEntity> verificationOpt =
                emailVerificationRepository.findTopByEmailAndPurposeAndUsedOrderByCreatedAtDesc(email, "LOGIN", false);
        if (verificationOpt.isEmpty()) {
            return ApiResponse.error("验证码无效或已过期");
        }

        EmailVerificationEntity verification = verificationOpt.get();
        if (verification.isUsed() || verification.getExpiresAt().isBefore(Instant.now())) {
            return ApiResponse.error("验证码无效或已过期");
        }
        if (!verification.getCode().equals(code)) {
            return ApiResponse.error("验证码错误");
        }

        // Mark as used
        verification.setUsed(true);
        emailVerificationRepository.save(verification);

        // Find or create user with auth_provider=EMAIL
        UserEntity user = userRepository.findByEmail(email).orElseGet(() -> {
            UserEntity newUser = new UserEntity();
            newUser.setUserId(UUID.randomUUID().toString().replace("-", ""));
            newUser.setUsername(email.split("@")[0] + "_" + UUID.randomUUID().toString().substring(0, 6));
            newUser.setPasswordHash(passwordEncoder.encode(UUID.randomUUID().toString()));
            newUser.setEmail(email);
            newUser.setEmailVerified(true);
            newUser.setAuthProvider("EMAIL");
            newUser.setEnabled(true);
            newUser.setCreatedAt(Instant.now());
            return userRepository.save(newUser);
        });

        if (!user.isEmailVerified()) {
            user.setEmailVerified(true);
            userRepository.save(user);
        }

        List<String> roles = userRoleRepository.findByUserId(user.getUserId()).stream()
                .map(r -> r.getRoleName())
                .distinct()
                .toList();
        if (roles.isEmpty()) {
            roles = List.of("VIEWER");
        }

        Instant now = Instant.now();
        String accessToken = generateAccessToken(user.getUsername(), roles, now);
        String refreshToken = generateRefreshToken();

        user.setRefreshToken(refreshToken);
        user.setRefreshTokenExpiresAt(now.plusSeconds(jwtProps.getRefreshTtlSeconds()));
        user.setLastLoginAt(now);
        userRepository.save(user);

        return ApiResponse.ok(Map.of(
                "accessToken", accessToken,
                "refreshToken", refreshToken,
                "expiresInSeconds", jwtProps.getAccessTtlSeconds(),
                "user", Map.of(
                        "userId", user.getUserId(),
                        "displayName", user.getUsername(),
                        "email", email,
                        "provider", user.getAuthProvider()
                )
        ));
    }

    // ─── Refresh token endpoints ────────────────────────────────────────────

    @PostMapping("/refresh")
    public ApiResponse<Map<String, Object>> refreshToken(@RequestBody Map<String, String> body) {
        String refreshToken = body.getOrDefault("refreshToken", "").trim();
        if (refreshToken.isEmpty()) {
            return ApiResponse.error("refreshToken 不能为空");
        }

        Optional<UserEntity> userOpt = userRepository.findByRefreshToken(refreshToken);
        if (userOpt.isEmpty()) {
            return ApiResponse.error("刷新 Token 无效或已过期");
        }

        UserEntity user = userOpt.get();
        if (user.getRefreshTokenExpiresAt() != null && user.getRefreshTokenExpiresAt().isBefore(Instant.now())) {
            return ApiResponse.error("刷新 Token 无效或已过期");
        }

        List<String> roles = userRoleRepository.findByUserId(user.getUserId()).stream()
                .map(r -> r.getRoleName())
                .distinct()
                .toList();
        if (roles.isEmpty()) {
            roles = List.of("VIEWER");
        }

        Instant now = Instant.now();
        String newAccessToken = generateAccessToken(user.getUsername(), roles, now);
        String newRefreshToken = generateRefreshToken();

        // Rotate refresh token
        user.setRefreshToken(newRefreshToken);
        user.setRefreshTokenExpiresAt(now.plusSeconds(jwtProps.getRefreshTtlSeconds()));
        userRepository.save(user);

        return ApiResponse.ok(Map.of(
                "accessToken", newAccessToken,
                "refreshToken", newRefreshToken,
                "expiresInSeconds", jwtProps.getAccessTtlSeconds()
        ));
    }

    @PostMapping("/logout")
    public ApiResponse<Map<String, Object>> logout(@RequestBody Map<String, String> body) {
        String refreshToken = body.getOrDefault("refreshToken", "").trim();
        if (refreshToken.isEmpty()) {
            return ApiResponse.error("refreshToken 不能为空");
        }

        Optional<UserEntity> userOpt = userRepository.findByRefreshToken(refreshToken);
        if (userOpt.isPresent()) {
            UserEntity user = userOpt.get();
            user.setRefreshToken(null);
            user.setRefreshTokenExpiresAt(null);
            userRepository.save(user);
        }

        return ApiResponse.ok(Map.of("message", "已注销"));
    }

    // ─── OAuth endpoints ────────────────────────────────────────────────────

    @GetMapping("/oauth/{provider}")
    public void initiateOAuth(@PathVariable String provider, HttpServletResponse response) throws IOException {
        OAuthProperties.Provider providerConfig = getOAuthProviderConfig(provider);
        if (providerConfig.getClientId().isEmpty()) {
            response.sendError(HttpServletResponse.SC_BAD_REQUEST, "OAuth provider not configured: " + provider);
            return;
        }

        String authUrl = switch (provider.toLowerCase()) {
            case "google" -> "https://accounts.google.com/o/oauth2/v2/auth"
                    + "?client_id=" + encode(providerConfig.getClientId())
                    + "&redirect_uri=" + encode(providerConfig.getRedirectUri())
                    + "&scope=" + encode("openid email profile")
                    + "&response_type=code"
                    + "&state=" + encode(generateState());
            case "github" -> "https://github.com/login/oauth/authorize"
                    + "?client_id=" + encode(providerConfig.getClientId())
                    + "&redirect_uri=" + encode(providerConfig.getRedirectUri())
                    + "&scope=" + encode("user:email")
                    + "&state=" + encode(generateState());
            default -> throw new IllegalArgumentException("Unknown provider: " + provider);
        };

        response.sendRedirect(authUrl);
    }

    @GetMapping("/oauth/{provider}/callback")
    public void handleOAuthCallback(
            @PathVariable String provider,
            @RequestParam String code,
            @RequestParam(required = false) String state,
            HttpServletResponse response) throws IOException {
        try {
            OAuthProperties.Provider providerConfig = getOAuthProviderConfig(provider);

            // Exchange code for access token
            String providerAccessToken = exchangeCodeForToken(provider, code, providerConfig);

            // Get user info from provider
            Map<String, String> userInfo = getProviderUserInfo(provider, providerAccessToken);

            String providerId = userInfo.get("id");
            String email = userInfo.get("email");
            String name = userInfo.get("name");
            String avatar = userInfo.get("avatar");

            // Find or create user
            UserEntity user = userRepository.findByAuthProviderAndOauthProviderId(provider.toUpperCase(), providerId)
                    .orElseGet(() -> {
                        UserEntity newUser = new UserEntity();
                        newUser.setUserId(UUID.randomUUID().toString().replace("-", ""));
                        newUser.setUsername(name != null && !name.isEmpty() ? name : providerId);
                        newUser.setPasswordHash(passwordEncoder.encode(UUID.randomUUID().toString()));
                        newUser.setEmail(email);
                        newUser.setEmailVerified(email != null && !email.isEmpty());
                        newUser.setAvatarUrl(avatar);
                        newUser.setAuthProvider(provider.toUpperCase());
                        newUser.setOauthProviderId(providerId);
                        newUser.setEnabled(true);
                        newUser.setCreatedAt(Instant.now());
                        return userRepository.save(newUser);
                    });

            List<String> roles = userRoleRepository.findByUserId(user.getUserId()).stream()
                    .map(r -> r.getRoleName())
                    .distinct()
                    .toList();
            if (roles.isEmpty()) {
                roles = List.of("VIEWER");
            }

            Instant now = Instant.now();
            String accessToken = generateAccessToken(user.getUsername(), roles, now);
            String refreshToken = generateRefreshToken();

            user.setRefreshToken(refreshToken);
            user.setRefreshTokenExpiresAt(now.plusSeconds(jwtProps.getRefreshTtlSeconds()));
            user.setLastLoginAt(now);
            userRepository.save(user);

            // Redirect to app deep link
            String deepLink = "com.autocode.mobile://callback"
                    + "?token=" + encode(accessToken)
                    + "&refreshToken=" + encode(refreshToken)
                    + "&name=" + encode(user.getUsername())
                    + "&email=" + encode(email != null ? email : "");
            response.sendRedirect(deepLink);

        } catch (Exception e) {
            log.error("OAuth callback error for provider {}: {}", provider, e.getMessage(), e);
            response.sendError(HttpServletResponse.SC_INTERNAL_SERVER_ERROR, "OAuth authentication failed");
        }
    }

    // ─── Helper methods ─────────────────────────────────────────────────────

    private String generateAccessToken(String subject, List<String> roles, Instant now) {
        JwtClaimsSet claims = JwtClaimsSet.builder()
                .subject(subject)
                .issuedAt(now)
                .expiresAt(now.plusSeconds(jwtProps.getAccessTtlSeconds()))
                .claim("roles", roles)
                .build();
        JwsHeader jwsHeader = JwsHeader.with(MacAlgorithm.HS256).build();
        return jwtEncoder.encode(JwtEncoderParameters.from(jwsHeader, claims)).getTokenValue();
    }

    private String generateRefreshToken() {
        byte[] bytes = new byte[32];
        SECURE_RANDOM.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    private String generateState() {
        return UUID.randomUUID().toString().replace("-", "");
    }

    private String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }

    private OAuthProperties.Provider getOAuthProviderConfig(String provider) {
        return switch (provider.toLowerCase()) {
            case "google" -> oauthProps.getGoogle();
            case "github" -> oauthProps.getGithub();
            default -> throw new IllegalArgumentException("Unknown provider: " + provider);
        };
    }

    private String exchangeCodeForToken(String provider, String code, OAuthProperties.Provider config) throws IOException {
        String tokenUrl = switch (provider.toLowerCase()) {
            case "google" -> "https://oauth2.googleapis.com/token";
            case "github" -> "https://github.com/login/oauth/access_token";
            default -> throw new IllegalArgumentException("Unknown provider: " + provider);
        };

        String form = "code=" + encode(code)
                + "&client_id=" + encode(config.getClientId())
                + "&client_secret=" + encode(config.getClientSecret())
                + "&redirect_uri=" + encode(config.getRedirectUri());

        if ("google".equals(provider.toLowerCase())) {
            form += "&grant_type=authorization_code";
        }

        HttpRequest httpRequest = HttpRequest.newBuilder()
                .uri(URI.create(tokenUrl))
                .header("Content-Type", "application/x-www-form-urlencoded")
                .header("Accept", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(form))
                .build();

        try {
            HttpResponse<String> resp = httpClient.send(httpRequest, HttpResponse.BodyHandlers.ofString());
            // Parse JSON response
            String responseBody = resp.body();
            // Simple JSON parsing for access_token field
            int start = responseBody.indexOf("\"access_token\":\"");
            if (start == -1) {
                throw new IOException("No access_token in response: " + responseBody);
            }
            start += "\"access_token\":\"".length();
            int end = responseBody.indexOf("\"", start);
            return responseBody.substring(start, end);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("Token exchange interrupted", e);
        }
    }

    private Map<String, String> getProviderUserInfo(String provider, String accessToken) throws IOException {
        String userInfoUrl = switch (provider.toLowerCase()) {
            case "google" -> "https://www.googleapis.com/oauth2/v2/userinfo";
            case "github" -> "https://api.github.com/user";
            default -> throw new IllegalArgumentException("Unknown provider: " + provider);
        };

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(userInfoUrl))
                .header("Authorization", "Bearer " + accessToken)
                .header("Accept", "application/json")
                .GET()
                .build();

        try {
            HttpResponse<String> resp = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            String body = resp.body();

            String id = extractJsonField(body, "id");
            String email = extractJsonField(body, "email");
            String name = extractJsonField(body, "name");
            String avatar = extractJsonField(body, provider.toLowerCase().equals("github") ? "avatar_url" : "picture");

            // GitHub may not return email in /user; fetch from /user/emails
            if ((email == null || email.isEmpty()) && "github".equals(provider.toLowerCase())) {
                email = fetchGitHubEmail(accessToken);
            }

            return Map.of(
                    "id", id != null ? id : "",
                    "email", email != null ? email : "",
                    "name", name != null ? name : "",
                    "avatar", avatar != null ? avatar : ""
            );
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("User info fetch interrupted", e);
        }
    }

    private String fetchGitHubEmail(String accessToken) throws IOException {
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create("https://api.github.com/user/emails"))
                .header("Authorization", "Bearer " + accessToken)
                .header("Accept", "application/json")
                .GET()
                .build();
        try {
            HttpResponse<String> resp = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            // Find primary email in JSON array
            String body = resp.body();
            // Simple extraction: look for "primary":true and get the preceding "email" field
            int primaryIdx = body.indexOf("\"primary\":true");
            if (primaryIdx == -1) {
                primaryIdx = body.indexOf("\"primary\": true");
            }
            if (primaryIdx > 0) {
                // Search backwards for "email"
                int emailIdx = body.lastIndexOf("\"email\":", primaryIdx);
                if (emailIdx > 0) {
                    int start = body.indexOf("\"", emailIdx + "\"email\":".length()) + 1;
                    int end = body.indexOf("\"", start);
                    return body.substring(start, end);
                }
            }
            return "";
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("GitHub email fetch interrupted", e);
        }
    }

    private String extractJsonField(String json, String field) {
        String search = "\"" + field + "\":\"";
        int start = json.indexOf(search);
        if (start == -1) {
            // Try with space after colon
            search = "\"" + field + "\": \"";
            start = json.indexOf(search);
            if (start == -1) return null;
        }
        start = json.indexOf("\"", start + search.length() - 1) + 1;
        int end = json.indexOf("\"", start);
        if (end == -1) return null;
        return json.substring(start, end);
    }
}
