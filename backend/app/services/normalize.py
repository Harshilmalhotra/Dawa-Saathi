import csv
import re
from pathlib import Path
from rapidfuzz import fuzz, process
from app.config import settings

SLOTS = ("morning", "afternoon", "evening", "night")

def parse_frequency(value: str | None) -> str | None:
    if not value: return None
    raw = value.strip().upper().replace(" ", "")
    aliases = {"OD": "1-0-0-0", "BD": "1-0-1-0", "BID": "1-0-1-0", "TDS": "1-1-1-0", "TID": "1-1-1-0", "QID": "1-1-1-1", "HS": "0-0-0-1"}
    if raw == "SOS": return None
    if raw in aliases: return aliases[raw]
    parts = raw.split("-")
    if len(parts) == 3 and all(p.isdigit() for p in parts): parts.append("0")
    if len(parts) == 4 and all(re.fullmatch(r"\d+", p) for p in parts): return "-".join(parts)
    return None

def medicine_names(path: str | Path | None = None) -> list[str]:
    file = Path(path) if path else Path(__file__).parents[1] / "data" / "medicines.csv"
    if not file.exists(): return []
    with file.open(encoding="utf-8", newline="") as handle: return [row["name"] for row in csv.DictReader(handle) if row.get("name")]

def normalize_drug(name: str | None, confidence: float, names: list[str] | None = None) -> tuple[str | None, float, bool]:
    if not name: return None, confidence, True
    choices = names if names is not None else medicine_names()
    found = process.extractOne(name, choices, scorer=fuzz.token_sort_ratio) if choices else None
    if not found: return name, min(confidence, 0.3), True
    canonical, score, _ = found
    if score >= 90: return canonical, confidence, False
    if score >= 70: return name, min(confidence, 0.6), True
    return name, min(confidence, 0.3), True

def match_strip(drug_name: str | None, strength: str | None, strips: list[dict]) -> tuple[str, str | None]:
    if not strips: return "none", None
    if not drug_name: return "uncertain", None
    candidates = [(s.get("printed_drug_name") or "", s) for s in strips]
    found = process.extractOne(drug_name, [x[0] for x in candidates], scorer=fuzz.token_sort_ratio)
    if not found: return "uncertain", None
    _, score, index = found
    strip = candidates[index][1]
    if score >= 85:
        if not strength or not strip.get("printed_strength"): return "uncertain", strip.get("image_id")
        if re.sub(r"\s", "", strength).lower() != re.sub(r"\s", "", strip["printed_strength"]).lower(): return "mismatch", strip.get("image_id")
        return "match", strip.get("image_id")
    return "uncertain", strip.get("image_id")

def review_status(drug_name: str | None, drug_conf: float, frequency: str | None, frequency_conf: float, food: str | None, food_conf: float, strip_status: str) -> str:
    threshold = settings.confidence_threshold
    return "auto_ok" if drug_name and frequency and food and min(drug_conf, frequency_conf, food_conf) >= threshold and strip_status not in {"mismatch", "uncertain"} else "needs_review"
