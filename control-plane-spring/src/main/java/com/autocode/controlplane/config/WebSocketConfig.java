/**
 * STOMP/WebSocket configuration for broadcasting task events to clients.
 */
package com.autocode.controlplane.config;

import com.autocode.controlplane.security.JwtWebSocketAuthInterceptor;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.context.annotation.Configuration;
import org.springframework.messaging.simp.config.MessageBrokerRegistry;
import org.springframework.messaging.simp.config.ChannelRegistration;
import org.springframework.web.socket.config.annotation.EnableWebSocketMessageBroker;
import org.springframework.web.socket.config.annotation.StompEndpointRegistry;
import org.springframework.web.socket.config.annotation.WebSocketMessageBrokerConfigurer;

@Configuration
@EnableWebSocketMessageBroker
public class WebSocketConfig implements WebSocketMessageBrokerConfigurer {

    private final ObjectProvider<JwtWebSocketAuthInterceptor> jwtWebSocketAuthInterceptor;

    public WebSocketConfig(
            ObjectProvider<JwtWebSocketAuthInterceptor> jwtWebSocketAuthInterceptor
    ) {
        this.jwtWebSocketAuthInterceptor = jwtWebSocketAuthInterceptor;
    }

    @Override
    public void configureMessageBroker(MessageBrokerRegistry registry) {
        registry.enableSimpleBroker("/topic");
        registry.setApplicationDestinationPrefixes("/app");
    }

    @Override
    public void registerStompEndpoints(StompEndpointRegistry registry) {
        registry.addEndpoint("/ws").setAllowedOriginPatterns("*");
    }

    @Override
    public void configureClientInboundChannel(ChannelRegistration registration) {
        jwtWebSocketAuthInterceptor.ifAvailable(registration::interceptors);
    }
}
