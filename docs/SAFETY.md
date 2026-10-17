# Safety and known limitations

- Patient consent is required before a case and image upload are accepted.
- The vision model transcribes visible writing; it must not diagnose, recommend alternatives, fill gaps, or create medicine precautions.
- Model output is validated against Pydantic schemas; extra fields are discarded. Unclear fields remain null with low confidence.
- AI output is labelled unverified. The API only permits schedule acknowledgement when required fields meet the configured confidence rule; the acknowledgement is by the patient and is not clinician verification.
- If a field is unclear, the UI blocks schedule creation and advises the patient not to rely on the AI reading.
- Telegram reminders contain no medicine names or prescription details and can only be linked after acknowledgement.
- Images and associated case data are scheduled for deletion after 30 days. Image content and full prescription text are not logged.

Known limitations: handwriting recognition can be wrong even at high confidence; confidence is not proof of correctness. Self-acknowledgement can miss an error and is not a substitute for review by the prescribing clinician. The model does not generate precautions because medication-specific safety advice cannot be safely inferred from an image. Hindi/Marathi voice quality varies by device. This is not a certified medical device.
