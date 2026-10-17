import json
import logging
from sqlalchemy import select
from app.db import SessionLocal
from app.models import AuditLog, Case, Image, Medicine
from app.services.groq import GroqAPIError, extract_prescription, extract_strip
from app.services.normalize import match_strip, normalize_drug, parse_frequency, review_status

logger = logging.getLogger(__name__)

def run_case(case_id: str) -> None:
    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        if not case: return
        if case.status != "extracting":
            return
        images = db.scalars(select(Image).where(Image.case_id == case_id)).all()
        prescription = [i.storage_key for i in images if i.kind == "prescription"]
        if not prescription: raise ValueError("No prescription image uploaded")
        strips = []
        for image in images:
            if image.kind == "strip":
                value = extract_strip(image.storage_key).model_dump()
                value["image_id"] = image.id; strips.append(value)
        result = extract_prescription(prescription)
        case.doctor_notes_text = None
        db.query(Medicine).filter(Medicine.case_id == case_id).delete()
        for row in result.medicines:
            uncertain = set(row.uncertain_fields)
            if row.drug_name is None or "drug_name" in uncertain: row.drug_name_conf = 0.0
            if row.strength is None or "strength" in uncertain: row.strength_conf = 0.0
            if row.frequency_code is None or "frequency_code" in uncertain: row.frequency_conf = 0.0
            if row.food_timing is None or "food_timing" in uncertain: row.food_timing_conf = 0.0
            if row.duration_days is None or "duration_days" in uncertain: row.duration_conf = 0.0
            name, name_conf, _ = normalize_drug(row.drug_name, row.drug_name_conf)
            frequency = None if row.as_needed else parse_frequency(row.frequency_code)
            frequency_conf = row.frequency_conf if frequency else 0.0
            duration = row.duration_days if row.duration_days and row.duration_days > 0 else None
            duration_conf = row.duration_conf if duration is not None else 0.0
            strip_status, strip_id = match_strip(name, row.strength, strips)
            status = review_status(name, name_conf, frequency, frequency_conf, row.food_timing, row.food_timing_conf, strip_status)
            db.add(Medicine(case_id=case_id, source_text=row.source_text, drug_name=name, drug_name_conf=name_conf, strength=row.strength, strength_conf=row.strength_conf, frequency_code=frequency, frequency_conf=frequency_conf, as_needed=row.as_needed, food_timing=row.food_timing, food_timing_conf=row.food_timing_conf, duration_days=duration, duration_conf=duration_conf, matched_strip_image_id=strip_id, strip_match_status=strip_status, review_status=status))
        db.add(AuditLog(case_id=case_id, actor="system", action="extraction_completed", detail_json=json.dumps({"medicine_count": len(result.medicines)})))
        case.status = "ai_ready"; db.commit()
    except Exception as exc:
        db.rollback()
        case = db.get(Case, case_id)
        if case: case.status = "failed"; db.add(AuditLog(case_id=case_id, actor="system", action="extraction_failed", detail_json=json.dumps({"error_type": type(exc).__name__}))); db.commit()
        if isinstance(exc, GroqAPIError):
            logger.warning("Case extraction failed: %s", exc)
        else:
            logger.warning("Case extraction failed (%s)", type(exc).__name__)
    finally:
        db.close()
