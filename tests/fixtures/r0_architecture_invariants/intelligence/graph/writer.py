def unsafe(session):
    return session.run('CREATE INDEX bad_index FOR (n:Bad) ON (n.id)')
