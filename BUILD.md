# Build notes

Dawa Saathi is a React/Vite and FastAPI prescription transcription app. The vision-capable Qwen model is called through Groq's OpenAI-compatible chat completions endpoint; local images are sent as base64 data URLs.

## Local checks

- Backend: `cd backend`, `pip install -e '.[dev]'`, `alembic upgrade head`, then `pytest`.
- Frontend: `cd frontend`, `npm install`, `npm test`, then `npm run build`.
- Set `GROQ_API_KEY` and `GROQ_MODEL=qwen/qwen3.6-27b` in the repository-root `.env` before submitting a real image.
- Synthetic demo: from `backend`, run `python -m scripts.seed_demo`; lookup code `DEMO01`.

The app displays AI output as unverified transcription. High-confidence fields can be acknowledged by the patient after comparison with the paper. Unclear fields block schedule creation. It does not generate drug precautions or treatment advice.

External Groq, Telegram, PostgreSQL, DigitalOcean Spaces and deployment credentials are optional or require the project's own service accounts. Keep real patient images and secrets out of the repository.
