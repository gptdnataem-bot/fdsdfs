# NXT Esports Bot с пингером для Replit

## Как запустить
1. Импортируй проект в Replit.
2. Открой **Tools → Secrets** и добавь переменные окружения:
   - BOT_TOKEN = 8296822215:AAE7HUE8FKo9TPv52LY7bg35Q1I8WT4Fk34
   - ADMIN_USER_ID = 6090041587
   - REVIEW_CHAT_ID = -1002779423327
   - TARGET_CHANNEL_ID = -1002715413786
   - OPENROUTER_API_KEY = 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
   - OPENROUTER_MODEL = deepseek/deepseek-chat
   - FETCH_INTERVAL_MIN = 5
   - KEEPALIVE_ENABLED = true
   - KEEPALIVE_INTERVAL_SEC = 300
   - COVER_MODE = always
   - COVER_TAG = HIGHLIGHT
3. Запусти проект (Run).
4. Проверь в браузере: `https://<имя-проекта>.<твой-юзер>.repl.co/health` должно вернуть OK.

## Как сделать, чтобы не засыпал
1. Зарегистрируйся на https://uptimerobot.com
2. Создай монитор типа HTTP(s) с адресом `/health`
3. Интервал — 5 минут.
