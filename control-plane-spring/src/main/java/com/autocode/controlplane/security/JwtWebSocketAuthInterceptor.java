package com.autocode.controlplane.security;

import org.springframework.messaging.Message;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.simp.stomp.StompCommand;
import org.springframework.messaging.simp.stomp.StompHeaderAccessor;
import org.springframework.messaging.support.ChannelInterceptor;
import org.springframework.messaging.support.MessageBuilder;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.stereotype.Component;

import java.util.Collection;
import java.util.List;

/**
 * Enforces JWT auth on STOMP CONNECT.
 */
@Component
public class JwtWebSocketAuthInterceptor implements ChannelInterceptor {

    private final JwtDecoder jwtDecoder;
    private final RolesClaimAuthoritiesConverter authoritiesConverter = new RolesClaimAuthoritiesConverter();

    public JwtWebSocketAuthInterceptor(JwtDecoder jwtDecoder) {
        this.jwtDecoder = jwtDecoder;
    }

    @Override
    public Message<?> preSend(Message<?> message, MessageChannel channel) {
        StompHeaderAccessor accessor = StompHeaderAccessor.wrap(message);
        if (accessor.getCommand() == null) {
            return message;
        }

        if (StompCommand.CONNECT.equals(accessor.getCommand())) {
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
        if (authorization == null || authorization.isBlank() || !authorization.startsWith("Bearer ")) {
            throw new AccessDeniedException("missing or invalid authorization header");
        }
        String token = authorization.substring("Bearer ".length()).trim();
        if (token.isEmpty()) {
            throw new AccessDeniedException("missing or invalid authorization header");
        }

        Jwt jwt;
        try {
            jwt = jwtDecoder.decode(token);
        } catch (JwtException ex) {
            throw new AccessDeniedException("invalid jwt token");
        }

        Collection<GrantedAuthority> authorities = authoritiesConverter.convert(jwt);
        if (authorities == null || authorities.isEmpty()) {
            throw new AccessDeniedException("missing jwt roles");
        }
        String username = jwt.getSubject();
        if (username == null || username.isBlank()) {
            username = "jwt-user";
        }
        return new UsernamePasswordAuthenticationToken(username, token, List.copyOf(authorities));
    }

    private static String header(StompHeaderAccessor accessor, String name) {
        return accessor.getFirstNativeHeader(name);
    }
}
