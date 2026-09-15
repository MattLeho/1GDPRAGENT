type ConnectorDraft = { path: string; host: string; account: string };

function isAbsolutePath(value: string): boolean {
  return value.startsWith('/') || /^[a-zA-Z]:[\\/]/.test(value) || value.startsWith('\\\\');
}

export function validateConnectorDraft(definitionKey: string, input: ConnectorDraft): Record<string, unknown> {
  const account = input.account.trim();
  const host = input.host.trim();
  const selectedPath = input.path.trim();

  if (definitionKey === 'email.imap') {
    if (!account || !host) throw new Error('Email account and IMAP host are required');
    return {
      host,
      port: 993,
      username: account,
      scope: 'headers_and_subject',
      mailboxes: ['INBOX'],
      trash_mailbox: 'Trash',
    };
  }

  if (['ai.conversation.snapshot', 'filesystem.scoped', 'media.photo.folder'].includes(definitionKey)) {
    if (!selectedPath || !isAbsolutePath(selectedPath)) {
      throw new Error('Choose an absolute path visible inside the Intelligence runtime');
    }
    if (definitionKey === 'ai.conversation.snapshot') return { paths: [selectedPath], service: 'auto' };
    if (definitionKey === 'media.photo.folder') return { roots: [selectedPath], mode: 'metadata_only' };
    return { roots: [selectedPath] };
  }

  return { page_content_capture: false, queue_limit: 1000 };
}
