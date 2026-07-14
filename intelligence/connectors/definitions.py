"""Built-in source connector definitions; acquisition only, never semantics."""
from .models import (
    ConnectorMode, ConnectorPermission, PermissionAccess, SourceConnectorDefinition,
)


BROWSER_HISTORY_DEFINITION = SourceConnectorDefinition(
    key="browser.chromium.history", version="1", display_name="Chromium browser history",
    provider="Chromium", connector_type="browser_history",
    modes=(ConnectorMode.SNAPSHOT_IMPORT, ConnectorMode.EVENT_STREAM),
    data_classes=("browser.visit",),
    permissions=(
        ConnectorPermission(
            key="history.read", access=PermissionAccess.READ, data_class="browser.visit",
            description="Read visit URL, time, transition and referral metadata", required=True,
        ),
        ConnectorPermission(
            key="page_content.read", access=PermissionAccess.NOT_READ, data_class="browser.visit",
            description="Page content is not captured by this connector version",
        ),
    ),
    supports_backfill=True, supports_incremental=True,
    configuration_schema={
        "type": "object", "additionalProperties": False,
        "properties": {
            "browser_profile_connector_id": {"type": "string", "minLength": 1},
            "queue_limit": {"type": "integer", "minimum": 1, "maximum": 5000},
            "page_content_capture": {"const": False},
        },
    },
)


IMAP_EMAIL_DEFINITION = SourceConnectorDefinition(
    key="email.imap", version="1", display_name="IMAP email source",
    provider="IMAP", connector_type="email_source",
    modes=(ConnectorMode.SNAPSHOT_IMPORT, ConnectorMode.INCREMENTAL_POLL),
    data_classes=("email.message",),
    permissions=(
        ConnectorPermission(
            key="mail.metadata", access=PermissionAccess.READ, data_class="email.message",
            description="Read mailbox, participants, timestamps and attachment metadata", required=True,
        ),
        ConnectorPermission(
            key="mail.headers", access=PermissionAccess.READ, data_class="email.message",
            description="Read subject and relevant RFC message headers",
        ),
        ConnectorPermission(
            key="mail.body", access=PermissionAccess.READ, data_class="email.message",
            description="Read text message bodies",
        ),
        ConnectorPermission(
            key="mail.attachments", access=PermissionAccess.READ, data_class="email.message",
            description="Ingest attachment content through Task 3A",
        ),
        ConnectorPermission(
            key="mail.source_delete", access=PermissionAccess.DELETE, data_class="email.message",
            description="Move explicitly approved messages to the IMAP Trash mailbox",
            required=False, enabled_by_default=False,
        ),
    ),
    supports_backfill=True, supports_incremental=True, supports_source_delete=True,
    configuration_schema={
        "type": "object", "additionalProperties": False,
        "required": ["host", "username", "scope"],
        "properties": {
            "host": {"type": "string", "minLength": 1},
            "port": {"type": "integer", "minimum": 1, "maximum": 65535},
            "username": {"type": "string", "minLength": 1},
            "scope": {"enum": ["metadata_only", "headers_and_subject", "text_body", "full_message"]},
            "mailboxes": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "sent_mailboxes": {"type": "array", "items": {"type": "string"}},
            "batch_size": {"type": "integer", "minimum": 1, "maximum": 500},
            "trash_mailbox": {"type": "string", "minLength": 1},
        },
    },
)


AI_CONVERSATION_DEFINITION = SourceConnectorDefinition(
    key="ai.conversation.snapshot", version="1", display_name="AI conversation exports",
    provider="Local export", connector_type="ai_conversation",
    modes=(ConnectorMode.SNAPSHOT_IMPORT, ConnectorMode.FOLDER_WATCH),
    data_classes=("ai.conversation_export", "ai.conversation_turn"),
    permissions=(ConnectorPermission(
        key="conversations.read", access=PermissionAccess.READ,
        data_class="ai.conversation_turn",
        description="Read user-selected AI conversation export files", required=True,
    ),),
    supports_backfill=True, supports_incremental=True,
    configuration_schema={
        "type": "object", "additionalProperties": False,
        "required": ["paths"], "properties": {
            "paths": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "service": {"enum": ["auto", "chatgpt", "claude", "generic"]},
            "max_file_bytes": {"type": "integer", "minimum": 1, "maximum": 536870912},
        },
    },
)


FILESYSTEM_DEFINITION = SourceConnectorDefinition(
    key="filesystem.scoped", version="1", display_name="Scoped filesystem",
    provider="Local filesystem", connector_type="filesystem",
    modes=(ConnectorMode.SNAPSHOT_IMPORT, ConnectorMode.FOLDER_WATCH),
    data_classes=("filesystem.file", "filesystem.observation"),
    permissions=(ConnectorPermission(
        key="files.read", access=PermissionAccess.READ, data_class="filesystem.file",
        description="Read files only below explicitly selected roots", required=True,
    ),), supports_backfill=True, supports_incremental=True,
    configuration_schema={"type": "object", "additionalProperties": False, "required": ["roots"], "properties": {
        "roots": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "include": {"type": "array", "items": {"type": "string"}},
        "exclude": {"type": "array", "items": {"type": "string"}},
        "max_size": {"type": "integer", "minimum": 1},
        "supported_types": {"type": "array", "items": {"type": "string"}},
        "metadata_only_paths": {"type": "array", "items": {"type": "string"}},
        "content_analysis_paths": {"type": "array", "items": {"type": "string"}},
    }},
)


PHOTO_FOLDER_DEFINITION = SourceConnectorDefinition(
    key="media.photo.folder", version="1", display_name="Photo/media folder",
    provider="Local filesystem", connector_type="photo_media_folder",
    modes=(ConnectorMode.SNAPSHOT_IMPORT, ConnectorMode.FOLDER_WATCH),
    data_classes=("photo.media", "photo.media_sidecar", "filesystem.observation"),
    permissions=(
        ConnectorPermission(
            key="media.metadata", access=PermissionAccess.READ, data_class="photo.media",
            description="Read selected media files for metadata extraction", required=True,
        ),
        ConnectorPermission(
            key="media.visual_analysis", access=PermissionAccess.READ, data_class="photo.media",
            description="Run explicitly selected visual analysis tasks",
        ),
    ), supports_backfill=True, supports_incremental=True,
    configuration_schema={"type": "object", "additionalProperties": False, "required": ["roots"], "properties": {
        "roots": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "mode": {"enum": ["metadata_only", "selected_visual_analysis", "full_visual_analysis"]},
        "visual_analysis_paths": {"type": "array", "items": {"type": "string"}},
        "include": {"type": "array", "items": {"type": "string"}},
        "exclude": {"type": "array", "items": {"type": "string"}},
        "max_size": {"type": "integer", "minimum": 1},
    }},
)
