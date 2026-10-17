from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db import Base, engine
from app.routers import cases
from apscheduler.schedulers.background import BackgroundScheduler
from threading import Thread
from app.services.notify import cleanup_expired, run_telegram_bot, send_due_reminders

app = FastAPI(title="Dawa Saathi API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(cases.router, prefix="/api")
scheduler = BackgroundScheduler(timezone=settings.timezone)
telegram_thread: Thread | None = None

@app.on_event("startup")
def create_tables() -> None:
    global telegram_thread
    Base.metadata.create_all(bind=engine)
    cleanup_expired()
    if not scheduler.running:
        scheduler.add_job(send_due_reminders, "interval", minutes=1, id="send-reminders", replace_existing=True)
        scheduler.add_job(cleanup_expired, "interval", hours=24, id="retention-cleanup", replace_existing=True)
        scheduler.start()
    if settings.telegram_bot_token and (telegram_thread is None or not telegram_thread.is_alive()):
        telegram_thread=Thread(target=run_telegram_bot,name="telegram-polling",daemon=True)
        telegram_thread.start()

@app.on_event("shutdown")
def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
