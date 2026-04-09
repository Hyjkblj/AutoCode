package com.autocode.controlplane.security;

import org.junit.jupiter.api.Test;
import org.springframework.messaging.Message;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.simp.stomp.StompCommand;
import org.springframework.messaging.simp.stomp.StompHeaderAccessor;
import org.springframework.messaging.support.ExecutorSubscribableChannel;
import org.springframework.messaging.support.MessageBuilder;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtException;

import java.time.Instant;
import java.util.List;
import java.util.function.Consumer;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class JwtWebSocketAuthInterceptorTest {

    private final MessageChannel channel = new ExecutorSubscribableChannel();

    @Test
    void connectShouldRejectMissingAuthorizationHeader() {
        JwtWebSocketAuthInterceptor interceptor = interceptor(token -> validJwt("operator"));
        Message<byte[]> message = stomp(StompCommand.CONNECT, accessor -> {
        });

        assertThrows(AccessDeniedException.class, () -> interceptor.preSend(message, channel));
    }

    @Test
    void connectShouldRejectInvalidJwtToken() {
        JwtWebSocketAuthInterceptor interceptor = interceptor(token -> {
            throw new JwtException("bad token");
        });
        Message<byte[]> message = stomp(StompCommand.CONNECT, accessor ->
                accessor.addNativeHeader("Authorization", "Bearer bad"));

        assertThrows(AccessDeniedException.class, () -> interceptor.preSend(message, channel));
    }

    @Test
    void connectShouldRejectTokenWithoutRoles() {
        JwtWebSocketAuthInterceptor interceptor = interceptor(token ->
                Jwt.withTokenValue(token)
                        .header("alg", "HS256")
                        .subject("operator")
                        .issuedAt(Instant.now())
                        .expiresAt(Instant.now().plusSeconds(300))
                        .build());
        Message<byte[]> message = stomp(StompCommand.CONNECT, accessor ->
                accessor.addNativeHeader("Authorization", "Bearer no-roles"));

        assertThrows(AccessDeniedException.class, () -> interceptor.preSend(message, channel));
    }

    @Test
    void connectWithValidJwtShouldAttachPrincipal() {
        JwtWebSocketAuthInterceptor interceptor = interceptor(token -> validJwt("operator"));
        Message<byte[]> message = stomp(StompCommand.CONNECT, accessor ->
                accessor.addNativeHeader("Authorization", "Bearer good"));

        Message<?> out = interceptor.preSend(message, channel);
        Authentication auth = (Authentication) StompHeaderAccessor.wrap(out).getUser();

        assertEquals("operator", auth.getName());
        assertTrue(auth.getAuthorities().stream().anyMatch(a -> "ROLE_OPERATOR".equals(a.getAuthority())));
    }

    @Test
    void subscribeShouldRejectWhenUnauthenticated() {
        JwtWebSocketAuthInterceptor interceptor = interceptor(token -> validJwt("operator"));
        Message<byte[]> message = stomp(StompCommand.SUBSCRIBE, accessor ->
                accessor.addNativeHeader("destination", "/topic/tasks/tsk-1"));

        assertThrows(AccessDeniedException.class, () -> interceptor.preSend(message, channel));
    }

    @Test
    void sendShouldRejectWhenUnauthenticated() {
        JwtWebSocketAuthInterceptor interceptor = interceptor(token -> validJwt("operator"));
        Message<byte[]> message = stomp(StompCommand.SEND, accessor ->
                accessor.addNativeHeader("destination", "/app/tasks/approve"));

        assertThrows(AccessDeniedException.class, () -> interceptor.preSend(message, channel));
    }

    @Test
    void sendShouldPassWhenAuthenticated() {
        JwtWebSocketAuthInterceptor interceptor = interceptor(token -> validJwt("operator"));
        Message<byte[]> message = stomp(StompCommand.SEND, accessor -> {
            accessor.addNativeHeader("destination", "/app/tasks/approve");
            accessor.setUser(new UsernamePasswordAuthenticationToken(
                    "operator",
                    "good",
                    List.of(new SimpleGrantedAuthority("ROLE_OPERATOR"))
            ));
        });

        Message<?> out = interceptor.preSend(message, channel);
        assertEquals(StompCommand.SEND, StompHeaderAccessor.wrap(out).getCommand());
    }

    private static JwtWebSocketAuthInterceptor interceptor(JwtDecoder decoder) {
        return new JwtWebSocketAuthInterceptor(decoder);
    }

    private static Jwt validJwt(String subject) {
        return Jwt.withTokenValue("good")
                .header("alg", "HS256")
                .subject(subject)
                .claim("roles", List.of("OPERATOR"))
                .issuedAt(Instant.now())
                .expiresAt(Instant.now().plusSeconds(300))
                .build();
    }

    private static Message<byte[]> stomp(StompCommand command, Consumer<StompHeaderAccessor> configurer) {
        StompHeaderAccessor accessor = StompHeaderAccessor.create(command);
        configurer.accept(accessor);
        return MessageBuilder.createMessage(new byte[0], accessor.getMessageHeaders());
    }
}
