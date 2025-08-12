import os, requests

TONE_INSTRUCTIONS = (
    "Ты — редактор канала NXT Esports. Пиши кратко, дерзко, по делу. "
    "Структура: 1) факт (1–2 предложения), 2) контекст/мнение (1–2 предложения), "
    "3) вопрос для вовлечения, 4) 2–4 хэштега. Без воды."
)

def rewrite_text(text: str) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        # No AI key; return trimmed original
        return text.strip()
    base = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    model = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": TONE_INSTRUCTIONS},
            {"role": "user", "content": text},
        ],
        "temperature": 0.7,
        "max_tokens": 240,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://nxt-esports-bot.local",
        "X-Title": "NXT Esports Bot",
    }
    try:
        r = requests.post(f"{base}/chat/completions", json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return text.strip()
