from app.services.normalize import parse_frequency, normalize_drug, match_strip, review_status

def test_frequency_aliases_and_invalid():
    assert parse_frequency("1-0-1") == "1-0-1-0"
    assert parse_frequency("BD") == "1-0-1-0"
    assert parse_frequency("TDS") == "1-1-1-0"
    assert parse_frequency("HS") == "0-0-0-1"
    assert parse_frequency("garbage") is None

def test_drug_thresholds():
    assert normalize_drug("Paracetamol", .9, ["Paracetamol"])[0] == "Paracetamol"
    assert normalize_drug("Paracetamol medicine", .9, ["Paracetamol"])[1] <= .6
    assert normalize_drug("zzzz", .9, ["Paracetamol"])[1] <= .3

def test_strip_status_and_review_guardrail():
    assert match_strip("Paracetamol", "500 mg", [{"printed_drug_name":"Paracetamol", "printed_strength":"500 mg", "image_id":"x"}])[0] == "match"
    assert match_strip("Paracetamol", "250 mg", [{"printed_drug_name":"Paracetamol", "printed_strength":"500 mg", "image_id":"x"}])[0] == "mismatch"
    assert match_strip("Paracetamol", None, [{"printed_drug_name":"Paracetamol", "printed_strength":"500 mg", "image_id":"x"}])[0] == "uncertain"
    assert review_status("Paracetamol", .95, "1-0-1-0", .95, "after_food", .95, "none") == "auto_ok"
    assert review_status("Paracetamol", .95, "1-0-1-0", .95, None, 0, "none") == "needs_review"
