from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.database import get_db, json_dumps, json_loads
from app.matching import recommendation_mode, score_match
from app.security import new_token, now_iso, sanitize_list, sanitize_text, verify_password
from app.seed import seed_if_empty

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Neighborhood Match")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class LoginBody(BaseModel):
    email: str
    password: str


class ProfileBody(BaseModel):
    bio: str = Field(default="", max_length=500)
    skills: list[str]
    availability: list[str]
    location: str
    interests: list[str] = Field(default_factory=list)


class RequestBody(BaseModel):
    opportunity_id: int


def row_to_user(row) -> dict[str, Any]:
    return {"id": row["id"], "email": row["email"], "name": row["name"], "role": row["role"]}


def current_user(request: Request):
    header = request.headers.get("authorization") or ""
    if not header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sign in required")
    token = header.split(" ", 1)[1].strip()
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.email, u.name, u.role, s.created_at AS session_created_at
            FROM sessions s JOIN users u ON u.id = s.user_id
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Session expired")

    try:
        created_at = row["session_created_at"]
        if created_at:
            session_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            if session_dt.tzinfo is None:
                session_dt = session_dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - session_dt > timedelta(hours=24):
                with get_db() as conn:
                    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                raise HTTPException(status_code=401, detail="Session expired")
    except ValueError:
        with get_db() as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        raise HTTPException(status_code=401, detail="Session expired")

    return row_to_user(row)


def audit(actor_id: int | None, action: str, details: str) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT INTO audit (actor_id, action, details, created_at) VALUES (?, ?, ?, ?)",
            (actor_id, action, details, now_iso()),
        )


def profile_dict(row) -> dict[str, Any]:
    if not row:
        return {
            "bio": "",
            "skills": [],
            "availability": [],
            "location": "",
            "interests": [],
        }
    return {
        "bio": row["bio"],
        "skills": json_loads(row["skills"]),
        "availability": json_loads(row["availability"]),
        "location": row["location"],
        "interests": json_loads(row["interests"]),
    }


def opportunity_dict(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "required_skills": json_loads(row["required_skills"]),
        "availability": json_loads(row["availability"]),
        "location": row["location"],
        "capacity": row["capacity"],
        "filled": row["filled"],
        "remaining": row["capacity"] - row["filled"],
        "coordinator_id": row["coordinator_id"],
        "organization": row["organization"],
    }


def validate_profile(body: ProfileBody) -> None:
    location = sanitize_text(body.location)
    if len(location) < 2 or len(location) > 80:
        raise HTTPException(status_code=422, detail="Location must be 2–80 characters")
    skills = sanitize_list(body.skills)
    if not skills:
        raise HTTPException(status_code=422, detail="Choose at least one skill")
    availability = sanitize_list(body.availability)
    if not availability:
        raise HTTPException(status_code=422, detail="Choose at least one availability window")
    if len(sanitize_text(body.bio)) > 500:
        raise HTTPException(status_code=422, detail="Bio must be 500 characters or fewer")


@app.on_event("startup")
def on_startup() -> None:
    seed_if_empty()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": recommendation_mode()}


@app.post("/api/auth/login")
def login(body: LoginBody) -> dict[str, Any]:
    email = body.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Enter a valid email")
    if not body.password:
        raise HTTPException(status_code=422, detail="Password is required")
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not row or not verify_password(body.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Email or password is incorrect")
        token = new_token()
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, row["id"], now_iso()),
        )
        user = row_to_user(row)
    audit(user["id"], "login", f"{user['name']} signed in as {user['role']}")
    return {"token": token, "user": user}


@app.post("/api/auth/logout")
def logout(request: Request) -> dict[str, str]:
    header = request.headers.get("authorization") or ""
    token = header.split(" ", 1)[1].strip() if header.lower().startswith("bearer ") else ""
    if token:
        with get_db() as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    return {"status": "ok"}


@app.get("/api/me")
def me(request: Request) -> dict[str, Any]:
    return {"user": current_user(request), "mode": recommendation_mode()}


@app.get("/api/profile")
def get_profile(request: Request) -> dict[str, Any]:
    user = current_user(request)
    if user["role"] != "volunteer":
        raise HTTPException(status_code=403, detail="Profiles are for volunteers")
    with get_db() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user["id"],)).fetchone()
    return {"profile": profile_dict(row)}


@app.put("/api/profile")
def put_profile(request: Request, body: ProfileBody) -> dict[str, Any]:
    user = current_user(request)
    if user["role"] != "volunteer":
        raise HTTPException(status_code=403, detail="Only volunteers can edit a volunteer profile")

    clean_body = ProfileBody(
        bio=sanitize_text(body.bio),
        skills=sanitize_list(body.skills),
        availability=sanitize_list(body.availability),
        location=sanitize_text(body.location),
        interests=sanitize_list(body.interests),
    )
    validate_profile(clean_body)
    skills = clean_body.skills
    availability = clean_body.availability
    interests = clean_body.interests
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO profiles (user_id, bio, skills, availability, location, interests)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                bio=excluded.bio,
                skills=excluded.skills,
                availability=excluded.availability,
                location=excluded.location,
                interests=excluded.interests
            """,
            (
                user["id"],
                clean_body.bio,
                json_dumps(skills),
                json_dumps(availability),
                clean_body.location,
                json_dumps(interests),
            ),
        )
    audit(user["id"], "profile_update", "Volunteer profile saved")
    return {
        "profile": {
            "bio": clean_body.bio,
            "skills": skills,
            "availability": availability,
            "location": clean_body.location,
            "interests": interests,
        }
    }


@app.get("/api/recommendations")
def recommendations(request: Request) -> dict[str, Any]:
    user = current_user(request)
    if user["role"] != "volunteer":
        raise HTTPException(status_code=403, detail="Recommendations are for volunteers")
    with get_db() as conn:
        profile_row = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user["id"],)).fetchone()
        opp_rows = conn.execute("SELECT * FROM opportunities ORDER BY id").fetchall()
        existing = conn.execute(
            "SELECT opportunity_id, status FROM requests WHERE volunteer_id = ?",
            (user["id"],),
        ).fetchall()
    profile = profile_dict(profile_row)
    request_map = {r["opportunity_id"]: r["status"] for r in existing}
    items = []
    for row in opp_rows:
        opp = opportunity_dict(row)
        score, reasons, eligible = score_match(profile, opp)
        status = request_map.get(opp["id"])
        if status in {"pending", "approved", "completed"}:
            eligible = False
        items.append(
            {
                **opp,
                "score": score,
                "reasons": reasons,
                "eligible": eligible and status is None,
                "request_status": status,
            }
        )
    items.sort(key=lambda x: (-x["score"], x["title"]))
    mode = recommendation_mode()
    return {"mode": mode, "items": items}


@app.post("/api/requests")
def create_request(request: Request, body: RequestBody) -> dict[str, Any]:
    user = current_user(request)
    if user["role"] != "volunteer":
        raise HTTPException(status_code=403, detail="Only volunteers can request participation")
    with get_db() as conn:
        profile_row = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user["id"],)).fetchone()
        opp_row = conn.execute("SELECT * FROM opportunities WHERE id = ?", (body.opportunity_id,)).fetchone()
        if not opp_row:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        existing = conn.execute(
            """
            SELECT id, status FROM requests
            WHERE volunteer_id = ? AND opportunity_id = ?
              AND status IN ('pending', 'approved', 'completed')
            """,
            (user["id"], body.opportunity_id),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="You already have a request for this opportunity")
        opp = opportunity_dict(opp_row)
        score, reasons, eligible = score_match(profile_dict(profile_row), opp)
        if opp["remaining"] <= 0:
            raise HTTPException(status_code=409, detail="This opportunity is full")
        if not eligible:
            raise HTTPException(status_code=400, detail="You are not eligible for this opportunity")
        conn.execute(
            """
            INSERT INTO requests (volunteer_id, opportunity_id, status, created_at, updated_at)
            VALUES (?, ?, 'pending', ?, ?)
            """,
            (user["id"], body.opportunity_id, now_iso(), now_iso()),
        )
        req_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    audit(user["id"], "request_created", f"Requested {opp['title']}")
    return {"id": req_id, "status": "pending", "score": score, "reasons": reasons}


@app.get("/api/requests")
def list_requests(request: Request) -> dict[str, Any]:
    user = current_user(request)
    with get_db() as conn:
        if user["role"] == "volunteer":
            rows = conn.execute(
                """
                SELECT r.*, o.title, o.organization, o.location, o.capacity, o.filled
                FROM requests r JOIN opportunities o ON o.id = r.opportunity_id
                WHERE r.volunteer_id = ?
                ORDER BY r.id DESC
                """,
                (user["id"],),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT r.*, o.title, o.organization, o.location, o.capacity, o.filled,
                       u.name AS volunteer_name, u.email AS volunteer_email
                FROM requests r
                JOIN opportunities o ON o.id = r.opportunity_id
                JOIN users u ON u.id = r.volunteer_id
                WHERE o.coordinator_id = ?
                ORDER BY r.id DESC
                """,
                (user["id"],),
            ).fetchall()
    items = [dict(row) for row in rows]
    return {"items": items}


@app.post("/api/requests/{request_id}/approve")
def approve_request(request: Request, request_id: int) -> dict[str, Any]:
    user = current_user(request)
    if user["role"] != "coordinator":
        raise HTTPException(status_code=403, detail="Only coordinators can approve requests")
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT r.*, o.title, o.capacity, o.filled, o.coordinator_id
            FROM requests r JOIN opportunities o ON o.id = r.opportunity_id
            WHERE r.id = ?
            """,
            (request_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Request not found")
        if row["coordinator_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="You cannot act on another coordinator's opportunity")
        if row["status"] != "pending":
            raise HTTPException(status_code=409, detail="Only pending requests can be approved")
        if row["filled"] >= row["capacity"]:
            raise HTTPException(status_code=409, detail="This opportunity is full")
        conn.execute(
            "UPDATE requests SET status='approved', updated_at=? WHERE id=?",
            (now_iso(), request_id),
        )
        conn.execute(
            "UPDATE opportunities SET filled = filled + 1 WHERE id = ?",
            (row["opportunity_id"],),
        )
    audit(user["id"], "request_approved", f"Approved request for {row['title']}")
    return {"id": request_id, "status": "approved"}


@app.post("/api/requests/{request_id}/reject")
def reject_request(request: Request, request_id: int) -> dict[str, Any]:
    user = current_user(request)
    if user["role"] != "coordinator":
        raise HTTPException(status_code=403, detail="Only coordinators can reject requests")
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT r.*, o.title, o.coordinator_id
            FROM requests r JOIN opportunities o ON o.id = r.opportunity_id
            WHERE r.id = ?
            """,
            (request_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Request not found")
        if row["coordinator_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="You cannot act on another coordinator's opportunity")
        if row["status"] != "pending":
            raise HTTPException(status_code=409, detail="Only pending requests can be rejected")
        conn.execute(
            "UPDATE requests SET status='rejected', updated_at=? WHERE id=?",
            (now_iso(), request_id),
        )
    audit(user["id"], "request_rejected", f"Rejected request for {row['title']}")
    return {"id": request_id, "status": "rejected"}


@app.post("/api/requests/{request_id}/complete")
def complete_request(request: Request, request_id: int) -> dict[str, Any]:
    user = current_user(request)
    if user["role"] != "volunteer":
        raise HTTPException(status_code=403, detail="Only the assigned volunteer can mark completion")
    with get_db() as conn:
        row = conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Request not found")
        if row["volunteer_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="You can only complete your own assignment")
        if row["status"] != "approved":
            raise HTTPException(status_code=409, detail="Only confirmed assignments can be completed")
        conn.execute(
            "UPDATE requests SET status='completed', updated_at=? WHERE id=?",
            (now_iso(), request_id),
        )
        title = conn.execute(
            "SELECT title FROM opportunities WHERE id = ?",
            (row["opportunity_id"],),
        ).fetchone()["title"]
    audit(user["id"], "assignment_completed", f"Marked {title} completed")
    return {"id": request_id, "status": "completed"}


@app.get("/api/dashboard")
def dashboard(request: Request) -> dict[str, Any]:
    user = current_user(request)
    with get_db() as conn:
        if user["role"] == "volunteer":
            counts = conn.execute(
                """
                SELECT
                  SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending,
                  SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) AS approved,
                  SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed
                FROM requests WHERE volunteer_id = ?
                """,
                (user["id"],),
            ).fetchone()
        else:
            counts = conn.execute(
                """
                SELECT
                  SUM(CASE WHEN r.status='pending' THEN 1 ELSE 0 END) AS pending,
                  SUM(CASE WHEN r.status='approved' THEN 1 ELSE 0 END) AS approved,
                  SUM(CASE WHEN r.status='completed' THEN 1 ELSE 0 END) AS completed
                FROM requests r
                JOIN opportunities o ON o.id = r.opportunity_id
                WHERE o.coordinator_id = ?
                """,
                (user["id"],),
            ).fetchone()
    return {
        "role": user["role"],
        "pending": counts["pending"] or 0,
        "approved": counts["approved"] or 0,
        "completed": counts["completed"] or 0,
    }


@app.get("/api/audit")
def list_audit(request: Request) -> dict[str, Any]:
    user = current_user(request)
    with get_db() as conn:
        if user["role"] == "volunteer":
            rows = conn.execute(
                """
                SELECT a.*, u.name AS actor_name
                FROM audit a LEFT JOIN users u ON u.id = a.actor_id
                WHERE a.actor_id = ?
                ORDER BY a.id DESC LIMIT 50
                """,
                (user["id"],),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT a.*, u.name AS actor_name
                FROM audit a LEFT JOIN users u ON u.id = a.actor_id
                ORDER BY a.id DESC LIMIT 80
                """,
            ).fetchall()
    return {"items": [dict(row) for row in rows]}
