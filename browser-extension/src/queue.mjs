export const DEFAULT_QUEUE_LIMIT = 5000;

export class PersistentQueue {
  constructor(storage, key = 'pendingVisits', limit = DEFAULT_QUEUE_LIMIT) {
    this.storage = storage;
    this.key = key;
    this.limit = limit;
  }

  async read() {
    const value = await this.storage.get(this.key);
    return Array.isArray(value[this.key]) ? value[this.key] : [];
  }

  async append(items) {
    const current = await this.read();
    const bySignature = new Map(current.map(item => [item.record_signature, item]));
    for (const item of items) bySignature.set(item.record_signature, item);
    const next = [...bySignature.values()];
    if (next.length > this.limit) throw new Error('local browser queue is full; sync or increase the explicit limit');
    await this.storage.set({[this.key]: next});
    return next.length;
  }

  async acknowledge(signatures) {
    const acknowledged = new Set(signatures);
    const remaining = (await this.read()).filter(item => !acknowledged.has(item.record_signature));
    await this.storage.set({[this.key]: remaining});
    return remaining.length;
  }
}
