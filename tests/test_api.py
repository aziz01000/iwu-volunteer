from datetime import datetime, timedelta, timezone

from app.database import get_db
from tests.conftest import login


def test_invalid_login(client):
    res = client.post("/api/auth/login", json={"email": "not-an-email", "password": "x"})
    assert res.status_code == 422
    res = client.post("/api/auth/login", json={"email": "maya@demo.test", "password": "wrong"})
    assert res.status_code == 401


def test_profile_validation(client):
    headers = login(client, "maya@demo.test")
    res = client.put(
        "/api/profile",
        json={"bio": "hi", "skills": [], "availability": ["weekends"], "location": "Bloomington", "interests": []},
        headers=headers,
    )
    assert res.status_code == 422
    res = client.put(
        "/api/profile",
        json={"bio": "hi", "skills": ["packing"], "availability": [], "location": "B", "interests": []},
        headers=headers,
    )
    assert res.status_code == 422


def test_coordinator_cannot_edit_profile(client):
    headers = login(client, "jordan@demo.test")
    res = client.put(
        "/api/profile",
        json={"bio": "no", "skills": ["packing"], "availability": ["weekends"], "location": "Bloomington", "interests": []},
        headers=headers,
    )
    assert res.status_code == 403


def test_recommendations_show_demo_mode(client):
    headers = login(client, "maya@demo.test")
    res = client.get("/api/recommendations", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "demo"
    titles = {item["title"]: item for item in body["items"]}
    assert titles["Weekend Food Sort"]["eligible"] is True
    assert titles["Community Garden Shift"]["eligible"] is False
    assert titles["Clinic Intake Desk"]["eligible"] is False


def test_duplicate_and_full_and_ineligible_requests(client):
    headers = login(client, "maya@demo.test")
    recs = client.get("/api/recommendations", headers=headers).json()["items"]
    food = next(i for i in recs if i["title"] == "Weekend Food Sort")
    garden = next(i for i in recs if i["title"] == "Community Garden Shift")
    clinic = next(i for i in recs if i["title"] == "Clinic Intake Desk")

    first = client.post("/api/requests", json={"opportunity_id": food["id"]}, headers=headers)
    assert first.status_code == 200
    dup = client.post("/api/requests", json={"opportunity_id": food["id"]}, headers=headers)
    assert dup.status_code == 409
    full = client.post("/api/requests", json={"opportunity_id": garden["id"]}, headers=headers)
    assert full.status_code == 409
    ineligible = client.post("/api/requests", json={"opportunity_id": clinic["id"]}, headers=headers)
    assert ineligible.status_code == 400


def test_unauthorized_coordinator_cannot_approve(client):
    volunteer = login(client, "maya@demo.test")
    recs = client.get("/api/recommendations", headers=volunteer).json()["items"]
    food = next(i for i in recs if i["title"] == "Weekend Food Sort")
    created = client.post("/api/requests", json={"opportunity_id": food["id"]}, headers=volunteer).json()

    volunteer_try = client.post(f"/api/requests/{created['id']}/approve", headers=volunteer)
    assert volunteer_try.status_code == 403

    other_coord = login(client, "riley@demo.test")
    other_try = client.post(f"/api/requests/{created['id']}/approve", headers=other_coord)
    assert other_try.status_code == 403

    owner = login(client, "jordan@demo.test")
    ok = client.post(f"/api/requests/{created['id']}/approve", headers=owner)
    assert ok.status_code == 200
    assert ok.json()["status"] == "approved"


def test_assignment_complete_dashboard_and_audit(client):
    volunteer = login(client, "maya@demo.test")
    recs = client.get("/api/recommendations", headers=volunteer).json()["items"]
    food = next(i for i in recs if i["title"] == "Weekend Food Sort")
    created = client.post("/api/requests", json={"opportunity_id": food["id"]}, headers=volunteer).json()
    owner = login(client, "jordan@demo.test")
    client.post(f"/api/requests/{created['id']}/approve", headers=owner)

    assignments = client.get("/api/requests", headers=volunteer).json()["items"]
    assert assignments[0]["status"] == "approved"

    done = client.post(f"/api/requests/{created['id']}/complete", headers=volunteer)
    assert done.status_code == 200

    dash = client.get("/api/dashboard", headers=volunteer).json()
    assert dash["completed"] == 1
    assert dash["approved"] == 0

    audit = client.get("/api/audit", headers=volunteer).json()["items"]
    actions = [row["action"] for row in audit]
    assert "assignment_completed" in actions
    assert "request_created" in actions
    assert "login" in actions


def test_expired_session_is_rejected(client):
    res = client.post("/api/auth/login", json={"email": "maya@demo.test", "password": "demo1234"})
    token = res.json()["token"]
    expired = (datetime.now(timezone.utc) - timedelta(days=3)).replace(microsecond=0).isoformat()
    with get_db() as conn:
        conn.execute("UPDATE sessions SET created_at = ? WHERE token = ?", (expired, token))

    me = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 401


def test_profile_rejects_html_injection(client):
    headers = login(client, "maya@demo.test")
    res = client.put(
        "/api/profile",
        json={
            "bio": "<script>alert('x')</script>",
            "skills": ["packing"],
            "availability": ["weekends"],
            "location": "Bloomington",
            "interests": ["food security"],
        },
        headers=headers,
    )
    assert res.status_code == 200
    body = res.json()["profile"]
    assert "<script>" not in body["bio"].lower()
    assert body["bio"] == "alert('x')"

    bad = client.put(
        "/api/profile",
        json={
            "bio": "still safe",
            "skills": ["packing"],
            "availability": ["weekends"],
            "location": "<img src=x onerror=alert(1)>",
            "interests": ["food security"],
        },
        headers=headers,
    )
    assert bad.status_code == 422
