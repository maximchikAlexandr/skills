# 1. Transcription Source Strategy (Yandex first, site subtitles fallback)

## Status

Accepted

## Context

Для YouTube-видео транскрибация через Yandex API (`getSubtitles`) часто возвращает `waiting=true` и пустой список даже после успешного запуска перевода аудио.

При этом в части роликов YouTube-субтитры доступны сразу и позволяют получить текст с таймкодами.

Требование: в рамках одного запуска получать 2 текстовых файла транскрибации (с таймкодами и без), не блокируя скачивание видео/аудио при недоступности Yandex subtitles.

## Decision

1. Источник по приоритету:
- сначала Yandex subtitles API;
- если Yandex subtitles недоступны, fallback на субтитры площадки через `yt-dlp`.

2. Формат артефактов:
- стабильная подпапка `transcription` внутри папки загрузки видео;
- `transcript_with_timestamps.txt`;
- `transcript_plain.txt`.

3. Прозрачность результата:
- в `download_metadata.txt` писать `transcription_status`, `transcription_source`, `transcription_info`.

## Consequences

- Пайплайн устойчивее: даже при недоступности Yandex subtitles можно получить транскрипты из site subtitles.
- Транскрипт может быть не на целевом языке (например, fallback на `en` при ошибках `ru` subtitles).
- В `transcription_info` фиксируется, откуда реально получен текст.
