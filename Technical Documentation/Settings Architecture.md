# Settings Architecture

Settings now uses navigation instead of one long card grid:

- **Profile & Identity** preserves existing profile and ID-document management.
- **Connectors** exposes email status, permissions, sync state, data classes, credential rotation/test/disconnect controls, and built-in SMTP/IMAP configuration.
- **Processing & Models** groups concrete task routes by Speech, Images, Documents, Semantic Analysis, Graph, and Policy & Requests. Each row exposes engine, location, model, fallback chain, health, and advanced limits.
- **Workflows** selects built-in/N8N/hybrid/disabled independently per workflow. N8N details appear only when applicable.
- **Data Retention** is an explicit placeholder for Task 5 and enables no deletion.
- **Privacy & Security** configures processing mode and external fallback, documents encryption/local paths, and answers which external engines processed personal data.
- **Advanced** contains raw provider credentials, ONSIT credentials, and canonical N8N webhook configuration.

Email secrets are submitted as secrets to a server action, encrypted server-side with versioned AES-256-GCM, and stored only in `connector_credentials`. Public settings queries omit ciphertext. Rotation increments a credential version; deletion removes the credential. Legacy browser-base64 values are quarantined as `needs_reentry` and are never treated as encrypted.
