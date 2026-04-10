-- Local MySQL bootstrap for AutoCode (idempotent)
-- Target: mysql://root:000000@127.0.0.1:3306

CREATE DATABASE IF NOT EXISTS mvp_codeops
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

ALTER DATABASE mvp_codeops
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

-- NOTE:
-- Schema objects are managed by Flyway migrations in:
-- control-plane-spring/src/main/resources/db/migration
-- Start control-plane-spring to apply those migrations.
