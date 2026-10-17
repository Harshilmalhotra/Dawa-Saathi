import logging
from datetime import datetime, timedelta, timezone
import asyncio
from telegram import Bot, Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes
from sqlalchemy import select
from app.config import settings
from app.db import SessionLocal
from app.models import Case, Image, ReminderJob, TelegramLinkToken

logger = logging.getLogger(__name__)
SLOT_LABELS = {"en": {"morning":"Morning", "afternoon":"Afternoon", "evening":"Evening", "night":"Night"}, "hi": {"morning":"सुबह", "afternoon":"दोपहर", "evening":"शाम", "night":"रात"}, "mr": {"morning":"सकाळ", "afternoon":"दुपार", "evening":"संध्याकाळ", "night":"रात्र"}}

def _send(chat_id: str, text: str) -> bool:
    if not settings.telegram_bot_token: return False
    try:
        async def send() -> None:
            async with Bot(settings.telegram_bot_token) as bot:
                await bot.send_message(chat_id=chat_id,text=text)
        asyncio.run(send())
        return True
    except Exception as exc:
        logger.warning("Telegram send failed (%s)", type(exc).__name__)
        return False

def send_schedule_ready(chat_id: str, language: str) -> None:
    messages={"en":"Your reading is ready after you confirmed it.","hi":"आपकी पुष्टि के बाद दवा की जानकारी तैयार है।","mr":"तुमच्या पुष्टीनंतर औषधांची माहिती तयार आहे."}
    _send(chat_id,messages.get(language,messages["en"]))

def run_telegram_bot() -> None:
    if not settings.telegram_bot_token: return
    application: Application = ApplicationBuilder().token(settings.telegram_bot_token).build()

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_message or not update.effective_chat or not context.args: return
        token=context.args[0]
        db=SessionLocal()
        try:
            link=db.get(TelegramLinkToken,token)
            if not link or link.used: return
            expiry=link.expires_at
            if expiry.tzinfo is None: expiry=expiry.replace(tzinfo=timezone.utc)
            case=db.get(Case,link.case_id)
            if not case or expiry <= datetime.now(timezone.utc): return
            case.telegram_chat_id=str(update.effective_chat.id); link.used=True; db.commit()
            reply={"en":"Reminders are connected.","hi":"रिमाइंडर जुड़ गए हैं।","mr":"आठवणी जोडल्या आहेत."}.get(case.language,"Reminders are connected.")
            await update.effective_message.reply_text(reply)
        finally: db.close()

    async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_message or not update.effective_chat: return
        db=SessionLocal()
        try:
            case=db.scalar(select(Case).where(Case.telegram_chat_id==str(update.effective_chat.id)))
            if case:
                case.telegram_chat_id=None; db.commit()
                reply={"en":"Reminders are stopped.","hi":"रिमाइंडर बंद कर दिए गए हैं।","mr":"आठवणी बंद केल्या आहेत."}.get(case.language,"Reminders are stopped.")
                await update.effective_message.reply_text(reply)
        finally: db.close()

    application.add_handler(CommandHandler("start",start))
    application.add_handler(CommandHandler("stop",stop))
    application.run_polling(stop_signals=None)

def send_due_reminders() -> None:
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        due = db.scalars(select(ReminderJob).where(ReminderJob.sent.is_(False), ReminderJob.fire_at <= now).order_by(ReminderJob.fire_at)).all()
        grouped: dict[tuple[str,str], list[ReminderJob]] = {}
        for job in due: grouped.setdefault((job.case_id,job.slot), []).append(job)
        for (case_id,slot), jobs in grouped.items():
            case=db.get(Case,case_id)
            if not case or not case.telegram_chat_id: continue
            labels=SLOT_LABELS.get(case.language,SLOT_LABELS["en"])
            reminder={"en":"It is time to check your medicine schedule.","hi":"दवा का समय देखने का समय है।","mr":"औषधांचे वेळापत्रक पाहण्याची वेळ झाली आहे."}.get(case.language,"It is time to check your medicine schedule.")
            lines=[f"{labels.get(slot,slot.title())} ☀️",reminder]
            if _send(case.telegram_chat_id,"\n".join(lines)):
                for job in jobs: job.sent=True
        db.commit()
    finally:
        db.close()

def cleanup_expired() -> None:
    db=SessionLocal()
    try:
        cutoff=datetime.now(timezone.utc)-timedelta(days=settings.retention_days)
        cases=db.scalars(select(Case).where(Case.created_at < cutoff)).all()
        for case in cases:
            images=db.scalars(select(Image).where(Image.case_id==case.id)).all()
            for image in images:
                try:
                    if settings.storage_backend == "s3":
                        import boto3
                        boto3.client("s3",endpoint_url=settings.s3_endpoint,region_name=settings.s3_region,aws_access_key_id=settings.s3_key,aws_secret_access_key=settings.s3_secret).delete_object(Bucket=settings.s3_bucket,Key=image.storage_key)
                    else:
                        from pathlib import Path
                        Path(image.storage_key).unlink(missing_ok=True)
                except Exception as exc:
                    logger.warning("Image retention cleanup failed (%s)",type(exc).__name__)
            db.delete(case)
        db.commit()
    finally:
        db.close()
