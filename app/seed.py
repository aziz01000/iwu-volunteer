from app.database import get_db, init_schema, json_dumps
from app.security import hash_password, now_iso

DEMO_PASSWORD = "demo1234"


def seed_if_empty() -> None:
    with get_db() as conn:
        init_schema(conn)
        count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        if count:
            return

        volunteer_hash = hash_password(DEMO_PASSWORD)
        coord_hash = hash_password(DEMO_PASSWORD)

        conn.execute(
            "INSERT INTO users (email, password_hash, name, role) VALUES (?, ?, ?, ?)",
            ("maya@demo.test", volunteer_hash, "Maya Chen", "volunteer"),
        )
        volunteer_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO profiles (user_id, bio, skills, availability, location, interests) VALUES (?, ?, ?, ?, ?, ?)",
            (
                volunteer_id,
                "Neighbor who wants regular, practical shifts.",
                json_dumps(["packing", "tutoring", "driving"]),
                json_dumps(["weekday evenings", "weekends"]),
                "Bloomington",
                json_dumps(["food security", "education"]),
            ),
        )

        conn.execute(
            "INSERT INTO users (email, password_hash, name, role) VALUES (?, ?, ?, ?)",
            ("jordan@demo.test", coord_hash, "Jordan Hale", "coordinator"),
        )
        food_coord = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute(
            "INSERT INTO users (email, password_hash, name, role) VALUES (?, ?, ?, ?)",
            ("riley@demo.test", coord_hash, "Riley Okonkwo", "coordinator"),
        )
        library_coord = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        opportunities = [
            (
                "Weekend Food Sort",
                "Sort donations and pack family boxes at the south pantry.",
                ["packing"],
                ["weekends"],
                "Bloomington",
                3,
                0,
                food_coord,
                "Heartland Food Bank",
            ),
            (
                "Pantry Deliveries",
                "Drive boxed groceries to neighbors without transport.",
                ["driving"],
                ["weekday evenings"],
                "Bloomington",
                2,
                0,
                food_coord,
                "Heartland Food Bank",
            ),
            (
                "After-school Tutoring",
                "Help middle-school students with reading and homework.",
                ["tutoring"],
                ["weekday evenings"],
                "Bloomington",
                2,
                0,
                library_coord,
                "County Library",
            ),
            (
                "Community Garden Shift",
                "Weed beds and harvest produce. Already fully staffed.",
                ["gardening"],
                ["weekends"],
                "Bloomington",
                1,
                1,
                food_coord,
                "Heartland Food Bank",
            ),
            (
                "Clinic Intake Desk",
                "Triage walk-in patients. Requires clinical credentials.",
                ["nursing", "cpr"],
                ["weekday evenings"],
                "Bloomington",
                2,
                0,
                library_coord,
                "County Library",
            ),
        ]
        for title, desc, skills, avail, loc, cap, filled, cid, org in opportunities:
            conn.execute(
                """
                INSERT INTO opportunities
                (title, description, required_skills, availability, location, capacity, filled, coordinator_id, organization)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (title, desc, json_dumps(skills), json_dumps(avail), loc, cap, filled, cid, org),
            )

        conn.execute(
            "INSERT INTO audit (actor_id, action, details, created_at) VALUES (?, ?, ?, ?)",
            (None, "seed", "Loaded demo users and opportunities", now_iso()),
        )
