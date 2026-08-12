# Agent-Reach Channels (установлено 2026-06-30)

Установлена версия 1.5.0, `pip install` через URL (не PyPI).
`agent-reach install --env=auto` — 9/16 каналов активны.

## Активные каналы (zero config)

### GitHub
- Команда: `gh repo view owner/repo`, `gh search repos "query"`
- Статус: полный доступ (fork, issue, PR, search)
- Установлен: системный пакет

### YouTube
- Команда: `yt-dlp --dump-json URL` — инфо о видео + субтитры
- Статус: работает
- Установлен: через pip (`yt-dlp==2026.6.9`)

### Reddit
- Команда: `rdt-cli search "query"`, `rdt-cli read URL`
- Статус: работает, залогинен как ddibirov
- Команда установки: `pipx install rdt-cli`

### Web (любая страница → Markdown)
- Команда: `curl https://r.jina.ai/URL`
- Статус: бесплатно, без API-ключа

### Web Search (семантический)
- Команда: Exa через mcporter
- Статус: работает, бесплатно, без API-ключа

### RSS/Atom
- Команда: `feedparser` (через Python)
- Статус: работает

### V2EX
- Команда: публичное API
- Статус: без аутентификации

### Bilibili
- Команда: `yt-dlp` + Bilibili API
- Статус: базовая работа, рекомендуется `pipx install bilibili-cli` для расширенного доступа

### WeChat Articles
- Команда: Exa search
- Статус: через семантический поиск

## Неактивные (требуют настройки)

- Twitter/X — нужен cookie (экспорт из Chrome)
- XiaoHongShu — OpenCLI/MCP
- Weibo — OpenCLI
- Douyin — OpenCLI
- LinkedIn — MCP/Jina Reader
- Xiaoyuzhou Podcast — Groq Whisper API
- Xueqiu (stock) — cookie

## Архитектура

Каждый канал = ordered backend list (primary + fallback). При падении одного бэкенда — переключение на следующий без участия пользователя.

Channels: `~/.agent-reach/channels/<platform>.py`
Конфиг: `~/.agent-reach/config.yaml`
SKILL: `~/.agents/skills/agent-reach/SKILL.md`
