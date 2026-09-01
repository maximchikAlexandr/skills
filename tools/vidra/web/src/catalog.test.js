import assert from 'node:assert/strict';
import test from 'node:test';

import { catalogStats, normalizeCatalog, reportHref, videoIdFromUrl } from './catalog.js';

test('normalizes catalog without mutating its input', () => {
  const payload = { queue: [{ id: 1, status: 'queued' }], reports: [{ id: 2, report_url: 'reports/a b.html' }] };
  const catalog = normalizeCatalog(payload);
  assert.deepEqual(catalogStats(catalog), { queued: 1, active: 0, failed: 0, reports: 1 });
  assert.equal(Object.isFrozen(catalog.queue[0]), true);
  assert.equal(Object.isFrozen(payload.queue[0]), false);
});

test('extracts YouTube ids and encodes report paths', () => {
  assert.equal(videoIdFromUrl('https://www.youtube.com/watch?v=abc123'), 'abc123');
  assert.equal(videoIdFromUrl('https://youtu.be/xyz789'), 'xyz789');
  assert.equal(reportHref('reports/разбор видео.html'), 'reports/%D1%80%D0%B0%D0%B7%D0%B1%D0%BE%D1%80%20%D0%B2%D0%B8%D0%B4%D0%B5%D0%BE.html');
});
