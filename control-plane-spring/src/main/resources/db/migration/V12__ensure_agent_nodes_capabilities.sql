-- Compatibility migration for environments created before capabilities was added.
-- Avoid MySQL/MariaDB syntax differences around "ADD COLUMN IF NOT EXISTS".
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
