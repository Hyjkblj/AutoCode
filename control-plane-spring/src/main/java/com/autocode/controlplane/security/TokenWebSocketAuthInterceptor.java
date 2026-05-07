package com.autocode.controlplane.security;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.messaging.Message;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.simp.stomp.StompCommand;
import org.springframework.messaging.simp.stomp.StompHeaderAccessor;
import org.springframework.messaging.support.ChannelInterceptor;
import org.springframework.messaging.support.MessageBuilder;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * Enforces token + deviceId on STOMP CONNECT in token auth mode.
 *
 * @deprecated Use {@link JwtWebSocketAuthInterceptor} (mvp.auth.mode=jwt) instead.
 *             Token mode will be removed in a future release.
 */
@Component
@ConditionalOnProperty(prefix = "mvp.auth", name = "mode", havingValue = "token")
@Deprecated(since = "2.0", forRemoval = true)
public class TokenWebSocketAuthInterceptor implements ChannelInterceptor {

    private final AuthProperties authProperties;

    public TokenWebSocketAuthInterceptor(AuthProperties authProperties) {
        this.authProperties = authProperties;
    }

    @Override
    public Message<?> preSend(Message<?> message, MessageChannel channel) {
        StompHeaderAccessor accessor = StompHeaderAccessor.wrap(message);
        if (accessor.getCommand() == null) {
            return message;
        }

        if (StompCommand.CONNECT.equals(accessor.getCommand())) {
            String deviceId = header(accessor, "deviceId");
            if (deviceId == null || deviceId.isBlank()) {
                throw new AccessDeniedException("missing deviceId");
            }

            Authentication authentication = parseAuthentication(accessor);
            accessor.setUser(authentication);
            return MessageBuilder.createMessage(message.getPayload(), accessor.getMessageHeaders());
        }

        if ((StompCommand.SUBSCRIBE.equals(accessor.getCommand())
                || StompCommand.SEND.equals(accessor.getCommand()))
                && accessor.getUser() == null) {
            throw new AccessDeniedException("unauthenticated websocket frame");
        }

        return message;
    }

    private Authentication parseAuthentication(StompHeaderAccessor accessor) {
        String authorization = header(accessor, "Authorization");
        if (authorization != null && authorization.startsWith("Bearer ")) {
            String token = authorization.substring("Bearer ".length());
            if (isAllowedOperatorToken(token)) {
                return new UsernamePasswordAuthenticationToken(
                        "operator",
                        token,
                        List.of(new SimpleGrantedAuthority("ROLE_OPERATOR"))
                );
            }
            throw new AccessDeniedException("invalid operator token");
        }

        String agentToken = header(accessor, "X-Agent-Token");
        if (isAllowedAgentToken(agentToken)) {
            return new UsernamePasswordAuthenticationToken(
                    "agent",
                    agentToken,
                    List.of(new SimpleGrantedAuthority("ROLE_AGENT"))
            );
        }

        throw new AccessDeniedException("missing or invalid token");
    }

    private boolean isAllowedOperatorToken(String token) {
        if (token == null || token.isBlank()) {
            return false;
        }
        if (authProperties.revokedTokenList().contains(token)) {
            return false;
        }
        return authProperties.operatorTokenList().contains(token);
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

    private static String header(StompHeaderAccessor accessor, String name) {
        return accessor.getFirstNativeHeader(name);
    }
}
