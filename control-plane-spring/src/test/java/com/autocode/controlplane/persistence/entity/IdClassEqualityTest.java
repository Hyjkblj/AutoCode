package com.autocode.controlplane.persistence.entity;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;

class IdClassEqualityTest {

    @Test
    void projectMembershipPkEqualityAndHashCode() {
        ProjectMembershipEntity.Pk a = new ProjectMembershipEntity.Pk("proj-1", "usr-1");
        ProjectMembershipEntity.Pk b = new ProjectMembershipEntity.Pk("proj-1", "usr-1");
        ProjectMembershipEntity.Pk c = new ProjectMembershipEntity.Pk("proj-2", "usr-1");

        assertEquals(a, b);
        assertEquals(a.hashCode(), b.hashCode());
        assertNotEquals(a, c);
    }

    @Test
    void userRolePkEqualityAndHashCode() {
        UserRoleEntity.Pk a = new UserRoleEntity.Pk("usr-1", "OPERATOR");
        UserRoleEntity.Pk b = new UserRoleEntity.Pk("usr-1", "OPERATOR");
        UserRoleEntity.Pk c = new UserRoleEntity.Pk("usr-1", "ADMIN");

        assertEquals(a, b);
        assertEquals(a.hashCode(), b.hashCode());
        assertNotEquals(a, c);
    }
}
