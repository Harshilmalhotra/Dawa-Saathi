import argparse
import json
from app.services.groq import extract_prescription

parser = argparse.ArgumentParser(description="Transcribe prescription images with a vision model via Groq")
parser.add_argument("images", nargs="+", help="Prescription image paths")
args = parser.parse_args()
print(json.dumps(extract_prescription(args.images).model_dump(), ensure_ascii=False, indent=2))
