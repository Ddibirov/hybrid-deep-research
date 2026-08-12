# Agent-Reach Data Sources (локально, машина Сэра)

Этот файл — machine-specific. Не коммитить в публичный репозиторий.

## Доступные каналы

| Канал | Команда | Статус | Примечание |
|-------|---------|--------|------------|
| GitHub | `gh repo view/repo/search` | ✅ | Полный доступ |
| YouTube | `yt-dlp --dump-json URL` | ✅ | Субтитры + инфо |
| Reddit | `rdt-cli search/read` | ✅ | Залогинен как ddibirov |
| Web (любой URL) | `curl https://r.jina.ai/URL` | ✅ | → чистый markdown |
| Web Search | Exa (semantic) | ✅ | Бесплатно, без API-ключа |
| RSS | `feedparser` | ✅ | |
| V2EX | Публичное API | ✅ | |
| Bilibili | `yt-dlp` / API | ✅ | |
| WeChat Articles | Exa | ✅ | |

Исследователи могут использовать эти команды напрямую в terminal().
Команды установлены в системе, никаких дополнительных API-ключей для указанных каналов не требуется.
