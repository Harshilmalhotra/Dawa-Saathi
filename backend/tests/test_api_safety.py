from fastapi.testclient import TestClient
from app.main import app
from app.db import Base, engine, SessionLocal
from app.models import Case, Medicine
from app.models import Image
from app.routers import cases as cases_router
from uuid import uuid4

client = TestClient(app)

def test_consent_required():
    response = client.post("/api/cases", json={"language": "en", "consent_given": False})
    assert response.status_code == 400

def test_unread_ai_case_hides_results():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    case = Case(access_code="ABC123", consent_given=True, status="extracting")
    db.add(case); db.flush()
    db.add(Medicine(case_id=case.id, source_text="secret", drug_name="secret drug")); db.commit()
    response = client.get("/api/cases/by-code/ABC123")
    assert response.status_code == 200 and "medicines" not in response.json()
    db.delete(case); db.commit(); db.close()

def test_patient_cannot_acknowledge_uncertain_ai_reading():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    case = Case(access_code="QWE123", consent_given=True, status="ai_ready")
    db.add(case); db.flush()
    db.add(Medicine(case_id=case.id, source_text="raw", drug_name="Unclear", review_status="needs_review")); db.commit()
    case_id = case.id; db.close()
    try:
        response = client.post(f"/api/cases/{case_id}/self-confirm", headers={"X-Access-Code": "QWE123"})
        assert response.status_code == 409
        payload = client.get("/api/cases/by-code/QWE123").json()
        assert payload["medicines"][0]["review_status"] == "needs_review"
    finally:
        db = SessionLocal(); case = db.get(Case, case_id)
        if case: db.delete(case); db.commit()
        db.close()

def test_patient_cannot_access_schedule_before_acknowledgement():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    case = Case(access_code="XYZ789", consent_given=True, status="ai_ready")
    db.add(case); db.commit(); case_id=case.id; db.close()
    try:
        assert client.get(f"/api/cases/{case_id}/schedule").status_code == 409
    finally:
        db=SessionLocal(); case=db.get(Case,case_id)
        if case: db.delete(case); db.commit()
        db.close()

def test_case_submit_claims_one_extraction_and_polling_does_not_restart_it(monkeypatch):
    Base.metadata.create_all(engine)
    db = SessionLocal()
    code = uuid4().hex[:6].upper()
    case = Case(access_code=code, consent_given=True, status="uploaded")
    db.add(case); db.flush()
    db.add(Image(case_id=case.id, kind="prescription", storage_key="unused"))
    case_id = case.id; db.commit(); db.close()
    calls = []
    monkeypatch.setattr(cases_router.settings, "groq_api_key", "test-key")
    monkeypatch.setattr(cases_router, "run_case", lambda submitted_id: calls.append(submitted_id))
    try:
        first = client.post(f"/api/cases/{case_id}/submit")
        second = client.post(f"/api/cases/{case_id}/submit")
        client.get(f"/api/cases/by-code/{code}")
        client.get(f"/api/cases/by-code/{code}")
        assert first.status_code == 202
        assert second.status_code == 409
        assert calls == [case_id]
    finally:
        db = SessionLocal(); case = db.get(Case, case_id)
        if case: db.delete(case); db.commit()
        db.close()
