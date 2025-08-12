
import os, asyncio, logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiohttp import web
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from storage.db import init_db, SessionLocal, Item
from ai.rewrite import rewrite_text
from fetchers.rss import load_config, parse_rss, youtube_channel_feed, filter_highlights

logging.basicConfig(level=logging.INFO)
load_dotenv()
init_db()
HEALTH_PORT = int(os.getenv("PORT", 8080))

async def health_handler(request):
    return web.Response(text="OK", status=200)

async def start_health_server():
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=HEALTH_PORT)
    await site.start()
    logging.info(f"Health server on :{HEALTH_PORT}")


BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID") or 0)
REVIEW_CHAT_ID = os.getenv("REVIEW_CHAT_ID") or (ADMIN_USER_ID and str(ADMIN_USER_ID)) or None
FETCH_INTERVAL_MIN = int(os.getenv("FETCH_INTERVAL_MIN") or 90)
KEEPALIVE_ENABLED = os.getenv("KEEPALIVE_ENABLED", "true").lower() == "true"
KEEPALIVE_INTERVAL_SEC = int(os.getenv("KEEPALIVE_INTERVAL_SEC") or 300)

config = load_config()
last_fetch_time = None

def is_admin(user_id: int) -> bool:
    return ADMIN_USER_ID == 0 or user_id == ADMIN_USER_ID

def fmt(item: Item) -> str:
    return f"📰 <b>{item.title}</b>\n{item.summary}\n\nИсточник: {item.source}\n\n<i>Status:</i> {item.status}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "NXT Esports Bot (editor mode)\n"
        "/postnow — собрать свежак и скинуть на ревью\n"
        "/queue — показать одобренные к публикации (админ)\n"
        "/postapproved — опубликовать следующий одобренный\n"
        "/schedule_at YYYY-MM-DD HH:MM — запланировать следующий одобренный\n"
        "/schedule_text YYYY-MM-DD HH:MM | текст — запланировать кастомный пост\n"
        "/sources — активные источники\n"
        "/setfreq <минуты> — изменить период (админ)"
    )

async def sources_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = []
    for game, data in config.get("games", {}).items():
        txt.append(f"• {game}: RSS={len(data.get('rss', []))}, YT={len(data.get('youtube_channels', []))}")
    await update.message.reply_text("\n".join(txt))

async def setfreq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        minutes = int(context.args[0])
    except:
        await update.message.reply_text("Использование: /setfreq 120")
        return
    global FETCH_INTERVAL_MIN
    FETCH_INTERVAL_MIN = minutes
    await update.message.reply_text(f"Интервал обновлён: {minutes} мин.")

async def send_for_review(app: Application, item: Item):
    if not REVIEW_CHAT_ID:
        return
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve:{item.id}"),
            InlineKeyboardButton("⏭️ Пропустить", callback_data=f"skip:{item.id}")
        ],
        [
            InlineKeyboardButton("🆗 Постнуть сейчас", callback_data=f"postnow:{item.id}"),
            InlineKeyboardButton("📆 Запланировать +60м", callback_data=f"plan60:{item.id}")
        ]
    ])
    if item.image_url:
        await app.bot.send_photo(chat_id=REVIEW_CHAT_ID, photo=item.image_url, caption=fmt(item), parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await app.bot.send_message(chat_id=REVIEW_CHAT_ID, text=fmt(item), parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=False)

async def _send_to_channel(app: Application, item: Item):
    text = f"📰 <b>{item.title}</b>\n{item.summary}\n\nИсточник: {item.source}\n#nxtesports #киберспорт"
    if item.image_url:
        await app.bot.send_photo(chat_id=CHANNEL_ID, photo=item.image_url, caption=text, parse_mode=ParseMode.HTML)
    else:
        await app.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode=ParseMode.HTML)

async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    action, sid = data.split(":")
    session = SessionLocal()
    item = session.get(Item, int(sid))
    if not item:
        await query.edit_message_text("Элемент не найден.")
        session.close()
        return
    if action == "approve":
        item.status = "approved"
        session.commit()
        await query.edit_message_reply_markup(None)
        await query.edit_message_caption(caption=fmt(item), parse_mode=ParseMode.HTML) if item.image_url else await query.edit_message_text(fmt(item), parse_mode=ParseMode.HTML)
    elif action == "skip":
        item.status = "skipped"
        session.commit()
        await query.edit_message_reply_markup(None)
        await query.edit_message_caption(caption=fmt(item), parse_mode=ParseMode.HTML) if item.image_url else await query.edit_message_text(fmt(item), parse_mode=ParseMode.HTML)
    elif action == "postnow":
        await _send_to_channel(context.application, item)
        item.status = "posted"
        session.commit()
        await query.edit_message_reply_markup(None)
        await query.edit_message_caption(caption=fmt(item), parse_mode=ParseMode.HTML) if item.image_url else await query.edit_message_text(fmt(item), parse_mode=ParseMode.HTML)
    elif action == "plan60":
        run_time = datetime.utcnow() + timedelta(minutes=60)
        item.scheduled_at = run_time
        item.status = "approved"
        session.commit()
        context.job_queue.run_once(callback=scheduled_post_job, when=run_time, data={"item_id": item.id})
        await query.edit_message_reply_markup(None)
        await query.edit_message_caption(caption=fmt(item), parse_mode=ParseMode.HTML) if item.image_url else await query.edit_message_text(fmt(item), parse_mode=ParseMode.HTML)
    session.close()

async def scheduled_post_job(ctx):
    app = ctx.application
    data = ctx.job.data or {}
    item_id = data.get("item_id")
    session = SessionLocal()
    item = session.get(Item, item_id)
    if item and item.status in ("approved", "new"):
        await _send_to_channel(app, item)
        item.status = "posted"
        session.commit()
    session.close()

async def fetch_to_review(app: Application):
    config = load_config()
last_fetch_time = None
    session = SessionLocal()
    added = 0
    try:
        for game, data in config.get("games", {}).items():
            for url in data.get("rss", []):
                for it in parse_rss(url):
                    title = it["title"].strip()
                    url_ = it["url"].strip()
                    summary = it["summary"].strip()
                    image_url = it.get("image_url")
                    source = url.split('/')[2]
                    exists = session.query(Item).filter_by(url=url_).first()
                    if exists:
                        continue
                    rewritten = rewrite_text(f"{title}\n\n{summary}\n\nКратко перескажи для киберспортивного канала NXT Esports.")
                    item = Item(url=url_, title=title, summary=rewritten, source=source, image_url=image_url, status="new")
                    session.add(item); session.commit()
                    await send_for_review(app, item)
                    added += 1
            for ch in data.get("youtube_channels", []):
                items = parse_rss(youtube_channel_feed(ch))
                items = filter_highlights(items, config.get("filters", {}).get("highlight_keywords", []))
                for it in items:
                    title = it["title"].strip()
                    url_ = it["url"].strip()
                    image_url = it.get("image_url")
                    summary = f"🎥 Хайлайты: {title}\nСмотри видео: {url_}"
                    source = "YouTube"
                    exists = session.query(Item).filter_by(url=url_).first()
                    if exists:
                        continue
                    item = Item(url=url_, title=title, summary=summary, source=source, image_url=image_url, status="new")
                    session.add(item); session.commit()
                    await send_for_review(app, item)
                    added += 1
        logging.info("Fetched %s new items for review", added)
        global last_fetch_time
        last_fetch_time = dt.datetime.utcnow() if 'dt' in globals() else __import__('datetime').datetime.utcnow()
        if added == 0 and (REVIEW_CHAT_ID):
            try:
                await app.bot.send_message(chat_id=REVIEW_CHAT_ID, text="🔎 Новых материалов нет. Я всё проверил.")
            except Exception:
                pass
    finally:
        session.close()

async def postnow_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Собираю свежие материалы и кидаю в редакторский чат…")
    await fetch_to_review(context.application)
    await update.message.reply_text("Готово! Проверь редакторский чат.")

async def queue_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    session = SessionLocal()
    items = session.query(Item).filter(Item.status=="approved").order_by(Item.id.asc()).limit(10).all()
    session.close()
    if not items:
        await update.message.reply_text("Одобренных постов нет.")
        return
    txt = "\n\n".join([f"<b>{it.title}</b>\n{it.summary[:260]}…" for it in items])
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML)

async def postapproved_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = SessionLocal()
    item = session.query(Item).filter(Item.status=="approved").order_by(Item.id.asc()).first()
    if not item:
        await update.message.reply_text("Нет одобренных постов.")
        session.close()
        return
    await _send_to_channel(context.application, item)
    item.status = "posted"
    session.commit(); session.close()
    await update.message.reply_text("Опубликовано.")

def parse_dt_arg(arg1: str, arg2: str) -> datetime:
    return datetime.fromisoformat(f"{arg1} {arg2}")

async def schedule_at_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /schedule_at 2025-08-12 14:30")
        return
    when = parse_dt_arg(context.args[0], context.args[1])
    session = SessionLocal()
    item = session.query(Item).filter(Item.status=="approved").order_by(Item.id.asc()).first()
    if not item:
        await update.message.reply_text("Нет одобренных постов.")
        session.close()
        return
    item.scheduled_at = when
    session.commit(); session.close()
    context.job_queue.run_once(callback=scheduled_post_job, when=when, data={"item_id": item.id})
    await update.message.reply_text(f"Запланировал на {when}.")

async def schedule_text_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text[len("/schedule_text "):]
    if "|" not in raw:
        await update.message.reply_text("Использование: /schedule_text YYYY-MM-DD HH:MM | текст")
        return
    dt_part, text = raw.split("|", 1)
    dt_part = dt_part.strip()
    parts = dt_part.split()
    if len(parts) != 2:
        await update.message.reply_text("Неверный формат даты. Пример: 2025-08-12 14:30")
        return
    when = parse_dt_arg(parts[0], parts[1])
    async def post_custom(ctx):
        await ctx.application.bot.send_message(chat_id=CHANNEL_ID, text=text.strip(), parse_mode=ParseMode.HTML)
    context.job_queue.run_once(callback=post_custom, when=when)
    await update.message.reply_text(f"Запланировал кастомный пост на {when}.")

async def scheduler_job(app: Application):
    await fetch_to_review(app)



async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = SessionLocal()
    try:
        total = session.query(Item).count()
        counts = {}
        for st in (\"new\",\"approved\",\"posted\",\"skipped\"):
            counts[st] = session.query(Item).filter(Item.status==st).count()
        from datetime import datetime as _dt
        last = session.query(Item).order_by(Item.created_at.desc()).first()
        last_created = last.created_at.isoformat(sep=' ') if last else '—'
    finally:
        session.close()
    lf = (last_fetch_time.isoformat(sep=' ') if 'last_fetch_time' in globals() and last_fetch_time else '—')
    await update.message.reply_text(
        f\"\"\"Статус бота:
Последний сбор: {lf}
Всего материалов в базе: {total}
new / approved / posted / skipped: {counts.get('new',0)} / {counts.get('approved',0)} / {counts.get('posted',0)} / {counts.get('skipped',0)}
Интервал парсинга: {FETCH_INTERVAL_MIN} мин.
KeepAlive: {'включен' if KEEPALIVE_ENABLED else 'выключен'} ({KEEPALIVE_INTERVAL_SEC} сек)
Последний добавленный материал: {last_created}
\"\"\".strip())

async def keepalive_job(app: Application):
    try:
        await app.bot.get_me()
        logging.debug(\"keepalive ping ok\")
    except Exception as e:
        logging.warning(\"keepalive ping failed: %s\", e)

async def main():
    await start_health_server()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sources", sources_cmd))
    app.add_handler(CommandHandler("postnow", postnow_cmd))
    app.add_handler(CommandHandler("queue", queue_cmd))
    app.add_handler(CommandHandler("postapproved", postapproved_cmd))
    app.add_handler(CommandHandler("schedule_at", schedule_at_cmd))
    app.add_handler(CommandHandler("schedule_text", schedule_text_cmd))
    app.add_handler(CommandHandler("setfreq", setfreq))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(CommandHandler("status", status_cmd))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: asyncio.create_task(scheduler_job(app)), "interval", minutes=FETCH_INTERVAL_MIN)
    if KEEPALIVE_ENABLED:
        scheduler.add_job(lambda: asyncio.create_task(keepalive_job(app)), "interval", seconds=KEEPALIVE_INTERVAL_SEC)
    scheduler.start()

    print("Bot is running (editor mode, media enabled). Ctrl+C to stop.")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
