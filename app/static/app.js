const SKILLS = ["packing", "tutoring", "driving", "gardening", "nursing", "cpr"];
const AVAIL = ["weekday evenings", "weekends", "weekday mornings"];
const INTERESTS = ["food security", "education", "health", "outdoors"];

const state = {
  token: localStorage.getItem("nm_token") || "",
  user: null,
  view: "login",
};

async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (opts.body && !(opts.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const res = await fetch(path, { ...opts, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail;
    const message = Array.isArray(detail)
      ? detail.map((d) => d.msg || d).join("; ")
      : detail || res.statusText;
    throw new Error(message);
  }
  return data;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function el(html) {
  const wrap = document.createElement("div");
  wrap.innerHTML = html.trim();
  return wrap.firstElementChild;
}

function renderNav() {
  const nav = document.getElementById("nav");
  if (!state.user) {
    nav.innerHTML = "";
    return;
  }
  const volunteer = state.user.role === "volunteer";
  const items = volunteer
    ? [
        ["profile", "Profile"],
        ["recommend", "Recommendations"],
        ["assignments", "Assignments"],
        ["dashboard", "Dashboard"],
        ["audit", "Audit"],
      ]
    : [
        ["inbox", "Requests"],
        ["dashboard", "Dashboard"],
        ["audit", "Audit"],
      ];
  nav.innerHTML = "";
  items.forEach(([id, label]) => {
    const btn = document.createElement("button");
    btn.textContent = label;
    btn.className = state.view === id ? "active" : "";
    btn.onclick = () => show(id);
    nav.appendChild(btn);
  });
  const out = document.createElement("button");
  out.textContent = "Sign out";
  out.className = "ghost";
  out.onclick = logout;
  nav.appendChild(out);
}

function show(view) {
  state.view = view;
  renderNav();
  const routes = {
    login: renderLogin,
    profile: renderProfile,
    recommend: renderRecommend,
    assignments: renderAssignments,
    inbox: renderInbox,
    dashboard: renderDashboard,
    audit: renderAudit,
  };
  routes[view]();
}

function renderLogin() {
  document.getElementById("view").innerHTML = `
    <section class="card">
      <h1>Sign in</h1>
      <p class="muted">Use a demo account or any seeded coordinator / volunteer.</p>
      <form id="login-form">
        <label for="email">Email</label>
        <input id="email" name="email" type="email" required />
        <label for="password">Password</label>
        <input id="password" name="password" type="password" required />
        <p id="login-error" class="error"></p>
        <div class="row-actions">
          <button class="primary" type="submit">Sign in</button>
        </div>
      </form>
      <div class="demo-box" style="margin-top:16px">
        <p class="muted">Demo accounts, password <code>demo1234</code></p>
        <div class="row-actions">
          <button class="ghost" type="button" data-fill="maya@demo.test">Volunteer: Maya Chen</button>
          <button class="ghost" type="button" data-fill="jordan@demo.test">Coordinator: Jordan Hale</button>
          <button class="ghost" type="button" data-fill="riley@demo.test">Coordinator: Riley Okonkwo</button>
        </div>
      </div>
    </section>
  `;
  document.querySelectorAll("[data-fill]").forEach((btn) => {
    btn.onclick = () => {
      document.getElementById("email").value = btn.dataset.fill;
      document.getElementById("password").value = "demo1234";
    };
  });
  document.getElementById("login-form").onsubmit = async (e) => {
    e.preventDefault();
    const err = document.getElementById("login-error");
    err.textContent = "";
    try {
      const body = {
        email: document.getElementById("email").value,
        password: document.getElementById("password").value,
      };
      const data = await api("/api/auth/login", { method: "POST", body: JSON.stringify(body) });
      state.token = data.token;
      state.user = data.user;
      localStorage.setItem("nm_token", data.token);
      show(data.user.role === "volunteer" ? "profile" : "inbox");
    } catch (ex) {
      err.textContent = ex.message;
    }
  };
}

async function logout() {
  try { await api("/api/auth/logout", { method: "POST" }); } catch (_) {}
  state.token = "";
  state.user = null;
  localStorage.removeItem("nm_token");
  show("login");
}

function chipGroup(name, options, selected) {
  return options
    .map(
      (opt) => `
      <label><input type="checkbox" name="${name}" value="${opt}" ${
        selected.includes(opt) ? "checked" : ""
      } /> ${opt}</label>`
    )
    .join("");
}

async function renderProfile() {
  const view = document.getElementById("view");
  view.innerHTML = `<section class="card"><h1>Volunteer profile</h1><p class="muted">Loading…</p></section>`;
  const { profile } = await api("/api/profile");
  view.innerHTML = `
    <section class="card">
      <h1>Volunteer profile</h1>
      <p class="muted">Signed in as ${state.user.name}. Recommendations use these skills and hours.</p>
      <form id="profile-form">
        <label for="location">Location</label>
        <input id="location" name="location" type="text" value="${escapeHtml(profile.location || "")}" />
        <label for="bio">Bio</label>
        <textarea id="bio" name="bio" rows="3">${escapeHtml(profile.bio || "")}</textarea>
        <label>Skills</label>
        <div class="chips">${chipGroup("skills", SKILLS, profile.skills || [])}</div>
        <label>Availability</label>
        <div class="chips">${chipGroup("availability", AVAIL, profile.availability || [])}</div>
        <label>Interests</label>
        <div class="chips">${chipGroup("interests", INTERESTS, profile.interests || [])}</div>
        <p id="profile-msg" class="muted" role="status" aria-live="polite"></p>
        <button class="primary" type="submit">Save profile</button>
      </form>
    </section>
  `;
  document.getElementById("profile-form").onsubmit = async (e) => {
    e.preventDefault();
    const msg = document.getElementById("profile-msg");
    const checked = (n) => [...document.querySelectorAll(`input[name="${n}"]:checked`)].map((i) => i.value);
    try {
      await api("/api/profile", {
        method: "PUT",
        body: JSON.stringify({
          location: document.getElementById("location").value,
          bio: document.getElementById("bio").value,
          skills: checked("skills"),
          availability: checked("availability"),
          interests: checked("interests"),
        }),
      });
      msg.className = "success";
      msg.textContent = "Profile saved.";
    } catch (ex) {
      msg.className = "error";
      msg.textContent = ex.message;
    }
  };
}

async function renderRecommend() {
  const view = document.getElementById("view");
  view.innerHTML = `<section class="card"><h1>Recommendations</h1><p class="muted">Loading…</p></section>`;
  const data = await api("/api/recommendations");
  const modeClass = data.mode === "ai" ? "ai" : "";
  const modeLabel = data.mode === "ai" ? "AI mode" : "Demo mode";
  view.innerHTML = `
    <section class="card">
      <h1>Recommended opportunities</h1>
      <p>Active ranking: <span class="badge ${modeClass}" data-testid="mode-badge">${modeLabel}</span>
        <span class="muted">${data.mode === "ai" ? "Hosted model ranking is enabled." : "Rule-based scoring. Set OPENAI_API_KEY to switch to AI ranking."}</span>
      </p>
    </section>
    <div class="grid" id="opp-grid"></div>
  `;
  const grid = document.getElementById("opp-grid");
  data.items.forEach((item) => {
    const card = el(`
      <article class="card">
        <h2>${escapeHtml(item.title)}</h2>
        <p class="muted">${escapeHtml(item.organization)} · ${escapeHtml(item.location)} · ${item.filled}/${item.capacity} filled</p>
        <p>${escapeHtml(item.description)}</p>
        <p class="muted">Score ${item.score}. ${escapeHtml(item.reasons.join(" · "))}</p>
        <p>${item.request_status ? `<span class="badge ${item.request_status === "approved" || item.request_status === "completed" ? "ok" : "pending"}">${escapeHtml(item.request_status)}</span>` : item.eligible ? '<span class="badge ok">eligible</span>' : '<span class="badge bad">not eligible</span>'}</p>
        <div class="row-actions"></div>
      </article>
    `);
    if (item.eligible) {
      const btn = document.createElement("button");
      btn.className = "primary";
      btn.textContent = "Request participation";
      btn.onclick = async () => {
        try {
          await api("/api/requests", {
            method: "POST",
            body: JSON.stringify({ opportunity_id: item.id }),
          });
          renderRecommend();
        } catch (ex) {
          alert(ex.message);
        }
      };
      card.querySelector(".row-actions").appendChild(btn);
    }
    grid.appendChild(card);
  });
}

async function renderAssignments() {
  const view = document.getElementById("view");
  const data = await api("/api/requests");
  view.innerHTML = `<section class="card"><h1>Your assignments</h1></section>`;
  const wrap = document.createElement("div");
  wrap.className = "grid";
  data.items.forEach((item) => {
    const card = el(`
      <article class="card">
        <h2>${escapeHtml(item.title)}</h2>
        <p class="muted">${escapeHtml(item.organization)} · ${escapeHtml(item.location)}</p>
        <p>Status: <span class="badge ${item.status === "approved" || item.status === "completed" ? "ok" : "pending"}" data-status="${escapeHtml(item.status)}">${escapeHtml(item.status)}</span></p>
        <div class="row-actions"></div>
      </article>
    `);
    if (item.status === "approved") {
      const btn = document.createElement("button");
      btn.className = "primary";
      btn.textContent = "Mark participation completed";
      btn.onclick = async () => {
        await api(`/api/requests/${item.id}/complete`, { method: "POST" });
        renderAssignments();
      };
      card.querySelector(".row-actions").appendChild(btn);
    }
    wrap.appendChild(card);
  });
  view.appendChild(wrap);
}

async function renderInbox() {
  const view = document.getElementById("view");
  const data = await api("/api/requests");
  view.innerHTML = `<section class="card"><h1>Participation requests</h1><p class="muted">You can only approve opportunities you coordinate.</p></section>`;
  const wrap = document.createElement("div");
  wrap.className = "grid";
  data.items.forEach((item) => {
    const card = el(`
      <article class="card">
        <h2>${escapeHtml(item.title)}</h2>
        <p class="muted">${escapeHtml(item.volunteer_name)} · ${escapeHtml(item.volunteer_email)}</p>
        <p>Status: <span class="badge">${escapeHtml(item.status)}</span> · ${item.filled}/${item.capacity} filled</p>
        <div class="row-actions"></div>
      </article>
    `);
    if (item.status === "pending") {
      const approve = document.createElement("button");
      approve.className = "primary";
      approve.textContent = "Approve";
      approve.onclick = async () => {
        try {
          await api(`/api/requests/${item.id}/approve`, { method: "POST" });
          renderInbox();
        } catch (ex) {
          alert(ex.message);
        }
      };
      const reject = document.createElement("button");
      reject.className = "danger";
      reject.textContent = "Reject";
      reject.onclick = async () => {
        await api(`/api/requests/${item.id}/reject`, { method: "POST" });
        renderInbox();
      };
      card.querySelector(".row-actions").appendChild(approve);
      card.querySelector(".row-actions").appendChild(reject);
    }
    wrap.appendChild(card);
  });
  if (!data.items.length) {
    wrap.innerHTML = `<section class="card"><p class="muted">No requests for your programs yet.</p></section>`;
  }
  view.appendChild(wrap);
}

async function renderDashboard() {
  const data = await api("/api/dashboard");
  document.getElementById("view").innerHTML = `
    <section class="grid">
      <article class="card"><p class="muted">Pending</p><p class="stat" data-testid="stat-pending">${data.pending}</p></article>
      <article class="card"><p class="muted">Confirmed</p><p class="stat" data-testid="stat-approved">${data.approved}</p></article>
      <article class="card"><p class="muted">Completed</p><p class="stat" data-testid="stat-completed">${data.completed}</p></article>
    </section>
  `;
}

async function renderAudit() {
  const data = await api("/api/audit");
  const rows = data.items
    .map(
      (item) =>
        `<tr><td>${item.created_at}</td><td>${item.actor_name || "system"}</td><td>${item.action}</td><td>${item.details}</td></tr>`
    )
    .join("");
  document.getElementById("view").innerHTML = `
    <section class="card">
      <h1>Audit history</h1>
      <table>
        <thead><tr><th>When</th><th>Who</th><th>Action</th><th>Details</th></tr></thead>
        <tbody>${rows || `<tr><td colspan="4">No events yet.</td></tr>`}</tbody>
      </table>
    </section>
  `;
}

async function boot() {
  if (state.token) {
    try {
      const me = await api("/api/me");
      state.user = me.user;
      show(me.user.role === "volunteer" ? "profile" : "inbox");
      return;
    } catch (_) {
      state.token = "";
      localStorage.removeItem("nm_token");
    }
  }
  show("login");
}

boot();
