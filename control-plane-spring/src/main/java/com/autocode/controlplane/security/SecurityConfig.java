/**
 * Spring Security filter chain wiring for the MVP token authentication filter.
 *
 * @deprecated Use {@link JwtSecurityConfig} (mvp.auth.mode=jwt) instead.
 *             Token mode will be removed in a future release.
 */
package com.autocode.controlplane.security;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.http.HttpMethod;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

@Configuration
@EnableMethodSecurity
@EnableConfigurationProperties({AuthProperties.class, MtlsProperties.class})
@ConditionalOnProperty(prefix = "mvp.auth", name = "mode", havingValue = "token")
@Deprecated(since = "2.0", forRemoval = true)
public class SecurityConfig {
    private static final Logger log = LoggerFactory.getLogger(SecurityConfig.class);

    @Bean
    public SecurityFilterChain securityFilterChain(
            HttpSecurity http,
            TokenAuthFilter tokenAuthFilter,
            MtlsProperties mtlsProperties
    ) throws Exception {
        log.warn("DEPRECATED: token auth mode is active (mvp.auth.mode=token). " +
                "Switch to JWT mode (mvp.auth.mode=jwt) — token mode will be removed in a future release.");
        http
                .csrf(csrf -> csrf.disable())
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(authorize -> authorize
                        .requestMatchers(
                                "/actuator/**",
                                "/ws/**",
                                "/v3/api-docs/**",
                                "/swagger-ui/**",
                                "/swagger-ui.html"
                        ).permitAll()
                        .requestMatchers(HttpMethod.GET, "/s/*", "/s/**").permitAll()
                        .requestMatchers(HttpMethod.GET, "/api/v1/tasks/*/artifacts/*/site", "/api/v1/tasks/*/artifacts/*/site/**").permitAll()
                        .anyRequest().authenticated()
                )
                .addFilterBefore(new AgentMtlsEnforcementFilter(mtlsProperties), UsernamePasswordAuthenticationFilter.class)
                .addFilterBefore(tokenAuthFilter, UsernamePasswordAuthenticationFilter.class);
        return http.build();
    }
}
