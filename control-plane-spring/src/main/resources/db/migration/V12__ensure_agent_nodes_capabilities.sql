-- Compatibility migration for environments created before capabilities was added.
ALTER TABLE agent_nodes
    ADD COLUMN IF NOT EXISTS capabilities TEXT;
