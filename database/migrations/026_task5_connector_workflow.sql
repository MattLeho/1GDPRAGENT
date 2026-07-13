-- Task 5 Wave 7: expose connector sync through the existing Task 2 workflow registry.
INSERT INTO workflow_preferences(workflow_key,execution_mode,enabled,configuration,fallback_order)
VALUES('connector.sync','built_in',TRUE,'{"schedule_interval_seconds":900}'::jsonb,'["built_in"]'::jsonb)
ON CONFLICT(workflow_key) DO NOTHING;
