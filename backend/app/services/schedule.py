from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from app.config import settings
from app.models import ReminderJob
from app.services.normalize import SLOTS

SLOT_TIMES = {"morning": time(8), "afternoon": time(14), "evening": time(18), "night": time(21)}

def build_reminders(case_id: str, medicine, now: datetime | None = None) -> list[ReminderJob]:
    if medicine.as_needed or not medicine.frequency_code: return []
    tz = ZoneInfo(settings.timezone)
    current = (now or datetime.now(tz)).astimezone(tz)
    days = medicine.duration_days or 7
    codes = medicine.frequency_code.split("-")
    jobs = []
    for day_offset in range(days):
        date = (current + timedelta(days=day_offset)).date()
        for idx, slot in enumerate(SLOTS):
            if idx < len(codes) and codes[idx].isdigit() and int(codes[idx]) > 0:
                fire = datetime.combine(date, SLOT_TIMES[slot], tzinfo=tz)
                if fire <= current: continue
                jobs.append(ReminderJob(case_id=case_id, medicine_id=medicine.id, slot=slot, fire_at=fire.astimezone(ZoneInfo("UTC")), sent=False))
    return jobs
