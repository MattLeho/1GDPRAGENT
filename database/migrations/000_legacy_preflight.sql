-- Make known route-created legacy variants safe for the canonical migrations.
ALTER TABLE IF EXISTS n8n_webhooks ADD COLUMN IF NOT EXISTS workflow_key TEXT;
ALTER TABLE IF EXISTS user_profiles ADD COLUMN IF NOT EXISTS avatar_url TEXT;
ALTER TABLE IF EXISTS request_chat_messages ADD COLUMN IF NOT EXISTS sender TEXT;
ALTER TABLE IF EXISTS request_chat_messages ADD COLUMN IF NOT EXISTS message TEXT;

DO $$
BEGIN
  IF to_regclass('public.request_chat_messages') IS NOT NULL THEN
    IF EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='request_chat_messages' AND column_name='role') THEN
      EXECUTE 'UPDATE request_chat_messages SET sender=COALESCE(sender,role) WHERE sender IS NULL';
    END IF;
    IF EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='request_chat_messages' AND column_name='content') THEN
      EXECUTE 'UPDATE request_chat_messages SET message=COALESCE(message,content) WHERE message IS NULL';
    END IF;
  END IF;
END $$;
