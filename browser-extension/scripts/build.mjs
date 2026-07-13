import {cp, mkdir, rm} from 'node:fs/promises';
import {resolve} from 'node:path';

const root = resolve(import.meta.dirname, '..');
const dist = resolve(root, 'dist');
await rm(dist, {recursive: true, force: true});
await mkdir(dist, {recursive: true});
await cp(resolve(root, 'manifest.json'), resolve(dist, 'manifest.json'));
await cp(resolve(root, 'src'), dist, {recursive: true});
console.log(`Built unpacked Chromium extension at ${dist}`);
