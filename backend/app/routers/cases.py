import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_db
from app.models import AuditLog, Case, Image, Medicine, ReminderJob, TelegramLinkToken
from app.schemas import CaseCreate
from app.services.extraction import run_case
from app.services.schedule import build_reminders
from app.services.storage import read_image, save_upload

router = APIRouter(tags=["cases"])

@router.post("/cases")
def create_case(payload: CaseCreate, db: Session = Depends(get_db)):
    if not payload.consent_given: raise HTTPException(400, "Consent is required")
    case = Case(access_code=secrets.token_hex(3).upper(), language=payload.language, consent_given=True)
    db.add(case); db.commit(); db.refresh(case)
    db.add(AuditLog(case_id=case.id, actor="patient", action="consent_recorded", detail_json="{}")); db.commit()
    return {"case_id": case.id, "access_code": case.access_code}

@router.post("/cases/{case_id}/images", status_code=201)
async def upload_image(case_id: str, kind: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    case = db.get(Case, case_id)
    if not case or not case.consent_given: raise HTTPException(404, "Case not found")
    if case.status != "uploaded": raise HTTPException(409, "Images cannot be changed after submission")
    if kind not in {"prescription", "strip"}: raise HTTPException(400, "Invalid image kind")
    existing = db.scalars(select(Image).where(Image.case_id == case_id, Image.kind == kind)).all()
    if (kind == "prescription" and len(existing) >= 3) or (kind == "strip" and len(existing) >= 10): raise HTTPException(400, "Image limit reached")
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}: raise HTTPException(415, "Upload a JPG, PNG, or WEBP image")
    data = await file.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024: raise HTTPException(413, "Image exceeds 8 MB")
    try: key = save_upload(data, file.filename or "upload.jpg")
    except Exception: raise HTTPException(400, "Image could not be read")
    image = Image(case_id=case_id, kind=kind, storage_key=key); db.add(image); db.commit(); db.refresh(image)
    return {"image_id": image.id}

@router.post("/cases/{case_id}/submit", status_code=202)
def submit(case_id: str, tasks: BackgroundTasks, db: Session = Depends(get_db)):
    case = db.get(Case, case_id)
    if not case: raise HTTPException(404, "Case not found")
    if not db.scalar(select(Image.id).where(Image.case_id == case_id, Image.kind == "prescription")): raise HTTPException(400, "Add a prescription image first")
    if not settings.groq_api_key:
        raise HTTPException(503, "AI reading is not configured. Add GROQ_API_KEY to the repository-root .env, then restart the backend.")
    claim = db.execute(update(Case).where(Case.id == case_id, Case.status == "uploaded").values(status="extracting"))
    if claim.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Case has already been submitted")
    db.commit()
    tasks.add_task(run_case, case_id)
    return {"status": "extracting"}

def _patient_payload(db: Session, case: Case):
    medicines = db.scalars(select(Medicine).where(Medicine.case_id == case.id)).all()
    jobs = db.scalars(select(ReminderJob).where(ReminderJob.case_id == case.id).order_by(ReminderJob.fire_at)).all()
    tz=ZoneInfo(settings.timezone)
    now=datetime.now(timezone.utc)
    remaining: dict[str,set[str]]={}
    for job in jobs:
        fire=job.fire_at if job.fire_at.tzinfo else job.fire_at.replace(tzinfo=timezone.utc)
        if fire > now: remaining.setdefault(job.medicine_id,set()).add(fire.astimezone(tz).date().isoformat())
    medicine_values=[]
    for medicine in medicines:
        value={k:v for k,v in medicine.__dict__.items() if not k.startswith("_")}
        value["days_remaining"]=len(remaining.get(medicine.id,set()))
        value["duration_not_specified"]=medicine.duration_days is None
        medicine_values.append(value)
    return {"medicines": medicine_values, "schedule": [{"slot": j.slot, "medicine_id": j.medicine_id, "fire_at": j.fire_at.isoformat()} for j in jobs], "doctor_notes_text": case.doctor_notes_text}

@router.get("/cases/by-code/{access_code}")
def by_code(access_code: str, db: Session = Depends(get_db)):
    case = db.scalar(select(Case).where(Case.access_code == access_code.upper()))
    if not case: raise HTTPException(404, "Case not found")
    result = {"case_id": case.id, "access_code": case.access_code, "status": case.status, "language": case.language}
    if case.status in {"ai_ready", "patient_confirmed"}: result.update(_patient_payload(db, case))
    return result

@router.post("/cases/{case_id}/self-confirm")
def self_confirm(case_id: str, x_access_code: str | None = Header(default=None), db: Session = Depends(get_db)):
    case = db.get(Case, case_id)
    if not case: raise HTTPException(404, "Case not found")
    if not x_access_code or x_access_code.upper() != case.access_code: raise HTTPException(403, "Case access code required")
    if case.status != "ai_ready": raise HTTPException(409, "This AI reading is not ready for confirmation")
    medicines = db.scalars(select(Medicine).where(Medicine.case_id == case_id)).all()
    if not medicines or any(m.review_status != "auto_ok" for m in medicines):
        raise HTTPException(409, "Some fields are unclear. Do not use this reading as medicine instructions; check with your prescriber.")
    for medicine in medicines:
        medicine.review_status = "patient_confirmed"
        db.add_all(build_reminders(case_id, medicine))
    case.status = "patient_confirmed"
    db.add(AuditLog(case_id=case_id, actor="patient", action="ai_reading_self_confirmed", detail_json="{}"))
    db.commit()
    if case.telegram_chat_id:
        from app.services.notify import send_schedule_ready
        send_schedule_ready(case.telegram_chat_id, case.language)
    return {"status": case.status}

@router.get("/cases/{case_id}/schedule")
def schedule(case_id: str, db: Session = Depends(get_db)):
    case = db.get(Case, case_id)
    if not case: raise HTTPException(404, "Case not found")
    if case.status != "patient_confirmed": raise HTTPException(409, "Schedule is not acknowledged")
    return _patient_payload(db, case)

@router.post("/cases/{case_id}/telegram-link")
def telegram_link(case_id: str, db: Session = Depends(get_db)):
    from app.config import settings
    case = db.get(Case, case_id)
    if not case: raise HTTPException(404, "Case not found")
    if case.status != "patient_confirmed": raise HTTPException(409, "Acknowledge the AI reading before connecting reminders")
    if not settings.telegram_bot_username: raise HTTPException(503, "Telegram is not configured")
    token = secrets.token_urlsafe(24)
    db.add(TelegramLinkToken(token=token,case_id=case_id,expires_at=datetime.now(timezone.utc)+timedelta(minutes=15),used=False)); db.commit()
    return {"url": f"https://t.me/{settings.telegram_bot_username}?start={token}"}

@router.get("/images/{image_id}")
def get_image(image_id: str, x_access_code: str | None = Header(default=None), db: Session = Depends(get_db)):
    image = db.get(Image, image_id)
    if not image: raise HTTPException(404, "Image not found")
    case = db.get(Case, image.case_id)
    if not case or x_access_code != case.access_code: raise HTTPException(403, "Access code required")
    return Response(read_image(image.storage_key), media_type="image/jpeg")
