const ACTIVE_STATUSES = Object.freeze(new Set(['queued', 'analyzing', 'failed']));

export const EMPTY_CATALOG = Object.freeze({
  queue: Object.freeze([]),
  reports: Object.freeze([]),
  generatedAt: null,
});

const freezeItems = (items) => Object.freeze(items.map((item) => Object.freeze({ ...item })));

export const normalizeCatalog = (payload) => Object.freeze({
  queue: freezeItems((payload?.queue ?? []).filter((item) => ACTIVE_STATUSES.has(item.status))),
  reports: freezeItems((payload?.reports ?? []).filter((item) => item.report_url)),
  generatedAt: payload?.generated_at ?? null,
});

export const catalogStats = ({ queue, reports }) => Object.freeze({
  queued: queue.filter(({ status }) => status === 'queued').length,
  active: queue.filter(({ status }) => status === 'analyzing').length,
  failed: queue.filter(({ status }) => status === 'failed').length,
  reports: reports.length,
});

export const videoIdFromUrl = (sourceUrl = '') => {
  try {
    const url = new URL(sourceUrl);
    return url.hostname === 'youtu.be'
      ? url.pathname.split('/').filter(Boolean)[0] ?? ''
      : url.searchParams.get('v') ?? '';
  } catch {
    return '';
  }
};

export const thumbnailUrl = (sourceUrl) => {
  const videoId = videoIdFromUrl(sourceUrl);
  return videoId ? `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg` : '';
};

export const reportHref = (reportUrl = '') => reportUrl.split('/').map(encodeURIComponent).join('/');

export const statusPresentation = (status) => Object.freeze({
  queued: { label: 'В очереди', color: 'gray' },
  analyzing: { label: 'Разбирается', color: 'cyan' },
  failed: { label: 'Не удалось', color: 'red' },
}[status] ?? { label: status, color: 'gray' });

export const categoryCounts = (reports) => Object.freeze(
  [...reports.reduce((counts, { category = 'uncategorized' }) => {
    const parts = category.split('/').filter(Boolean);
    parts.forEach((_, index) => {
      const path = parts.slice(0, index + 1).join('/');
      counts.set(path, (counts.get(path) ?? 0) + 1);
    });
    return counts;
  }, new Map())]
    .map(([path, count]) => Object.freeze({ path, count, depth: path.split('/').length - 1 }))
    .sort((left, right) => left.path.localeCompare(right.path)),
);

export const reportsInCategory = (reports, category) => (
  category ? reports.filter(({ category: reportCategory = 'uncategorized' }) => reportCategory === category || reportCategory.startsWith(`${category}/`)) : reports
);
