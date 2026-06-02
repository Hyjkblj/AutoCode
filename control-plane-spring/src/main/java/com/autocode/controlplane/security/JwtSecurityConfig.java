package com.autocode.controlplane.security;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwtValidators;
import org.springframework.security.oauth2.jwt.JwtTimestampValidator;
import org.springframework.security.oauth2.core.DelegatingOAuth2TokenValidator;
import org.springframework.security.oauth2.core.OAuth2TokenValidator;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtClaimValidator;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationConverter;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import jakarta.annotation.PostConstruct;
import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Set;

@Configuration
@EnableMethodSecurity
@EnableConfigurationProperties({JwtAuthProperties.class, MtlsProperties.class, AuthProperties.class})
public class JwtSecurityConfig {

    private static final Logger log = LoggerFactory.getLogger(JwtSecurityConfig.class);

    private static final Set<String> DEFAULT_SECRETS = Set.of(
            "dev-secret-change-me-dev-secret-change-me",
            "autocode-dev-jwt-secret-which-is-at-least-32bytes",
            "your-jwt-secret-at-least-32-bytes-long",
            "changeme",
            "secret",
            "jwt-secret"
    );

    private final JwtAuthProperties jwtProps;

    public JwtSecurityConfig(JwtAuthProperties jwtProps) {
        this.jwtProps = jwtProps;
    }

    @PostConstruct
    void validateJwtSecret() {
        String secret = jwtProps.getSecret();
        if (secret == null || secret.isBlank()) {
            throw new IllegalStateException(
                    "FATAL: mvp.auth.jwt.secret is empty. Set a strong secret (>=32 bytes) before starting.");
        }
        if (DEFAULT_SECRETS.contains(secret.trim().toLowerCase())) {
            throw new IllegalStateException(
                    "FATAL: mvp.auth.jwt.secret uses a known default value. "
                            + "Set a unique secret via MVP_JWT_SECRET environment variable.");
        }
        if (secret.getBytes(StandardCharsets.UTF_8).length < 32) {
            throw new IllegalStateException(
                    "FATAL: mvp.auth.jwt.secret is too short (>=32 bytes required). "
                            + "Current: " + secret.getBytes(StandardCharsets.UTF_8).length + " bytes.");
        }
        log.info("JWT secret validation passed (length={} bytes)", secret.getBytes(StandardCharsets.UTF_8).length);
    }

    @Bean
    public SecurityFilterChain jwtFilterChain(
            HttpSecurity http,
            MtlsProperties mtlsProperties,
            JwtAgentTokenAuthAdapterFilter jwtAgentTokenAuthAdapterFilter
    ) throws Exception {
        http
                .csrf(csrf -> csrf.disable())
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/actuator/health", "/actuator/info").permitAll()
                        .requestMatchers("/actuator/**").hasAnyAuthority("ROLE_ADMIN")
                        .requestMatchers("/ws/**", "/v3/api-docs/**", "/swagger-ui/**", "/swagger-ui.html").permitAll()
                        .requestMatchers("/api/v1/auth/**").permitAll()
                        .requestMatchers(HttpMethod.GET, "/s/*", "/s/**").permitAll()
                        .requestMatchers(HttpMethod.GET, "/api/v1/tasks/*/artifacts/*/site", "/api/v1/tasks/*/artifacts/*/site/**").permitAll()
                        .requestMatchers("/api/v1/agent/**").hasAnyAuthority("ROLE_AGENT", "ROLE_ADMIN")
                        .requestMatchers(HttpMethod.POST, "/api/v1/tasks/*/artifacts", "/api/v1/tasks/*/artifacts/").hasAnyAuthority("ROLE_AGENT", "ROLE_OPERATOR", "ROLE_ADMIN")
                        .anyRequest().hasAnyAuthority("ROLE_OPERATOR", "ROLE_ADMIN", "ROLE_VIEWER")
                )
                .addFilterBefore(new AgentMtlsEnforcementFilter(mtlsProperties), org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter.class)
                .addFilterBefore(jwtAgentTokenAuthAdapterFilter, UsernamePasswordAuthenticationFilter.class)
                .oauth2ResourceServer(oauth2 -> oauth2
                        .jwt(jwt -> jwt.jwtAuthenticationConverter(jwtAuthenticationConverter()))
                );
        return http.build();
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    public SecretKey jwtSecretKey(JwtAuthProperties props) {
        byte[] bytes = props.getSecret().getBytes(StandardCharsets.UTF_8);
        return new SecretKeySpec(bytes, "HmacSHA256");
    }

    @Bean
    public JwtDecoder jwtDecoder(SecretKey key) {
        NimbusJwtDecoder decoder = NimbusJwtDecoder.withSecretKey(key).macAlgorithm(MacAlgorithm.HS256).build();
        OAuth2TokenValidator<Jwt> validator = new DelegatingOAuth2TokenValidator<>(
                JwtValidators.createDefault(),
                new JwtTimestampValidator(),
                new JwtClaimValidator<List<String>>("roles", r -> r != null && !r.isEmpty())
        );
        decoder.setJwtValidator(validator);
        return decoder;
    }

    @Bean
    public JwtEncoder jwtEncoder(SecretKey key) {
        return new NimbusJwtEncoder(new com.nimbusds.jose.jwk.source.ImmutableSecret<>(key));
    }

    private JwtAuthenticationConverter jwtAuthenticationConverter() {
        JwtAuthenticationConverter converter = new JwtAuthenticationConverter();
        converter.setJwtGrantedAuthoritiesConverter(new RolesClaimAuthoritiesConverter());
        return converter;
    }
}

