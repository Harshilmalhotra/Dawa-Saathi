"""Evaluate extraction against a team-authored labels.json without logging image contents."""
import argparse
import json
from pathlib import Path
from app.services.groq import extract_prescription
from app.services.normalize import match_strip, normalize_drug, parse_frequency, review_status

parser = argparse.ArgumentParser()
parser.add_argument("image_dir", type=Path)
parser.add_argument("labels", type=Path)
args = parser.parse_args()
truth = json.loads(args.labels.read_text(encoding="utf-8"))
images = sorted(str(p) for p in args.image_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
prediction = extract_prescription(images)
fields = ("drug_name", "strength", "frequency_code", "food_timing", "duration_days")
counts = {field: [0, 0] for field in fields}
for index, expected in enumerate(truth.get("medicines", [])):
    if index >= len(prediction.medicines): continue
    actual = prediction.medicines[index].model_dump()
    for field in fields:
        counts[field][1] += 1
        counts[field][0] += actual.get(field) == expected.get(field)
for field, (correct, total) in counts.items():
    print(f"{field}: {correct}/{total} ({correct / total:.1%})" if total else f"{field}: no labels")
review_count = 0
for medicine in prediction.medicines:
    name, name_conf, _ = normalize_drug(medicine.drug_name, medicine.drug_name_conf)
    frequency = None if medicine.as_needed else parse_frequency(medicine.frequency_code)
    strip_status, _ = match_strip(name, medicine.strength, [])
    status = review_status(name, name_conf, frequency, medicine.frequency_conf if frequency else 0.0, medicine.food_timing, medicine.food_timing_conf, strip_status)
    review_count += status == "needs_review"
print(f"routed to review: {review_count}/{len(prediction.medicines)} ({review_count / len(prediction.medicines):.1%})" if prediction.medicines else "no medicines extracted")
