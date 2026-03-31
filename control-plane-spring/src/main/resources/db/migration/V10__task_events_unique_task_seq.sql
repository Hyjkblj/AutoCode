ALTER TABLE task_events
    ADD UNIQUE KEY uq_task_events_task_seq (task_id, seq_num);

