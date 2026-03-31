package com.autocode.controlplane.security;

import org.springframework.core.convert.converter.Converter;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;

/**
 * Converts JWT "roles" claim to Spring Security authorities.
 *
 * Expected claim format: ["OPERATOR","ADMIN",...]
 */
public class RolesClaimAuthoritiesConverter implements Converter<Jwt, Collection<GrantedAuthority>> {
    @Override
    public Collection<GrantedAuthority> convert(Jwt jwt) {
        Object raw = jwt.getClaims().get("roles");
        List<GrantedAuthority> out = new ArrayList<>();
        if (raw instanceof Collection<?> c) {
            for (Object r : c) {
                if (r == null) continue;
                String role = String.valueOf(r).trim();
                if (role.isEmpty()) continue;
                if (!role.startsWith("ROLE_")) {
                    role = "ROLE_" + role;
                }
                out.add(new SimpleGrantedAuthority(role));
            }
        }
        return out;
    }
}

