package com.autocode.gateway;

import com.autocode.gateway.filter.RateLimitingFilter;
import com.autocode.gateway.filter.TimeoutFilter;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.autoconfigure.data.redis.RedisAutoConfiguration;
import org.springframework.boot.autoconfigure.data.redis.RedisReactiveAutoConfiguration;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.cloud.gateway.route.Route;
import org.springframework.cloud.gateway.route.RouteLocator;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.core.ReactiveStringRedisTemplate;
import org.springframework.mock.http.server.reactive.MockServerHttpRequest;
import org.springframework.mock.web.server.MockServerWebExchange;
import org.springframework.test.context.TestPropertySource;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.List;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

/**
 * Property-based tests for Property 30: Gateway Unified Entry Point.
 *
 * <p><b>Validates: Requirements 9.1, 9.2</b>
 *
 * <p>Property 30 states: <em>For any system service access, the
 * Spring_Cloud_Gateway SHALL provide unified entry point at port 8080 with
 * proper routing.</em>
 *
 * <p>These parameterised tests cover many input combinations to verify:
 * <ul>
 *   <li>Every Control Plane path is routed to the Control Plane upstream (port 8058).</li>
 *   <li>Every Java Sandbox path is routed to the Java Sandbox upstream (port 18080).</li>
 *   <li>Every static content path is routed to the static-content route.</li>
 *   <li>Generation paths use the dedicated generation route (300-second timeout).</li>
 *   <li>Standard API paths use the standard API route (30-second timeout).</li>
 *   <li>Unrecognised paths are handled by the fallback route (no upstream leak).</li>
 *   <li>All required service route IDs are present in the route locator.</li>
 *   <li>Rate limit constant is 100 requests per minute per client.</li>
 * </ul>
 *
 * <p>Redis auto-configuration is excluded so the test runs without a real
 * Redis instance; a mock {@link ReactiveStringRedisTemplate} is provided
 * instead.
 */
@SpringBootTest(
        classes = {GatewayApplication.class, GatewayRoutingPropertyTest.TestConfig.class},
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT
)
@TestPropertySource(properties = {
        "gateway.upstream.control-plane.url=http://localhost:8058",
        "gateway.upstream.java-sandbox.url=http://localhost:18080",
        "gateway.upstream.static-content.url=http://localhost:8058",
        "spring.data.redis.host=localhost",
        "spring.data.redis.port=6379",
        "spring.cloud.gateway.httpclient.connect-timeout=1000",
        "spring.cloud.gateway.httpclient.response-timeout=30s",
        // Disable YAML-defined routes (they use RequestRateLimiter which requires Redis)
        // The programmatic routes in GatewayConfig are what we test here.
        "spring.cloud.gateway.routes=",
        "spring.autoconfigure.exclude=" +
                "org.springframework.cloud.gateway.config.GatewayRedisAutoConfiguration," +
                "org.springframework.cloud.configuration.CompatibilityVerifierAutoConfiguration"
})
@DisplayName("Property 30: Gateway Unified Entry Point (Requirements 9.1, 9.2)")
class GatewayRoutingPropertyTest {

    /**
     * Minimal test configuration that provides a mock Redis template so the
     * {@link RateLimitingFilter} can be instantiated without a real Redis.
     */
    @Configuration
    @EnableAutoConfiguration(exclude = {
            RedisAutoConfiguration.class,
            RedisReactiveAutoConfiguration.class
    })
    static class TestConfig {
        @Bean
        public ReactiveStringRedisTemplate reactiveStringRedisTemplate() {
            return mock(ReactiveStringRedisTemplate.class);
        }
    }

    @Autowired
    private RouteLocator routeLocator;

    @Autowired
    private TimeoutFilter timeoutFilter;

    // =========================================================================
    // Property 30a – Control Plane routing (Requirement 9.2)
    // =========================================================================

    /**
     * For any Control Plane API path, the gateway SHALL route to the Control
     * Plane upstream (port 8058).
     *
     * <p><b>Validates: Requirements 9.1, 9.2</b>
     */
    @ParameterizedTest(name = "Control Plane path ''{0}'' routes to control-plane upstream (port 8058)")
    @MethodSource("controlPlanePaths")
    @DisplayName("Property 30a: Control Plane paths route to Control Plane upstream")
    void property30a_controlPlanePaths_routeToControlPlane(String path) {
        Route matchedRoute = findFirstMatchingRoute(path);

        assertThat(matchedRoute)
                .as("A route must exist for Control Plane path '%s'", path)
                .isNotNull();

        assertThat(matchedRoute.getUri().getPort())
                .as("Route for '%s' must target control-plane port 8058", path)
                .isEqualTo(8058);
    }

    static Stream<Arguments> controlPlanePaths() {
        return Stream.of(
                // Standard API paths
                Arguments.of("/api/tasks"),
                Arguments.of("/api/tasks/123"),
                Arguments.of("/api/tasks/123/status"),
                Arguments.of("/api/events"),
                Arguments.of("/api/events/publish"),
                Arguments.of("/api/artifacts"),
                Arguments.of("/api/artifacts/abc-123"),
                Arguments.of("/api/approvals"),
                Arguments.of("/api/approvals/pending"),
                // Actuator / management
                Arguments.of("/actuator/health"),
                Arguments.of("/actuator/info"),
                Arguments.of("/actuator/metrics"),
                Arguments.of("/actuator/prometheus"),
                // Artifact short-links
                Arguments.of("/s/abc123"),
                Arguments.of("/s/xyz-456")
        );
    }

    // =========================================================================
    // Property 30b – Generation path routing (Requirement 9.2)
    // =========================================================================

    /**
     * For any generation task path, the gateway SHALL route to the Control
     * Plane upstream using the dedicated generation route (which carries the
     * 300-second timeout policy).
     *
     * <p><b>Validates: Requirements 9.1, 9.2</b>
     */
    @ParameterizedTest(name = "Generation path ''{0}'' uses control-plane-generation route")
    @MethodSource("generationPaths")
    @DisplayName("Property 30b: Generation paths use the dedicated generation route")
    void property30b_generationPaths_useGenerationRoute(String path) {
        Route matchedRoute = findFirstMatchingRoute(path);

        assertThat(matchedRoute)
                .as("A route must exist for generation path '%s'", path)
                .isNotNull();

        assertThat(matchedRoute.getId())
                .as("Generation path '%s' must use the 'control-plane-generation' route", path)
                .isEqualTo("control-plane-generation");

        // Also verify it targets the Control Plane
        assertThat(matchedRoute.getUri().getPort())
                .as("Generation path '%s' must target port 8058", path)
                .isEqualTo(8058);
    }

    static Stream<Arguments> generationPaths() {
        return Stream.of(
                Arguments.of("/api/tasks/generate/backend"),
                Arguments.of("/api/tasks/generate/frontend"),
                Arguments.of("/api/tasks/generate/fullstack"),
                Arguments.of("/api/generate/backend"),
                Arguments.of("/api/generate/run"),
                Arguments.of("/api/backend-generate/start"),
                Arguments.of("/api/backend-generate/run"),
                Arguments.of("/api/fullstack-generate/start"),
                Arguments.of("/api/fullstack-generate/run")
        );
    }

    // =========================================================================
    // Property 30c – Java Sandbox routing (Requirement 9.2)
    // =========================================================================

    /**
     * For any Java Sandbox path, the gateway SHALL route to the Java Sandbox
     * upstream (port 18080).
     *
     * <p><b>Validates: Requirements 9.1, 9.2</b>
     */
    @ParameterizedTest(name = "Sandbox path ''{0}'' routes to java-sandbox upstream (port 18080)")
    @MethodSource("sandboxPaths")
    @DisplayName("Property 30c: Sandbox paths route to Java Sandbox upstream")
    void property30c_sandboxPaths_routeToJavaSandbox(String path) {
        Route matchedRoute = findFirstMatchingRoute(path);

        assertThat(matchedRoute)
                .as("A route must exist for sandbox path '%s'", path)
                .isNotNull();

        assertThat(matchedRoute.getUri().getPort())
                .as("Sandbox path '%s' must target port 18080", path)
                .isEqualTo(18080);

        assertThat(matchedRoute.getId())
                .as("Sandbox path '%s' must use 'java-sandbox' route", path)
                .isEqualTo("java-sandbox");
    }

    static Stream<Arguments> sandboxPaths() {
        return Stream.of(
                Arguments.of("/sandbox/execute"),
                Arguments.of("/sandbox/execute/java"),
                Arguments.of("/sandbox/health"),
                Arguments.of("/sandbox/run"),
                Arguments.of("/sandbox/compile")
        );
    }

    // =========================================================================
    // Property 30d – Static content routing (Requirement 9.2)
    // =========================================================================

    /**
     * For any static content path, the gateway SHALL route to the static
     * content route.
     *
     * <p><b>Validates: Requirements 9.1, 9.2</b>
     */
    @ParameterizedTest(name = "Static path ''{0}'' uses static-content route")
    @MethodSource("staticPaths")
    @DisplayName("Property 30d: Static content paths use the static-content route")
    void property30d_staticPaths_useStaticContentRoute(String path) {
        Route matchedRoute = findFirstMatchingRoute(path);

        assertThat(matchedRoute)
                .as("A route must exist for static path '%s'", path)
                .isNotNull();

        assertThat(matchedRoute.getId())
                .as("Static path '%s' must use 'static-content' route", path)
                .isEqualTo("static-content");
    }

    static Stream<Arguments> staticPaths() {
        return Stream.of(
                Arguments.of("/static/app.js"),
                Arguments.of("/static/style.css"),
                Arguments.of("/static/index.html"),
                Arguments.of("/assets/logo.png"),
                Arguments.of("/assets/fonts/roboto.woff2"),
                Arguments.of("/favicon.ico")
        );
    }

    // =========================================================================
    // Property 30e – All known service paths have a non-fallback route (Req 9.1)
    // =========================================================================

    /**
     * For any path belonging to a known service, the gateway SHALL have at
     * least one matching route that is not the fallback 404 handler.
     *
     * <p><b>Validates: Requirements 9.1, 9.2</b>
     */
    @ParameterizedTest(name = "Known service path ''{0}'' does not fall through to fallback")
    @MethodSource("allKnownServicePaths")
    @DisplayName("Property 30e: All known service paths have a non-fallback route")
    void property30e_allKnownServicePaths_haveNonFallbackRoute(String path) {
        Route matchedRoute = findFirstMatchingRoute(path);

        assertThat(matchedRoute)
                .as("A route must exist for known service path '%s'", path)
                .isNotNull();

        assertThat(matchedRoute.getId())
                .as("Known service path '%s' must not fall through to fallback route", path)
                .isNotEqualTo("fallback");
    }

    static Stream<Arguments> allKnownServicePaths() {
        return Stream.concat(
                Stream.concat(controlPlanePaths(), generationPaths()),
                Stream.concat(sandboxPaths(), staticPaths())
        );
    }

    // =========================================================================
    // Property 30f – Unrecognised paths are handled by fallback (Req 9.1)
    // =========================================================================

    /**
     * For any path that does not belong to a known service, the gateway SHALL
     * route to the fallback handler (returning 404) rather than leaking to an
     * upstream service.
     *
     * <p><b>Validates: Requirements 9.1</b>
     */
    @ParameterizedTest(name = "Unknown path ''{0}'' is handled by fallback route")
    @MethodSource("unknownPaths")
    @DisplayName("Property 30f: Unknown paths are handled by fallback route")
    void property30f_unknownPaths_routeToFallback(String path) {
        Route matchedRoute = findFirstMatchingRoute(path);

        assertThat(matchedRoute)
                .as("A route (fallback) must exist for unknown path '%s'", path)
                .isNotNull();

        assertThat(matchedRoute.getId())
                .as("Unknown path '%s' must be handled by fallback route", path)
                .isEqualTo("fallback");
    }

    static Stream<Arguments> unknownPaths() {
        return Stream.of(
                Arguments.of("/unknown"),
                Arguments.of("/admin"),
                Arguments.of("/internal/secret"),
                Arguments.of("/v1/legacy"),
                Arguments.of("/graphql"),
                Arguments.of("/metrics")   // not under /actuator
        );
    }

    // =========================================================================
    // Property 30g – All required service route IDs are present (Req 9.2)
    // =========================================================================

    /**
     * The gateway route locator SHALL define routes for all three required
     * service categories: Control Plane, Java Sandbox, and static content.
     *
     * <p><b>Validates: Requirements 9.2</b>
     */
    @ParameterizedTest(name = "Required route ''{0}'' is present in route locator")
    @MethodSource("requiredRouteIds")
    @DisplayName("Property 30g: All required service routes are configured")
    void property30g_requiredRoutes_arePresentInLocator(String requiredRouteId) {
        List<String> routeIds = routeLocator.getRoutes()
                .map(Route::getId)
                .collectList()
                .block();

        assertThat(routeIds)
                .as("Route locator must contain route '%s' (Requirement 9.2)", requiredRouteId)
                .contains(requiredRouteId);
    }

    static Stream<Arguments> requiredRouteIds() {
        return Stream.of(
                // Control Plane routes (Requirement 9.2)
                Arguments.of("control-plane-generation"),
                Arguments.of("control-plane-api"),
                // Java Sandbox route (Requirement 9.2)
                Arguments.of("java-sandbox"),
                // Static content route (Requirement 9.2)
                Arguments.of("static-content")
        );
    }

    // =========================================================================
    // Property 30h – Timeout routing: generation paths get 300s (Req 9.4)
    // =========================================================================

    /**
     * For any generation path, the timeout filter SHALL resolve a 300-second
     * timeout (not the default 30-second API timeout).
     *
     * <p><b>Validates: Requirements 9.2</b> (generation routing behaviour)
     */
    @ParameterizedTest(name = "Generation path ''{0}'' resolves to 300-second timeout")
    @MethodSource("generationPaths")
    @DisplayName("Property 30h: Generation paths resolve to 300-second timeout")
    void property30h_generationPaths_resolve300sTimeout(String path) throws Exception {
        Duration timeout = invokeResolveTimeout(timeoutFilter, path);

        assertThat(timeout)
                .as("Generation path '%s' must resolve to 300-second timeout", path)
                .isEqualTo(Duration.ofSeconds(300));
    }

    // =========================================================================
    // Property 30i – Timeout routing: standard API paths get 30s (Req 9.4)
    // =========================================================================

    /**
     * For any standard API path (non-generation), the timeout filter SHALL
     * resolve the default 30-second timeout.
     *
     * <p><b>Validates: Requirements 9.2</b> (standard API routing behaviour)
     */
    @ParameterizedTest(name = "Standard API path ''{0}'' resolves to 30-second timeout")
    @MethodSource("standardApiPaths")
    @DisplayName("Property 30i: Standard API paths resolve to 30-second timeout")
    void property30i_standardApiPaths_resolve30sTimeout(String path) throws Exception {
        Duration timeout = invokeResolveTimeout(timeoutFilter, path);

        assertThat(timeout)
                .as("Standard API path '%s' must resolve to 30-second timeout", path)
                .isEqualTo(Duration.ofSeconds(30));
    }

    static Stream<Arguments> standardApiPaths() {
        return Stream.of(
                Arguments.of("/api/tasks"),
                Arguments.of("/api/tasks/123"),
                Arguments.of("/api/events"),
                Arguments.of("/api/artifacts"),
                Arguments.of("/actuator/health"),
                Arguments.of("/sandbox/execute"),
                Arguments.of("/static/app.js"),
                Arguments.of("/s/abc123")
        );
    }

    // =========================================================================
    // Property 30j – Rate limit is 100 requests per minute per client (Req 9.5)
    // =========================================================================

    /**
     * The rate limiting policy SHALL enforce exactly 100 requests per minute
     * per client, with a 60-second window.
     *
     * <p><b>Validates: Requirements 9.2</b> (gateway policy configuration)
     */
    @ParameterizedTest(name = "Rate limit constant {0} has expected value {1}")
    @MethodSource("rateLimitConstants")
    @DisplayName("Property 30j: Rate limit is 100 requests per minute per client")
    void property30j_rateLimitConstants_matchRequirements(String constantName, long expectedValue)
            throws Exception {
        long actualValue = readRateLimitConstant(constantName);

        assertThat(actualValue)
                .as("Rate limit constant '%s' must equal %d (Requirement 9.5)", constantName, expectedValue)
                .isEqualTo(expectedValue);
    }

    static Stream<Arguments> rateLimitConstants() {
        return Stream.of(
                Arguments.of("MAX_REQUESTS_PER_WINDOW", 100L),
                Arguments.of("WINDOW_DURATION_SECONDS", 60L)
        );
    }

    // =========================================================================
    // Helpers
    // =========================================================================

    /**
     * Returns the first {@link Route} whose predicate matches the given path,
     * or {@code null} if no route matches.
     */
    private Route findFirstMatchingRoute(String path) {
        ServerWebExchange exchange = exchangeFor(path);
        return routeLocator.getRoutes()
                .filter(route -> Boolean.TRUE.equals(
                        Mono.from(route.getPredicate().apply(exchange)).block()))
                .next()
                .block();
    }

    /** Creates a {@link ServerWebExchange} for the given path (GET request). */
    private static ServerWebExchange exchangeFor(String path) {
        MockServerHttpRequest request = MockServerHttpRequest.get(path).build();
        return MockServerWebExchange.from(request);
    }

    /**
     * Invokes the package-private {@code resolveTimeout(String)} method on
     * {@link TimeoutFilter} via reflection (the method is package-private and
     * this test lives in a different package).
     */
    private static Duration invokeResolveTimeout(TimeoutFilter filter, String path)
            throws Exception {
        java.lang.reflect.Method method =
                TimeoutFilter.class.getDeclaredMethod("resolveTimeout", String.class);
        method.setAccessible(true);
        return (Duration) method.invoke(filter, path);
    }

    /**
     * Reads a package-private static field from {@link RateLimitingFilter}
     * via reflection and returns its value as a {@code long}.
     */
    private static long readRateLimitConstant(String constantName) throws Exception {
        return switch (constantName) {
            case "MAX_REQUESTS_PER_WINDOW" -> {
                java.lang.reflect.Field f =
                        RateLimitingFilter.class.getDeclaredField("MAX_REQUESTS_PER_WINDOW");
                f.setAccessible(true);
                yield (long) f.get(null);
            }
            case "WINDOW_DURATION_SECONDS" -> {
                java.lang.reflect.Field f =
                        RateLimitingFilter.class.getDeclaredField("WINDOW_DURATION");
                f.setAccessible(true);
                yield ((Duration) f.get(null)).getSeconds();
            }
            default -> throw new IllegalArgumentException("Unknown constant: " + constantName);
        };
    }
}
