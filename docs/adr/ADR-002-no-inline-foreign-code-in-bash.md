# 1. No Inline JS/Python in Bash Scripts

## Status

Accepted

## Context

В реализации `download_youtube.sh` присутствовали inline-вставки JS/Python через heredoc.

Это усложняет поддержку, тестирование и повторное использование логики.

Пользователь явно зафиксировал правило: если в bash нужен код на другом языке, его нужно выносить в отдельный файл рядом со скриптом.

## Decision

1. Запретить inline-код на других языках в bash-скриптах проекта.
2. Вынести логику в отдельные файлы и вызывать их из bash:
- `yandex_translate_audio.mjs`
- `yandex_fetch_transcription.mjs`
- `subtitles_to_txt.py`

## Consequences

- Код проще читать, отлаживать и переиспользовать.
- Меньше риск поломок из-за сложного экранирования heredoc.
- Легче переносить/тестировать JS/Python-части отдельно от bash-оркестрации.
