from datetime import datetime
from zoneinfo import ZoneInfo
from types import SimpleNamespace
from app.services.schedule import build_reminders

def test_two_daily_slots_for_five_days():
    medicine=SimpleNamespace(id="m1", as_needed=False, frequency_code="1-0-1-0", duration_days=5)
    now=datetime(2026,10,17,0,0,tzinfo=ZoneInfo("Asia/Kolkata"))
    jobs=build_reminders("c1",medicine,now)
    assert len(jobs)==10
    assert {job.slot for job in jobs}=={"morning","evening"}
