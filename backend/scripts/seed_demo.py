"""Create a clearly synthetic local demo case without making a model call."""
from sqlalchemy import select
from app.db import Base, SessionLocal, engine
from app.models import AuditLog, Case, Medicine
from app.services.schedule import build_reminders

Base.metadata.create_all(engine)
db = SessionLocal()
try:
    case = db.scalar(select(Case).where(Case.access_code == "DEMO01"))
    if case:
        print("Demo case already exists: DEMO01")
    else:
        case = Case(access_code="DEMO01", status="patient_confirmed", language="en", consent_given=True)
        db.add(case)
        db.flush()
        samples = [
            {"drug_name":"Paracetamol", "strength":"500 mg", "frequency_code":"1-0-1-0", "food_timing":"after_food", "duration_days":5},
            {"drug_name":"Metformin", "strength":"500 mg", "frequency_code":"1-0-1-0", "food_timing":"with_food", "duration_days":7},
            {"drug_name":"Pantoprazole", "strength":"40 mg", "frequency_code":"1-0-0-0", "food_timing":"before_food", "duration_days":7},
        ]
        for sample in samples:
            medicine = Medicine(case_id=case.id, source_text="Synthetic demo only; not a real prescription.", **sample, review_status="patient_confirmed", drug_name_conf=1, strength_conf=1, frequency_conf=1, food_timing_conf=1, duration_conf=1, strip_match_status="none")
            db.add(medicine)
            db.flush()
            db.add_all(build_reminders(case.id, medicine))
        db.add(AuditLog(case_id=case.id, actor="system", action="synthetic_demo_seeded", detail_json="{}"))
        db.commit()
        print("Created synthetic demo case: DEMO01")
finally:
    db.close()
