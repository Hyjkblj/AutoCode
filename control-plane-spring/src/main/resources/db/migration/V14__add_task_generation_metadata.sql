ALTER TABLE tasks
    ADD COLUMN target VARCHAR(32),
    ADD COLUMN template_id VARCHAR(128),
    ADD COLUMN export_mode VARCHAR(32);
