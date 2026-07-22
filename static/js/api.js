/* Shared API client and small UI helpers. */
const API = {
  base: "/api/v1",
  async request(path, options = {}) {
    const res = await fetch(this.base + path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      credentials: "same-origin",
      ...options,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const data = await res.json();
        let d = data.detail !== undefined ? data.detail : data;
        if (Array.isArray(d)) d = d.map((x) => (x.msg || JSON.stringify(x))).join("; ");
        else if (typeof d === "object") d = JSON.stringify(d);
        if (d) detail = String(d);
      } catch (e) {}
      throw new Error(detail);
    }
    return res.json();
  },
  get(path) { return this.request(path); },
  post(path, body) { return this.request(path, { method: "POST", body: JSON.stringify(body) }); },
  put(path, body) { return this.request(path, { method: "PUT", body: JSON.stringify(body) }); },
  del(path) { return this.request(path, { method: "DELETE" }); },
};

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const c of [].concat(children)) {
    node.append(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return node;
}

function notify(container, message, ok = true) {
  container.innerHTML = "";
  container.append(el("div", { class: "notice " + (ok ? "ok" : "err") }, message));
}

/* Reusable job card template: every job card on the platform is rendered
   from this single function instead of separate pages per job. */
function jobCard(job, extras = null) {
  const card = el("article", {
    class: "card job-card reveal visible",
    tabindex: "0", role: "link", "aria-label": job.title + " at " + job.company,
    onclick: (e) => { if (!e.target.closest("a,button")) window.location.href = "/jobs/" + job.job_id; },
    onkeydown: (e) => { if (e.key === "Enter") window.location.href = "/jobs/" + job.job_id; },
  }, [
    el("div", { class: "title-row" }, [
      el("h3", {}, [el("a", { href: "/jobs/" + job.job_id }, job.title)]),
      extras && extras.score !== undefined
        ? el("span", { class: "score-pill" }, (extras.score * 100).toFixed(0) + "%")
        : "",
    ]),
    el("p", { class: "meta" }, `${job.company} - ${job.location} - ${job.job_type} - ${job.salary_range}`),
    el("div", { class: "chips" }, job.skills.map((s) => el("span", { class: "chip" }, s))),
  ]);
  card.append(el("div", { class: "card-actions" }, [
    el("a", { class: "btn btn-primary btn-sm", href: "/jobs/" + job.job_id }, "View & apply"),
    extras && extras.applied ? el("span", { class: "applied-badge" }, "Applied") : "",
  ]));
  if (extras && (extras.matched || extras.missing)) {
    card.append(el("div", { class: "chips" }, [
      ...(extras.matched || []).map((s) => el("span", { class: "chip match" }, "have " + s)),
      ...(extras.missing || []).map((s) => el("span", { class: "chip miss" }, "need " + s)),
    ]));
  }
  return card;
}

/* Scroll reveal animation */
document.addEventListener("DOMContentLoaded", () => {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((e) => e.isIntersecting && e.target.classList.add("visible"));
  }, { threshold: 0.12 });
  document.querySelectorAll(".reveal").forEach((n) => observer.observe(n));

  API.get("/auth/me").then((me) => {
    document.querySelectorAll("[data-auth=out]").forEach((n) => (n.style.display = "none"));
    document.querySelectorAll("[data-auth=in]").forEach((n) => (n.style.display = ""));
    if (me.role === "admin")
      document.querySelectorAll("[data-auth=admin]").forEach((n) => (n.style.display = ""));
  }).catch(() => {});
});

async function logout() {
  await API.post("/auth/logout", {});
  window.location.href = "/";
}

/* Mobile navigation toggle (hamburger menu) */
function toggleNav() {
  const links = document.getElementById("nav-links");
  const btn = document.getElementById("nav-toggle");
  if (!links) return;
  const open = links.classList.toggle("open");
  if (btn) btn.setAttribute("aria-expanded", open ? "true" : "false");
}

/* Render cleaned AI output as structured HTML: headings, numbered points
   and dash bullets instead of one raw text block. */
function aiBlock(container, text) {
  container.innerHTML = "";
  const box = el("div", { class: "ai-output structured" });
  let list = null;
  const flush = () => { if (list) { box.append(list); list = null; } };
  String(text).split("\n").forEach((raw) => {
    const line = raw.trim();
    if (!line) { flush(); return; }
    const numbered = line.match(/^(\d+)[.)]\s*(.+)/);
    const dashed = line.match(/^[-\u2022]\s*(.+)/);
    const heading = !numbered && !dashed && line.length < 70 && /[:：]$/.test(line);
    if (numbered) {
      if (!list || list.tagName !== "OL") { flush(); list = el("ol"); }
      list.append(el("li", {}, numbered[2]));
    } else if (dashed) {
      if (!list || list.tagName !== "UL") { flush(); list = el("ul"); }
      list.append(el("li", {}, dashed[1]));
    } else if (heading) {
      flush(); box.append(el("h4", {}, line.replace(/[:：]$/, "")));
    } else {
      flush(); box.append(el("p", {}, line));
    }
  });
  flush();
  container.append(box);
}
function loading(container, label = "Working") {
  container.innerHTML = "";
  container.append(el("p", { class: "meta" }, [el("span", { class: "spinner" }), " " + label + "..."]));
}
