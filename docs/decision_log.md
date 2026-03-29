# Decision log

## Scope

Лог отражает текущее состояние разработки `video-analyzer` и принятые рабочие решения, чтобы продолжить реализацию в другом треде без потери контекста.

## Current state (implemented)

1. Базовые скрипты:
- `video-analyzer/scripts/download_youtube.sh`
- `video-analyzer/scripts/extract_stop_frames.sh`

2. Скачать видео и аудио:
- выходная папка: `~/.cache/video-analyzer/<sanitized_title>_<timestamp>`;
- пробелы в названии папки заменяются на `_`;
- видео сохраняется как `original_video.<ext>`;
- аудио как `audio_track.m4a`.

3. Выбор языковой дорожки:
- входной аргумент `audio_lang` (default `ru`);
- при наличии целевой дорожки выбирается она;
- при отсутствии — fallback на оригинал.

4. Перевод аудиодорожки:
- при отсутствии целевой аудиодорожки запускается перевод через VOT/Yandex клиент;
- JS-исполнитель: `video-analyzer/scripts/yandex_translate_audio.mjs`;
- результат: `audio_track_translated_<lang>.mp3`.

5. Транскрибация:
- сначала попытка Yandex subtitles (`video-analyzer/scripts/yandex_fetch_transcription.mjs`);
- при неуспехе fallback на subtitles площадки через `yt-dlp`;
- конвертация subtitle -> txt: `video-analyzer/scripts/subtitles_to_txt.py`;
- выходная стабильная подпапка: `<out_dir>/transcription`;
- файлы:
  - `transcript_with_timestamps.txt`
  - `transcript_plain.txt`.

6. Метаданные запуска:
- в `download_metadata.txt` пишутся статусы и детали:
  - `translation_status`, `translation_info`
  - `transcription_status`, `transcription_source`, `transcription_info`.

## Important observations from testing

1. Yandex subtitles часто возвращают `waiting=true` и пустой список на ряде видео, даже после успешного аудио-перевода.
2. Для YouTube auto-translated subtitles на `ru` встречается `HTTP 429`.
3. Fallback на site subtitles повышает вероятность получить транскрипты, но язык может быть не целевым.

## Operational knobs

1. Перевод аудио:
- `VIDEO_ANALYZER_TRANSLATE_MAX_ATTEMPTS`
- `VIDEO_ANALYZER_TRANSLATE_POLL_SECONDS`

2. Yandex subtitles:
- `VIDEO_ANALYZER_SUBS_MAX_ATTEMPTS`
- `VIDEO_ANALYZER_SUBS_POLL_SECONDS`

## Open items / risks

1. Точность и полнота `transcript_plain.txt` зависит от качества исходных субтитров (Yandex или YouTube auto-captions).
2. Для длинных видео время выполнения заметно растет из-за сетевых ретраев.
3. Нужна финальная политика при `429` (например, backoff/jitter, отдельный retry профайл для subtitles).
4. Нужна финальная договоренность: допустим ли fallback язык транскрипции, если целевой язык недоступен.

## Commits in this thread (relevant)

1. `693810b` - Add video-analyzer download and frame extraction scripts
2. `c415774` - Refactor downloader and add Yandex audio translation helper
3. `860653a` - Add robust transcription pipeline with subtitle fallback
