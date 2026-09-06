import '@mantine/core/styles.css';
import './styles.css';
import './ratings.css';

import { StrictMode, useCallback, useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Alert,
  Anchor,
  AppShell,
  Badge,
  Box,
  Button,
  Card,
  Container,
  Divider,
  Group,
  Image,
  Loader,
  MantineProvider,
  Paper,
  SimpleGrid,
  Stack,
  Text,
  ThemeIcon,
  Title,
} from '@mantine/core';
import { IconAlertTriangle, IconArrowUpRight, IconBrandGithub, IconChevronRight, IconClock, IconFolder, IconFolders, IconPlayerPlay, IconRefresh, IconVideo } from '@tabler/icons-react';

import { categoryCounts, categoryLabel, catalogStats, EMPTY_CATALOG, itemsInCategory, normalizeCatalog, reportHref, reportsInCategory, repositoryLabel, sortByRating, statusPresentation, thumbnailUrl, withRating } from './catalog.js';

const theme = {
  primaryColor: 'teal',
  defaultRadius: 'md',
  fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif',
  headings: { fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif' },
};

const useCatalog = () => {
  const [state, setState] = useState({ catalog: EMPTY_CATALOG, loading: true, error: '' });
  const load = useCallback(async () => {
    setState((current) => ({ ...current, loading: true, error: '' }));
    try {
      const response = await fetch('api/catalog', { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const catalog = normalizeCatalog(await response.json());
      setState({ catalog, loading: false, error: '' });
    } catch (error) {
      setState((current) => ({ ...current, loading: false, error: `Каталог недоступен: ${error.message}` }));
    }
  }, []);
  useEffect(() => { load(); }, [load]);
  const rate = useCallback(async (sourceType, reportHash, rating) => {
    setState((current) => ({ ...current, catalog: withRating(current.catalog, sourceType, reportHash, rating) }));
    try {
      const response = await fetch('api/ratings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_type: sourceType, report_hash: reportHash, rating }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
    } catch (error) {
      await load();
      setState((current) => ({ ...current, error: `Не удалось сохранить оценку: ${error.message}` }));
    }
  }, [load]);
  return { ...state, reload: load, rate };
};

const Stat = ({ label, value }) => (
  <Paper className="stat" withBorder><Text size="xs" c="dimmed" tt="uppercase" fw={700}>{label}</Text><Text size="xl" fw={800}>{value}</Text></Paper>
);

const QueueCard = ({ item }) => {
  const status = statusPresentation(item.status);
  const isProject = item.source_type === 'github_project';
  return (
    <Card className="queue-card" withBorder>
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <Box><Group gap="xs"><Badge color={status.color} variant="light">{status.label}</Badge><Badge color={isProject ? 'dark' : 'teal'} variant="outline">{isProject ? 'GitHub' : 'Видео'}</Badge></Group><Text fw={700} mt="sm">{item.title}</Text><Anchor href={item.source_url} target="_blank" rel="noopener noreferrer" size="sm">Открыть источник <IconArrowUpRight size={13} /></Anchor></Box>
        <ThemeIcon variant="light" color={status.color}>{isProject ? <IconBrandGithub size={18} /> : <IconClock size={18} />}</ThemeIcon>
      </Group>
      {item.request && <Text size="sm" c="dimmed" mt="sm" lineClamp={1}>{item.request}</Text>}
      {item.error && <Alert icon={<IconAlertTriangle size={16} />} color="red" variant="light" mt="md" p="sm"><Text size="sm" lineClamp={2}>{item.error}</Text></Alert>}
    </Card>
  );
};

const Rating = ({ value = 0, onChange }) => (
  <Group className="rating" gap={2} role="radiogroup" aria-label="Оценка отчёта">
    {[1, 2, 3, 4, 5].map((star) => (
      <button key={star} type="button" className={star <= value ? 'star active' : 'star'} role="radio" aria-checked={value === star} aria-label={`${star} из 5`} title={`Оценить на ${star}`} onClick={() => onChange(star)}>★</button>
    ))}
  </Group>
);

const ReportCard = ({ report, onRate }) => {
  const thumbnail = thumbnailUrl(report.source_url);
  const [imageFailed, setImageFailed] = useState(false);
  return (
    <Card className="report-card" withBorder padding={0}>
      <Anchor className="report-link" href={reportHref(report.report_url)}><Box className="thumb">{thumbnail && !imageFailed ? <Image src={thumbnail} alt="" h="100%" w="100%" fit="cover" onError={() => setImageFailed(true)} /> : <IconVideo size={38} stroke={1.5} /> }<ThemeIcon className="play" radius="xl" size="lg"><IconPlayerPlay size={18} /></ThemeIcon></Box></Anchor>
      <Stack gap={7} p="md"><Group gap="xs"><Badge variant="light">{report.report_concept || 'видеоотчёт'}</Badge>{report.source_count > 1 && <Badge color="violet" variant="light">{report.source_count} видео</Badge>}</Group><Anchor className="title-link" href={reportHref(report.report_url)}><Title order={3} size="h4" lineClamp={2}>{report.report_title || report.title}</Title></Anchor><Text size="sm" c="dimmed" lineClamp={1}>{report.title}</Text><Rating value={report.rating ?? 0} onChange={(rating) => onRate('video', report.report_hash, rating)} /><Group justify="space-between" mt="xs"><Text size="xs" c="dimmed">{categoryLabel(report.category)}</Text><Text size="xs" ff="monospace" c="teal">{report.report_hash}</Text></Group></Stack>
    </Card>
  );
};

const ProjectCard = ({ project, onRate }) => {
  const [imageFailed, setImageFailed] = useState(false);
  const isSkill = project.source_type === 'github_skill';
  return (
    <Card className="report-card project-card" withBorder padding={0}>
      <Anchor className="report-link" href={reportHref(project.report_url)}><Box className="thumb project-thumb">{project.preview_url && !imageFailed ? <Image src={project.preview_url} alt={`Превью ${repositoryLabel(project)}`} h="100%" w="100%" fit="cover" onError={() => setImageFailed(true)} /> : <IconBrandGithub size={42} stroke={1.5} />}</Box></Anchor>
      <Stack gap={7} p="md"><Group justify="space-between" wrap="nowrap"><Badge leftSection={<IconBrandGithub size={12} />} variant="light">{isSkill ? 'GitHub Skill' : 'GitHub'}</Badge>{project.stars != null && <Text size="xs" c="dimmed">★ {project.stars.toLocaleString('ru-RU')}</Text>}</Group><Anchor className="title-link" href={reportHref(project.report_url)}><Title order={3} size="h4" lineClamp={2}>{project.title}</Title></Anchor><Text size="sm" fw={650}>{repositoryLabel(project)}</Text>{isSkill && <Text size="xs" ff="monospace" c="dimmed" lineClamp={1}>{project.skill_path}</Text>}{project.summary && <Text size="sm" c="dimmed" lineClamp={2}>{project.summary}</Text>}<Rating value={project.rating ?? 0} onChange={(rating) => onRate(project.source_type, project.report_hash, rating)} /><Text size="xs" ff="monospace" c="dimmed">{project.revision.slice(0, 12)}</Text></Stack>
    </Card>
  );
};

const CategoryBrowser = ({ items, selected, onSelect, allLabel = 'Все отчёты' }) => {
  const categories = categoryCounts(items);
  return (
    <Paper withBorder className="category-browser">
      <Group gap="xs" mb="sm"><ThemeIcon variant="light"><IconFolders size={18} /></ThemeIcon><Text fw={800}>Темы</Text></Group>
      <Button fullWidth justify="space-between" variant={!selected ? 'light' : 'subtle'} onClick={() => onSelect('')} rightSection={<Badge size="sm" variant="transparent">{items.length}</Badge>}>{allLabel}</Button>
      <Divider my="xs" />
      <Stack gap={2}>{categories.map(({ path, count, depth }) => (
        <Button key={path} fullWidth justify="space-between" variant={selected === path ? 'light' : 'subtle'} color={selected === path ? 'teal' : 'gray'} onClick={() => onSelect(path)} className="category-button" style={{ paddingLeft: 12 + depth * 18 }} leftSection={depth ? <IconChevronRight size={14} /> : <IconFolder size={16} />} rightSection={<Badge size="sm" variant="transparent">{count}</Badge>}>{categoryLabel(path)}</Button>
      ))}</Stack>
    </Paper>
  );
};

const Empty = ({ children }) => <Paper withBorder className="empty"><IconVideo size={30} /><Text c="dimmed">{children}</Text></Paper>;

const App = () => {
  const { catalog, loading, error, reload, rate } = useCatalog();
  const stats = useMemo(() => catalogStats(catalog), [catalog]);
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedProjectCategory, setSelectedProjectCategory] = useState('');
  const visibleReports = useMemo(() => sortByRating(reportsInCategory(catalog.reports, selectedCategory)), [catalog.reports, selectedCategory]);
  const visibleProjects = useMemo(() => sortByRating(itemsInCategory(catalog.projects, selectedProjectCategory)), [catalog.projects, selectedProjectCategory]);
  return (
    <AppShell header={{ height: 64 }}>
      <AppShell.Header><Container size="xl" h="100%"><Group h="100%" justify="space-between" wrap="nowrap"><Group gap="sm" wrap="nowrap"><ThemeIcon radius="md" size="lg"><IconFolders size={21} /></ThemeIcon><Box><Text fw={850} lh={1}>VIDRA</Text><Text size="xs" c="dimmed">Каталог аналитических отчётов</Text></Box></Group><Button className="refresh-button" variant="subtle" leftSection={loading ? <Loader size={15} /> : <IconRefresh size={16} />} onClick={reload} disabled={loading}>Обновить</Button></Group></Container></AppShell.Header>
      <AppShell.Main><Container size="xl" py="xl">
        <Group className="hero" justify="space-between" align="flex-end" mb="xl"><Box className="hero-copy"><Text className="kicker">Библиотека знаний</Text><Title order={1}>Видео и GitHub-проекты</Title><Text c="dimmed" mt={4}>Очередь источников и проверяемые HTML-разборы.</Text></Box><SimpleGrid cols={5} spacing="xs" className="stats"><Stat label="В очереди" value={stats.queued} /><Stat label="В работе" value={stats.active} /><Stat label="Ошибки" value={stats.failed} /><Stat label="Видео" value={stats.reports} /><Stat label="Проекты" value={stats.projects} /></SimpleGrid></Group>
        {error && <Alert color="red" icon={<IconAlertTriangle size={18} />} mb="xl">{error}</Alert>}
        <section><Group justify="space-between" mb="md"><Box><Title order={2}>Очередь источников</Title><Text size="sm" c="dimmed">Видео и GitHub-проекты в порядке добавления</Text></Box><Badge color="gray" variant="light">{catalog.queue.length}</Badge></Group>{catalog.queue.length ? <SimpleGrid cols={{ base: 1, md: 2 }}>{catalog.queue.map((item) => <QueueCard key={`${item.source_type}:${item.id}`} item={item} />)}</SimpleGrid> : <Empty>Очередь пуста</Empty>}</section>
        <section className="reports"><Group justify="space-between" mb="md"><Box><Title order={2}>Готовые отчёты</Title>{selectedCategory && <Text size="sm" c="dimmed">{categoryLabel(selectedCategory)}</Text>}</Box><Badge variant="light">{visibleReports.length}</Badge></Group>{catalog.reports.length ? <div className="library"><CategoryBrowser items={catalog.reports} selected={selectedCategory} onSelect={setSelectedCategory} /><Box>{visibleReports.length ? <SimpleGrid cols={{ base: 1, md: 2, xl: 3 }}>{visibleReports.map((report) => <ReportCard key={report.report_url} report={report} onRate={rate} />)}</SimpleGrid> : <Empty>В этой теме отчётов нет</Empty>}</Box></div> : <Empty>Отчётов пока нет</Empty>}</section>
        <section className="reports" id="projects"><Group justify="space-between" mb="md"><Box><Title order={2}>Разборы GitHub-проектов</Title>{selectedProjectCategory ? <Text size="sm" c="dimmed">{categoryLabel(selectedProjectCategory)}</Text> : <Text size="sm" c="dimmed">Один проект — один самостоятельный отчёт</Text>}</Box><Badge color="dark" variant="light">{visibleProjects.length}</Badge></Group>{catalog.projects.length ? <div className="library"><CategoryBrowser items={catalog.projects} selected={selectedProjectCategory} onSelect={setSelectedProjectCategory} allLabel="Все проекты" /><Box>{visibleProjects.length ? <SimpleGrid cols={{ base: 1, md: 2, xl: 3 }}>{visibleProjects.map((project) => <ProjectCard key={project.repository_key} project={project} onRate={rate} />)}</SimpleGrid> : <Empty>В этой теме проектов нет</Empty>}</Box></div> : <Empty>Разборов проектов пока нет</Empty>}</section>
      </Container></AppShell.Main>
    </AppShell>
  );
};

createRoot(document.getElementById('root')).render(<StrictMode><MantineProvider theme={theme} defaultColorScheme="light"><App /></MantineProvider></StrictMode>);
