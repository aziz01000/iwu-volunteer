# Neighborhood Match

Local volunteer placement: profiles, eligibility-aware recommendations, coordinator approval, completion, and audit history.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000

Demo password for all seeded accounts: `demo1234`

- Volunteer: `maya@demo.test`
- Food bank coordinator: `jordan@demo.test`
- Library coordinator: `riley@demo.test`

Recommendations use **demo mode** unless `OPENAI_API_KEY` or `AI_API_KEY` is set.

## Tests

```bash
pytest
```
