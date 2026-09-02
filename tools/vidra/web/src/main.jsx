import '@mantine/core/styles.css';
import './styles.css';

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

import { categoryCounts, categoryLabel, catalogStats, EMPTY_CATALOG, itemsInCategory, normalizeCatalog, reportHref, reportsInCategory, repositoryLabel, statusPresentation, thumbnailUrl } from './catalog.js';

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
  return { ...state, reload: load };
};

const Stat = ({ label, value }) => (
  <Paper className="stat" withBorder><Text size="xs" c="dimmed" tt="uppercase" fw={700}>{label}</Text><Text size="xl" fw={800}>{value}</Text></Paper>
);

const QueueCard = ({ video }) => {
  const status = statusPresentation(video.status);
  return (
    <Card className="queue-card" withBorder>
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <Box><Badge color={status.color} variant="light">{status.label}</Badge><Text fw={700} mt="sm">{video.title}</Text><Anchor href={video.source_url} target="_blank" rel="noopener noreferrer" size="sm">Открыть источник <IconArrowUpRight size={13} /></Anchor></Box>
        <ThemeIcon variant="light" color={status.color}><IconClock size={18} /></ThemeIcon>
      </Group>
      {video.request && <Text size="sm" c="dimmed" mt="sm" lineClamp={1}>{video.request}</Text>}
      {video.error && <Alert icon={<IconAlertTriangle size={16} />} color="red" variant="light" mt="md" p="sm"><Text size="sm" lineClamp={2}>{video.error}</Text></Alert>}
    </Card>
  );
};

const ReportCard = ({ report }) => {
  const thumbnail = thumbnailUrl(report.source_url);
  const [imageFailed, setImageFailed] = useState(false);
  return (
    <Card className="report-card" withBorder padding={0} component="a" href={reportHref(report.report_url)}>
      <Box className="thumb">{thumbnail && !imageFailed ? <Image src={thumbnail} alt="" h="100%" w="100%" fit="cover" onError={() => setImageFailed(true)} /> : <IconVideo size={38} stroke={1.5} /> }<ThemeIcon className="play" radius="xl" size="lg"><IconPlayerPlay size={18} /></ThemeIcon></Box>
      <Stack gap={7} p="md"><Group gap="xs"><Badge variant="light">{report.report_concept || 'video report'}</Badge>{report.source_count > 1 && <Badge color="violet" variant="light">{report.source_count} видео</Badge>}</Group><Title order={3} size="h4" lineClamp={2}>{report.report_title || report.title}</Title><Text size="sm" c="dimmed" lineClamp={1}>{report.title}</Text><Group justify="space-between" mt="xs"><Text size="xs" c="dimmed">{categoryLabel(report.category)}</Text><Text size="xs" ff="monospace" c="teal">{report.report_hash}</Text></Group></Stack>
    </Card>
  );
};

const ProjectCard = ({ project }) => {
  const [imageFailed, setImageFailed] = useState(false);
  return (
    <Card className="report-card project-card" withBorder padding={0} component="a" href={reportHref(project.report_url)}>
      <Box className="thumb project-thumb">{project.preview_url && !imageFailed ? <Image src={project.preview_url} alt={`Превью ${repositoryLabel(project)}`} h="100%" w="100%" fit="cover" onError={() => setImageFailed(true)} /> : <IconBrandGithub size={42} stroke={1.5} />}</Box>
      <Stack gap={7} p="md"><Group justify="space-between" wrap="nowrap"><Badge leftSection={<IconBrandGithub size={12} />} variant="light">GitHub</Badge>{project.stars != null && <Text size="xs" c="dimmed">★ {project.stars.toLocaleString('ru-RU')}</Text>}</Group><Title order={3} size="h4" lineClamp={2}>{project.title}</Title><Text size="sm" fw={650}>{repositoryLabel(project)}</Text>{project.summary && <Text size="sm" c="dimmed" lineClamp={2}>{project.summary}</Text>}<Text size="xs" ff="monospace" c="dimmed">{project.revision.slice(0, 12)}</Text></Stack>
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
  const { catalog, loading, error, reload } = useCatalog();
  const stats = useMemo(() => catalogStats(catalog), [catalog]);
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedProjectCategory, setSelectedProjectCategory] = useState('');
  const visibleReports = useMemo(() => reportsInCategory(catalog.reports, selectedCategory), [catalog.reports, selectedCategory]);
  const visibleProjects = useMemo(() => itemsInCategory(catalog.projects, selectedProjectCategory), [catalog.projects, selectedProjectCategory]);
  return (
    <AppShell header={{ height: 64 }}>
      <AppShell.Header><Container size="xl" h="100%"><Group h="100%" justify="space-between" wrap="nowrap"><Group gap="sm" wrap="nowrap"><ThemeIcon radius="md" size="lg"><IconFolders size={21} /></ThemeIcon><Box><Text fw={850} lh={1}>VIDRA</Text><Text size="xs" c="dimmed">Каталог аналитических отчётов</Text></Box></Group><Button className="refresh-button" variant="subtle" leftSection={loading ? <Loader size={15} /> : <IconRefresh size={16} />} onClick={reload} disabled={loading}>Обновить</Button></Group></Container></AppShell.Header>
      <AppShell.Main><Container size="xl" py="xl">
        <Group className="hero" justify="space-between" align="flex-end" mb="xl"><Box className="hero-copy"><Text className="kicker">Библиотека знаний</Text><Title order={1}>Видео и GitHub-проекты</Title><Text c="dimmed" mt={4}>Очередь источников и проверяемые HTML-разборы.</Text></Box><SimpleGrid cols={5} spacing="xs" className="stats"><Stat label="В очереди" value={stats.queued} /><Stat label="В работе" value={stats.active} /><Stat label="Ошибки" value={stats.failed} /><Stat label="Видео" value={stats.reports} /><Stat label="Проекты" value={stats.projects} /></SimpleGrid></Group>
        {error && <Alert color="red" icon={<IconAlertTriangle size={18} />} mb="xl">{error}</Alert>}
        <section><Group justify="space-between" mb="md"><Title order={2}>Очередь</Title><Badge color="gray" variant="light">{catalog.queue.length}</Badge></Group>{catalog.queue.length ? <SimpleGrid cols={{ base: 1, md: 2 }}>{catalog.queue.map((video) => <QueueCard key={video.id} video={video} />)}</SimpleGrid> : <Empty>Очередь пуста</Empty>}</section>
        <section className="reports"><Group justify="space-between" mb="md"><Box><Title order={2}>Готовые отчёты</Title>{selectedCategory && <Text size="sm" c="dimmed">{categoryLabel(selectedCategory)}</Text>}</Box><Badge variant="light">{visibleReports.length}</Badge></Group>{catalog.reports.length ? <div className="library"><CategoryBrowser items={catalog.reports} selected={selectedCategory} onSelect={setSelectedCategory} /><Box>{visibleReports.length ? <SimpleGrid cols={{ base: 1, md: 2, xl: 3 }}>{visibleReports.map((report) => <ReportCard key={report.report_url} report={report} />)}</SimpleGrid> : <Empty>В этой теме отчётов нет</Empty>}</Box></div> : <Empty>Отчётов пока нет</Empty>}</section>
        <section className="reports" id="projects"><Group justify="space-between" mb="md"><Box><Title order={2}>Разборы GitHub-проектов</Title>{selectedProjectCategory ? <Text size="sm" c="dimmed">{categoryLabel(selectedProjectCategory)}</Text> : <Text size="sm" c="dimmed">Один проект — один самостоятельный отчёт</Text>}</Box><Badge color="dark" variant="light">{visibleProjects.length}</Badge></Group>{catalog.projects.length ? <div className="library"><CategoryBrowser items={catalog.projects} selected={selectedProjectCategory} onSelect={setSelectedProjectCategory} allLabel="Все проекты" /><Box>{visibleProjects.length ? <SimpleGrid cols={{ base: 1, md: 2, xl: 3 }}>{visibleProjects.map((project) => <ProjectCard key={project.repository_key} project={project} />)}</SimpleGrid> : <Empty>В этой теме проектов нет</Empty>}</Box></div> : <Empty>Разборов проектов пока нет</Empty>}</section>
      </Container></AppShell.Main>
    </AppShell>
  );
};

createRoot(document.getElementById('root')).render(<StrictMode><MantineProvider theme={theme} defaultColorScheme="light"><App /></MantineProvider></StrictMode>);
