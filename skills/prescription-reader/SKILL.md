---
name: prescription-reader
description: Transcribe handwritten prescription images into the Dawa Saathi extraction schema with confidence flags. Use when reading a prescription image; never infer unclear medicine instructions or generate medicine advice.
---

# Prescription reader

Read the supplied prescription image and return only JSON matching [`references/schema.json`](references/schema.json).

## Transcription procedure

1. Transcribe each medicine line exactly into `source_text`.
2. Extract the visible drug name, strength, four-slot morning-afternoon-evening-night frequency, food timing, and duration. Preserve explicit shorthand only when its meaning is stated in the schema instructions below.
3. Give each field a confidence from 0 to 1 based on legibility. Confidence reflects what is visible, not how plausible a medicine or dose seems.
4. Set an unclear or ambiguous field to `null`, with confidence from 0.0 to 0.4. Never fill a gap from common practice, context, or memory. Mark `as_needed` true only when the prescription explicitly indicates as-needed use such as SOS.
5. Set `overall_legibility` and transcribe general instructions into `doctor_notes_text`. Use `unknown` if the language hint is unclear.
6. Return no advice, diagnosis, warning, alternative, precaution, or inferred dose. Uncertain fields must remain null and must not be presented as usable instructions.

## Frequency and food notation

Use `Morning-Afternoon-Evening-Night` codes such as `1-0-1-0`. OD means once daily (morning only if the prescription does not specify a time); BD/BID means twice daily; TDS/TID means three times daily; QID means four times daily; HS means bedtime; SOS means as needed with a null frequency. AC means before food and PC means after food. Only map these abbreviations when the handwriting is legible.

For strip images, transcribe printed text only. Do not use strip appearance to infer a prescription instruction.
