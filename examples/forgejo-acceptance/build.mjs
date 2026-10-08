import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';

mkdirSync('dist', { recursive: true });
const checksum = createHash('sha256').update(readFileSync('README.md')).digest('hex');
// Deliberately non-sensitive artifact: no environment, logs, tokens or Git config.
writeFileSync('dist/acceptance.json', JSON.stringify({ node: process.version, sourceSha256: checksum }, null, 2) + '\n');
