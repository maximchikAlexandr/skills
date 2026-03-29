# Decision log

## Scope

Лог отражает текущее состояние разработки `video-analyzer` и принятые рабочие решения, чтобы продолжить реализацию в другом треде без потери контекста.

## Reference

Yandex translation/subtitles API integration based on [voice-over-translation](https://github.com/ilyhalight/voice-over-translation) — browser extension that proxies Yandex Browser voiceover API. Used as reference for understanding protobuf endpoints (`/video-translation/translate`, `/video-subtitles/get-subtitles`), session flow, and the `@vot.js/ext` client library.

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

## Iteration 2: deduplicate rolling captions, improve language handling

### Problem

1. YouTube auto-generated VTT use a "rolling" display pattern: short (~10 ms) flash cues alternate with longer cues that repeat the tail of the previous cue + new words.  `subtitles_to_txt.py` treated every cue independently → каждая строка дублировалась ~3 раза.
2. Транскрипции приходили на английском, хотя `audio_lang=ru`. Причина: Yandex subtitles API возвращает `waiting=true` / пустой список; fallback на site subtitles получал английские субтитры; `getSubtitles` не передавал `responseLang`.

### Changes

1. `subtitles_to_txt.py`:
   - Добавлен `_deduplicate_rolling_cues`: фильтрует flash-cues (< 100 ms), убирает word-level overlap между consecutive cues.
   - Дедупликация активируется автоматически только при > 20 % flash cues (обычные SRT не затрагиваются).
   - Результат: 1565 строк → 228 (Unison видео), 94 (test видео); текст без дублирования.
2. `yandex_fetch_transcription.mjs` — `getSubtitles` теперь передаёт `responseLang: targetLang`.
3. `download_youtube.sh` — yt-dlp subtitle fallback: `--extractor-retries 3 --retry-sleep extractor:5`.

### Test results (https://www.youtube.com/watch?v=mViFYTwWvcM)

- `translation_status=ok` — перевод аудио успешен.
- `transcription_source=site_subtitles`, `lang=en-en` — Yandex subtitles API снова не вернул данных; fallback получил английские субтитры площадки.
- Текст без дублирования, чистый.

## Open items / risks

1. Точность и полнота `transcript_plain.txt` зависит от качества исходных субтитров (Yandex или YouTube auto-captions).
2. Для длинных видео время выполнения заметно растет из-за сетевых ретраев.
3. Yandex subtitles API часто не отдаёт данные (`waiting=true`). `responseLang` передаётся, но это не гарантирует получение субтитров.
4. При fallback на site subtitles язык может отличаться от целевого, если YouTube не предоставляет авто-перевод (429) или субтитров на целевом языке.

## Commits in this thread (relevant)

1. `693810b` - Add video-analyzer download and frame extraction scripts
2. `c415774` - Refactor downloader and add Yandex audio translation helper
3. `860653a` - Add robust transcription pipeline with subtitle fallback
