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

## Deploy to Vercel

Vercel detects this repository as FastAPI from `requirements.txt` and the
`app` object exported by the root-level `index.py` entry point. Leave the
Vercel Build Command and Output Directory settings empty so framework
detection can configure the deployment.

Commit and push the application files before redeploying:

```bash
git add .
git commit -m "Add FastAPI application"
git push origin main
```

The demo uses SQLite. On Vercel it is automatically stored in writable `/tmp`
space, which is ephemeral and can differ between function instances. Use a
managed database such as Postgres before relying on persistent production data
or sessions.
