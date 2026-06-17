package com.autocode.controlplane.api;

import com.autocode.controlplane.security.AuthProperties;
import com.autocode.controlplane.security.JwtAuthProperties;
import com.autocode.controlplane.security.OAuthProperties;
import com.autocode.controlplane.persistence.entity.UserEntity;
import com.autocode.controlplane.persistence.entity.UserRoleEntity;
import com.autocode.controlplane.persistence.repo.UserEntityRepository;
import com.autocode.controlplane.persistence.repo.UserRoleEntityRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.web.bind.annotation.*;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.security.crypto.password.PasswordEncoder;

/**
 * MVP auth endpoints for JWT mode.
 *
 * In production, replace with enterprise IdP integration.
 */
@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {
    private static final Logger log = LoggerFactory.getLogger(AuthController.class);

    private final JwtEncoder jwtEncoder;
    private final JwtAuthProperties jwtProps;
    private final AuthProperties authProps;
    private final OAuthProperties oauthProps;
    private final UserEntityRepository userRepository;
    private final UserRoleEntityRepository userRoleRepository;
    private final PasswordEncoder passwordEncoder;
    private final HttpClient httpClient = HttpClient.newHttpClient();

    // state -> pending OAuth result (JWT token)
    private final ConcurrentHashMap<String, OAuthPendingResult> oauthPendingResults = new ConcurrentHashMap<>();

    public AuthController(
            JwtEncoder jwtEncoder,
            JwtAuthProperties jwtProps,
            AuthProperties authProps,
            OAuthProperties oauthProps,
            UserEntityRepository userRepository,
            UserRoleEntityRepository userRoleRepository,
            PasswordEncoder passwordEncoder
    ) {
        this.jwtEncoder = jwtEncoder;
        this.jwtProps = jwtProps;
        this.authProps = authProps;
        this.oauthProps = oauthProps;
        this.userRepository = userRepository;
        this.userRoleRepository = userRoleRepository;
        this.passwordEncoder = passwordEncoder;
    }

    private record OAuthPendingResult(String jwtToken, Instant expiresAt) {}

    public record LoginRequest(String username, String password) {
    }

    public record RegisterRequest(String username, String password, String email) {
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

    @PostMapping("/register")
    public ApiResponse<Map<String, Object>> register(@RequestBody RegisterRequest request) {
        if (request == null || request.username() == null || request.password() == null) {
            return ApiResponse.error("username and password are required");
        }

        String username = request.username().trim();
        String password = request.password();
        String email = request.email() != null ? request.email().trim() : null;

        if (username.isEmpty() || username.length() < 3 || username.length() > 64) {
            return ApiResponse.error("username must be 3-64 characters");
        }
        if (password.length() < 6) {
            return ApiResponse.error("password must be at least 6 characters");
        }
        if (email != null && !email.isEmpty() && !email.matches("^[\\w.-]+@[\\w.-]+\\.[a-zA-Z]{2,}$")) {
            return ApiResponse.error("invalid email format");
        }

        if (userRepository.findByUsername(username).isPresent()) {
            return ApiResponse.error("username already exists");
        }
        if (email != null && !email.isEmpty() && userRepository.findByEmail(email).isPresent()) {
            return ApiResponse.error("email already registered");
        }

        UserEntity user = new UserEntity();
        user.setUserId(UUID.randomUUID().toString());
        user.setUsername(username);
        user.setPasswordHash(passwordEncoder.encode(password));
        user.setEmail(email);
        user.setEmailVerified(false);
        user.setAuthProvider("LOCAL");
        user.setEnabled(true);
        user.setCreatedAt(Instant.now());
        userRepository.save(user);

        UserRoleEntity role = new UserRoleEntity();
        role.setUserId(user.getUserId());
        role.setRoleName("VIEWER");
        userRoleRepository.save(role);

        Instant now = Instant.now();
        List<String> roles = List.of("VIEWER");
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
                "expiresInSeconds", jwtProps.getAccessTtlSeconds(),
                "displayName", user.getUsername()
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

    // ── OAuth endpoints ───────────────────────────────────────────────

    /**
     * Step 1: Mobile app calls this to get the OAuth authorization URL.
     * The user is redirected to Google/GitHub to authenticate.
     */
    @GetMapping("/oauth/{provider}/authorize")
    public ApiResponse<Map<String, String>> oauthAuthorize(@PathVariable String provider) {
        OAuthProperties.Provider providerConfig;
        String authUrl;
        String state = UUID.randomUUID().toString();

        switch (provider.toLowerCase()) {
            case "google" -> {
                providerConfig = oauthProps.getGoogle();
                if (providerConfig.getClientId().isBlank()) {
                    return ApiResponse.error("Google OAuth not configured");
                }
                authUrl = "https://accounts.google.com/o/oauth2/v2/auth"
                        + "?client_id=" + encode(providerConfig.getClientId())
                        + "&redirect_uri=" + encode(providerConfig.getRedirectUri())
                        + "&response_type=code"
                        + "&scope=" + encode("openid email profile")
                        + "&state=" + encode(state);
            }
            case "github" -> {
                providerConfig = oauthProps.getGithub();
                if (providerConfig.getClientId().isBlank()) {
                    return ApiResponse.error("GitHub OAuth not configured");
                }
                authUrl = "https://github.com/login/oauth/authorize"
                        + "?client_id=" + encode(providerConfig.getClientId())
                        + "&redirect_uri=" + encode(providerConfig.getRedirectUri())
                        + "&scope=" + encode("user:email")
                        + "&state=" + encode(state);
            }
            default -> {
                return ApiResponse.error("unsupported provider: " + provider);
            }
        }

        // Store state for later verification (expires in 10 minutes)
        oauthPendingResults.put(state, new OAuthPendingResult("", Instant.now().plusSeconds(600)));

        return ApiResponse.ok(Map.of(
                "authorizationUrl", authUrl,
                "state", state
        ));
    }

    /**
     * Step 2: Backend callback from Google/GitHub.
     * Exchanges the authorization code for tokens and creates/links the user.
     * Stores the resulting JWT so the mobile app can poll for it.
     */
    @GetMapping("/oauth/{provider}/callback")
    public Map<String, Object> oauthCallback(
            @PathVariable String provider,
            @RequestParam(required = false) String code,
            @RequestParam(required = false) String state,
            @RequestParam(required = false) String error
    ) {
        // Redirect page that tells the mobile app the auth is complete
        String redirectHtml = """
                <!DOCTYPE html>
                <html><head><meta charset="utf-8"><title>登录成功</title></head>
                <body style="display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif;background:#0d0d0d;color:#fff;">
                <div style="text-align:center;">
                    <h1 style="color:#FFB800;">✓ 认证成功</h1>
                    <p>请返回应用继续操作。</p>
                    <script>
                        // Try to communicate with the app via custom URL scheme
                        if (window.opener) { window.close(); }
                    </script>
                </div>
                </body></html>
                """;

        if (error != null) {
            return Map.of("error", error, "html", errorHtml("认证失败: " + error));
        }
        if (code == null || state == null) {
            return Map.of("error", "missing code or state", "html", errorHtml("缺少授权码"));
        }

        OAuthPendingResult pending = oauthPendingResults.remove(state);
        if (pending == null) {
            return Map.of("error", "invalid or expired state", "html", errorHtml("无效或已过期的认证状态"));
        }

        try {
            String accessToken = exchangeCodeForToken(provider, code);
            OAuthUserInfo userInfo = fetchUserInfo(provider, accessToken);
            UserEntity user = findOrCreateUser(provider, userInfo);

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
            String jwt = jwtEncoder.encode(JwtEncoderParameters.from(jwsHeader, claims)).getTokenValue();

            // Store JWT for mobile app to poll
            oauthPendingResults.put(state, new OAuthPendingResult(jwt, Instant.now().plusSeconds(300)));

            return Map.of("success", true, "html", redirectHtml);
        } catch (Exception e) {
            log.error("OAuth callback error for provider={}", provider, e);
            return Map.of("error", e.getMessage(), "html", errorHtml("认证处理失败: " + e.getMessage()));
        }
    }

    /**
     * Step 3: Mobile app polls this endpoint to get the JWT after OAuth completes.
     */
    @GetMapping("/oauth/{provider}/poll/{state}")
    public ApiResponse<Map<String, Object>> oauthPoll(@PathVariable String provider, @PathVariable String state) {
        OAuthPendingResult pending = oauthPendingResults.get(state);
        if (pending == null) {
            return ApiResponse.error("invalid or expired state");
        }
        if (pending.jwtToken().isEmpty()) {
            return ApiResponse.error("authentication_pending");
        }
        if (pending.expiresAt().isBefore(Instant.now())) {
            oauthPendingResults.remove(state);
            return ApiResponse.error("state expired");
        }
        // Clean up after successful retrieval
        oauthPendingResults.remove(state);
        return ApiResponse.ok(Map.of(
                "accessToken", pending.jwtToken(),
                "tokenType", "Bearer"
        ));
    }

    private String exchangeCodeForToken(String provider, String code) throws Exception {
        return switch (provider.toLowerCase()) {
            case "google" -> exchangeGoogleCode(code);
            case "github" -> exchangeGithubCode(code);
            default -> throw new IllegalArgumentException("unsupported provider: " + provider);
        };
    }

    private String exchangeGoogleCode(String code) throws Exception {
        OAuthProperties.Provider cfg = oauthProps.getGoogle();
        String body = "code=" + encode(code)
                + "&client_id=" + encode(cfg.getClientId())
                + "&client_secret=" + encode(cfg.getClientSecret())
                + "&redirect_uri=" + encode(cfg.getRedirectUri())
                + "&grant_type=authorization_code";

        HttpRequest req = HttpRequest.newBuilder()
                .uri(URI.create("https://oauth2.googleapis.com/token"))
                .header("Content-Type", "application/x-www-form-urlencoded")
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();
        HttpResponse<String> resp = httpClient.send(req, HttpResponse.BodyHandlers.ofString());
        if (resp.statusCode() != 200) {
            throw new RuntimeException("Google token exchange failed: " + resp.body());
        }
        // Extract access_token from JSON response
        String responseBody = resp.body();
        int start = responseBody.indexOf("\"access_token\":\"") + 16;
        int end = responseBody.indexOf("\"", start);
        return responseBody.substring(start, end);
    }

    private String exchangeGithubCode(String code) throws Exception {
        OAuthProperties.Provider cfg = oauthProps.getGithub();
        String body = "{\"code\":\"" + code
                + "\",\"client_id\":\"" + cfg.getClientId()
                + "\",\"client_secret\":\"" + cfg.getClientSecret() + "\"}";

        HttpRequest req = HttpRequest.newBuilder()
                .uri(URI.create("https://github.com/login/oauth/access_token"))
                .header("Content-Type", "application/json")
                .header("Accept", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();
        HttpResponse<String> resp = httpClient.send(req, HttpResponse.BodyHandlers.ofString());
        if (resp.statusCode() != 200) {
            throw new RuntimeException("GitHub token exchange failed: " + resp.body());
        }
        String responseBody = resp.body();
        int start = responseBody.indexOf("\"access_token\":\"") + 16;
        int end = responseBody.indexOf("\"", start);
        return responseBody.substring(start, end);
    }

    private OAuthUserInfo fetchUserInfo(String provider, String accessToken) throws Exception {
        return switch (provider.toLowerCase()) {
            case "google" -> fetchGoogleUserInfo(accessToken);
            case "github" -> fetchGithubUserInfo(accessToken);
            default -> throw new IllegalArgumentException("unsupported provider: " + provider);
        };
    }

    private OAuthUserInfo fetchGoogleUserInfo(String accessToken) throws Exception {
        HttpRequest req = HttpRequest.newBuilder()
                .uri(URI.create("https://www.googleapis.com/oauth2/v2/userinfo"))
                .header("Authorization", "Bearer " + accessToken)
                .GET()
                .build();
        HttpResponse<String> resp = httpClient.send(req, HttpResponse.BodyHandlers.ofString());
        String body = resp.body();
        String id = extractJsonString(body, "id");
        String email = extractJsonString(body, "email");
        String name = extractJsonString(body, "name");
        String picture = extractJsonString(body, "picture");
        return new OAuthUserInfo(id, email, name, picture);
    }

    private OAuthUserInfo fetchGithubUserInfo(String accessToken) throws Exception {
        HttpRequest req = HttpRequest.newBuilder()
                .uri(URI.create("https://api.github.com/user"))
                .header("Authorization", "Bearer " + accessToken)
                .header("Accept", "application/json")
                .GET()
                .build();
        HttpResponse<String> resp = httpClient.send(req, HttpResponse.BodyHandlers.ofString());
        String body = resp.body();
        String id = String.valueOf(extractJsonLong(body, "id"));
        String login = extractJsonString(body, "login");
        String email = extractJsonString(body, "email");
        String avatarUrl = extractJsonString(body, "avatar_url");

        // GitHub may not return email in /user; try /user/emails
        if (email == null || email.isBlank()) {
            HttpRequest emailReq = HttpRequest.newBuilder()
                    .uri(URI.create("https://api.github.com/user/emails"))
                    .header("Authorization", "Bearer " + accessToken)
                    .header("Accept", "application/json")
                    .GET()
                    .build();
            HttpResponse<String> emailResp = httpClient.send(emailReq, HttpResponse.BodyHandlers.ofString());
            email = extractPrimaryEmail(emailResp.body());
        }

        return new OAuthUserInfo(id, email, login, avatarUrl);
    }

    private record OAuthUserInfo(String providerId, String email, String displayName, String avatarUrl) {}

    private UserEntity findOrCreateUser(String provider, OAuthUserInfo info) {
        String providerKey = provider.toUpperCase();
        Optional<UserEntity> existing = userRepository.findByAuthProviderAndOauthProviderId(providerKey, info.providerId());
        if (existing.isPresent()) {
            return existing.get();
        }

        // Try to find by email
        if (info.email() != null && !info.email().isBlank()) {
            Optional<UserEntity> byEmail = userRepository.findByEmail(info.email());
            if (byEmail.isPresent()) {
                UserEntity user = byEmail.get();
                user.setAuthProvider(providerKey);
                user.setOauthProviderId(info.providerId());
                userRepository.save(user);
                return user;
            }
        }

        // Create new user
        String providerId = info.providerId();
        String username = info.displayName() != null && !info.displayName().isBlank()
                ? info.displayName() : providerKey.toLowerCase() + "_" + providerId.substring(Math.max(0, providerId.length() - 8));

        // Ensure username uniqueness
        String baseUsername = username;
        int counter = 1;
        while (userRepository.findByUsername(username).isPresent()) {
            username = baseUsername + "_" + counter++;
        }

        UserEntity user = new UserEntity();
        user.setUserId(UUID.randomUUID().toString());
        user.setUsername(username);
        user.setPasswordHash(passwordEncoder.encode(UUID.randomUUID().toString()));
        user.setEmail(info.email());
        user.setEmailVerified(true);
        user.setAvatarUrl(info.avatarUrl());
        user.setAuthProvider(providerKey);
        user.setOauthProviderId(info.providerId());
        user.setEnabled(true);
        user.setCreatedAt(Instant.now());
        userRepository.save(user);

        UserRoleEntity role = new UserRoleEntity();
        role.setUserId(user.getUserId());
        role.setRoleName("VIEWER");
        userRoleRepository.save(role);

        return user;
    }

    private static String extractJsonString(String json, String key) {
        String search = "\"" + key + "\":";
        int start = json.indexOf(search);
        if (start < 0) return null;
        start += search.length();
        // Skip whitespace
        while (start < json.length() && json.charAt(start) == ' ') start++;
        if (start >= json.length()) return null;
        if (json.charAt(start) == '"') {
            start++;
            int end = json.indexOf('"', start);
            if (end < 0) return null;
            return json.substring(start, end);
        }
        // null
        if (json.startsWith("null", start)) return null;
        int end = start;
        while (end < json.length() && json.charAt(end) != ',' && json.charAt(end) != '}' && json.charAt(end) != ']') end++;
        return json.substring(start, end).trim();
    }

    private static long extractJsonLong(String json, String key) {
        String val = extractJsonString(json, key);
        if (val == null) return 0;
        return Long.parseLong(val.replaceAll("[^0-9-]", ""));
    }

    private static String extractPrimaryEmail(String emailsJson) {
        // Simple extraction: find "primary":true entry
        int primaryIdx = emailsJson.indexOf("\"primary\":true");
        if (primaryIdx < 0) {
            // Just get first email
            int emailIdx = emailsJson.indexOf("\"email\":\"");
            if (emailIdx < 0) return null;
            int start = emailIdx + 9;
            int end = emailsJson.indexOf('"', start);
            return emailsJson.substring(start, end);
        }
        // Walk backwards to find the "email" key in the same object
        int searchStart = emailsJson.lastIndexOf("{", primaryIdx);
        String segment = emailsJson.substring(searchStart, emailsJson.indexOf("}", primaryIdx) + 1);
        return extractJsonString(segment, "email");
    }

    private static String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }

    private static String errorHtml(String message) {
        return """
                <!DOCTYPE html>
                <html><head><meta charset="utf-8"><title>认证失败</title></head>
                <body style="display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif;background:#0d0d0d;color:#fff;">
                <div style="text-align:center;">
                    <h1 style="color:#F44336;">✗ %s</h1>
                    <p>请返回应用重试。</p>
                </div>
                </body></html>
                """.formatted(message);
    }
}

