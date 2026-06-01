package com.autocode.protocol.validation;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.networknt.schema.JsonSchema;
import com.networknt.schema.JsonSchemaFactory;
import com.networknt.schema.SpecVersion;
import com.networknt.schema.ValidationMessage;

import java.io.IOException;
import java.io.InputStream;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

/**
 * JSON Schema-based validator for shared protocol messages.
 *
 * <p>Loads {@code .schema.json} files from the classpath and validates
 * JSON instances against them. Schemas are cached after first load.</p>
 */
public class SchemaValidator {
    private static final ObjectMapper MAPPER = new ObjectMapper()
            .registerModule(new JavaTimeModule())
            .disable(com.fasterxml.jackson.databind.SerializationFeature.WRITE_DATES_AS_TIMESTAMPS)
            .setSerializationInclusion(JsonInclude.Include.NON_NULL);
    private static final JsonSchemaFactory SCHEMA_FACTORY =
            JsonSchemaFactory.getInstance(SpecVersion.VersionFlag.V202012);

    private final Map<String, JsonSchema> cache = new ConcurrentHashMap<>();

    /**
     * Validate a JSON object against the named schema.
     *
     * @param schemaResourcePath classpath path to the schema file
     * @param jsonNode           the JSON instance to validate
     * @throws ContractViolationException if validation fails
     */
    public void validate(String schemaResourcePath, JsonNode jsonNode) {
        JsonSchema schema = cache.computeIfAbsent(schemaResourcePath, this::loadSchema);
        Set<ValidationMessage> errors = schema.validate(jsonNode);
        if (!errors.isEmpty()) {
            String details = errors.stream()
                    .map(ValidationMessage::getMessage)
                    .collect(Collectors.joining("; "));
            throw new ContractViolationException("schema violation (" + schemaResourcePath + "): " + details);
        }
    }

    /**
     * Validate a JSON object serialized from a POJO.
     */
    public void validate(String schemaResourcePath, Object pojo) {
        JsonNode node = MAPPER.valueToTree(pojo);
        validate(schemaResourcePath, node);
    }

    /**
     * Validate raw JSON bytes against the named schema.
     */
    public void validateBytes(String schemaResourcePath, byte[] jsonBytes) throws IOException {
        JsonNode node = MAPPER.readTree(jsonBytes);
        validate(schemaResourcePath, node);
    }

    private JsonSchema loadSchema(String resourcePath) {
        try (InputStream is = getClass().getClassLoader().getResourceAsStream(resourcePath)) {
            if (is == null) {
                throw new IllegalStateException("schema not found on classpath: " + resourcePath);
            }
            JsonNode schemaNode = MAPPER.readTree(is);
            return SCHEMA_FACTORY.getSchema(schemaNode);
        } catch (IOException e) {
            throw new IllegalStateException("failed to load schema: " + resourcePath, e);
        }
    }
}
