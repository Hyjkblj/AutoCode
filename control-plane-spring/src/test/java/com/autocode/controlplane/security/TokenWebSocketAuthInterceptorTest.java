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

import java.util.List;
import java.util.function.Consumer;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class TokenWebSocketAuthInterceptorTest {

    private final MessageChannel channel = new ExecutorSubscribableChannel();

    @Test
    void connectShouldRejectMissingDeviceId() {
        TokenWebSocketAuthInterceptor interceptor = interceptor();
        Message<byte[]> message = stomp(StompCommand.CONNECT, accessor ->
                accessor.addNativeHeader("Authorization", "Bearer op-a"));

        assertThrows(AccessDeniedException.class, () -> interceptor.preSend(message, channel));
    }

    @Test
    void connectShouldRejectRevokedOperatorToken() {
        TokenWebSocketAuthInterceptor interceptor = interceptor();
        Message<byte[]> message = stomp(StompCommand.CONNECT, accessor -> {
            accessor.addNativeHeader("deviceId", "dev-1");
            accessor.addNativeHeader("Authorization", "Bearer op-b");
        });

        assertThrows(AccessDeniedException.class, () -> interceptor.preSend(message, channel));
    }

    @Test
    void connectWithValidOperatorTokenShouldAttachPrincipal() {
        TokenWebSocketAuthInterceptor interceptor = interceptor();
        Message<byte[]> message = stomp(StompCommand.CONNECT, accessor -> {
            accessor.addNativeHeader("deviceId", "dev-1");
            accessor.addNativeHeader("Authorization", "Bearer op-a");
        });

        Message<?> out = interceptor.preSend(message, channel);
        Authentication auth = (Authentication) StompHeaderAccessor.wrap(out).getUser();

        assertEquals("operator", auth.getName());
        assertTrue(auth.getAuthorities().stream().anyMatch(a -> "ROLE_OPERATOR".equals(a.getAuthority())));
    }

    @Test
    void connectWithValidAgentTokenShouldAttachPrincipal() {
        TokenWebSocketAuthInterceptor interceptor = interceptor();
        Message<byte[]> message = stomp(StompCommand.CONNECT, accessor -> {
            accessor.addNativeHeader("deviceId", "dev-2");
            accessor.addNativeHeader("X-Agent-Token", "ag-a");
        });

        Message<?> out = interceptor.preSend(message, channel);
        Authentication auth = (Authentication) StompHeaderAccessor.wrap(out).getUser();

        assertEquals("agent", auth.getName());
        assertTrue(auth.getAuthorities().stream().anyMatch(a -> "ROLE_AGENT".equals(a.getAuthority())));
    }

    @Test
    void subscribeShouldRejectWhenUnauthenticated() {
        TokenWebSocketAuthInterceptor interceptor = interceptor();
        Message<byte[]> message = stomp(StompCommand.SUBSCRIBE, accessor ->
                accessor.addNativeHeader("destination", "/topic/tasks/tsk-1"));

        assertThrows(AccessDeniedException.class, () -> interceptor.preSend(message, channel));
    }

    @Test
    void sendShouldRejectWhenUnauthenticated() {
        TokenWebSocketAuthInterceptor interceptor = interceptor();
        Message<byte[]> message = stomp(StompCommand.SEND, accessor ->
                accessor.addNativeHeader("destination", "/app/tasks/approve"));

        assertThrows(AccessDeniedException.class, () -> interceptor.preSend(message, channel));
    }

    @Test
    void sendShouldPassWhenAuthenticated() {
        TokenWebSocketAuthInterceptor interceptor = interceptor();
        Message<byte[]> message = stomp(StompCommand.SEND, accessor -> {
            accessor.addNativeHeader("destination", "/app/tasks/approve");
            accessor.setUser(new UsernamePasswordAuthenticationToken(
                    "operator",
                    "op-a",
                    List.of(new SimpleGrantedAuthority("ROLE_OPERATOR"))
            ));
        });

        Message<?> out = interceptor.preSend(message, channel);
        assertEquals(StompCommand.SEND, StompHeaderAccessor.wrap(out).getCommand());
    }

    private static TokenWebSocketAuthInterceptor interceptor() {
        AuthProperties props = new AuthProperties();
        props.setOperatorTokens("op-a,op-b");
        props.setAgentTokens("ag-a,ag-b");
        props.setRevokedTokens("op-b,ag-b");
        return new TokenWebSocketAuthInterceptor(props);
    }

    private static Message<byte[]> stomp(StompCommand command, Consumer<StompHeaderAccessor> configurer) {
        StompHeaderAccessor accessor = StompHeaderAccessor.create(command);
        configurer.accept(accessor);
        return MessageBuilder.createMessage(new byte[0], accessor.getMessageHeaders());
    }
}
