-- AG-UP-05 / PY-AG-01 control-plane compatibility:
-- older environments may have applied early V1 without later-edited agent_nodes columns.
-- Backfill registration/runtime columns in a forward-only migration.
-- V13 keeps migration versions unique while preserving existing V12 history.

SET @has_version_col := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'agent_nodes'
      AND COLUMN_NAME = 'version'
);

SET @sql_add_version := IF(
    @has_version_col = 0,
    'ALTER TABLE agent_nodes ADD COLUMN version VARCHAR(64) NULL',
    'SELECT 1'
);
PREPARE stmt_add_version FROM @sql_add_version;
EXECUTE stmt_add_version;
DEALLOCATE PREPARE stmt_add_version;

SET @has_capabilities_col := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'agent_nodes'
      AND COLUMN_NAME = 'capabilities'
);

SET @sql_add_capabilities := IF(
    @has_capabilities_col = 0,
    'ALTER TABLE agent_nodes ADD COLUMN capabilities TEXT NULL',
    'SELECT 1'
);
PREPARE stmt_add_capabilities FROM @sql_add_capabilities;
EXECUTE stmt_add_capabilities;
DEALLOCATE PREPARE stmt_add_capabilities;

SET @has_heartbeat_col := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'agent_nodes'
      AND COLUMN_NAME = 'last_heartbeat_at'
);

SET @sql_add_heartbeat := IF(
    @has_heartbeat_col = 0,
    'ALTER TABLE agent_nodes ADD COLUMN last_heartbeat_at TIMESTAMP(6) NULL',
    'SELECT 1'
);
PREPARE stmt_add_heartbeat FROM @sql_add_heartbeat;
EXECUTE stmt_add_heartbeat;
DEALLOCATE PREPARE stmt_add_heartbeat;
