from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

from appv1 import queries
from appv1.сonfig import settings
from appv1.db_helper import db_helper
from appv1.queries import Service, Period

app = FastAPI(title="UTM Analytics", version="0.4.0")


async def exec_one(session, stmt):
    res = await session.execute(stmt)
    row = res.mappings().first()
    return dict(row) if row else {}


async def exec_all(session, stmt):
    res = await session.execute(stmt)
    return [dict(r) for r in res.mappings().all()]


@app.get("/", response_class=HTMLResponse)
async def index():
    base_url = settings.BASE_URL.rstrip("/")
    return f"""
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>UTM Analytics</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-900">
  <div class="max-w-6xl mx-auto p-6">
    <div class="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
      <div>
        <h1 class="text-2xl font-bold">UTM Analytics</h1>
        <p class="text-slate-600">BASE_URL: <code>{base_url}</code></p>
      </div>
      <div class="flex gap-2">
        <select id="service" class="border rounded-lg px-3 py-2 bg-white">
          <option value="rpp">RPP</option>
          <option value="farma">Farma</option>
        </select>
        <select id="period" class="border rounded-lg px-3 py-2 bg-white">
          <option value="day">day</option>
          <option value="week">week</option>
          <option value="month">month</option>
        </select>
        <button id="reload" class="rounded-lg px-4 py-2 bg-slate-900 text-white">Обновить</button>
      </div>
    </div>

    <div id="error" class="hidden mt-4 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200"></div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
      <div class="p-4 rounded-2xl bg-white shadow">
        <div class="text-slate-500">Всего пользователей</div>
        <div id="total_users" class="text-3xl font-bold mt-2">—</div>
      </div>
      <div class="p-4 rounded-2xl bg-white shadow">
        <div class="text-slate-500">UTM: с метками</div>
        <div id="with_utm" class="text-3xl font-bold mt-2">—</div>
        <div class="text-slate-500 mt-2">UTM: без меток</div>
        <div id="without_utm" class="text-2xl font-semibold mt-1">—</div>
      </div>
      <div class="p-4 rounded-2xl bg-white shadow">
        <div class="text-slate-500">Клики “получить файл”</div>
        <div id="file_clicks" class="text-3xl font-bold mt-2">—</div>
      </div>
    </div>

    <div id="segments_wrap" class="mt-6 hidden">
      <h2 class="text-xl font-bold mb-3">Сегменты (RPP)</h2>
      <div class="overflow-x-auto bg-white rounded-2xl shadow">
        <table class="min-w-full text-sm">
          <thead class="bg-slate-100">
            <tr>
              <th class="text-left p-3">segment</th>
              <th class="text-left p-3">users</th>
              <th class="text-left p-3">pct</th>
            </tr>
          </thead>
          <tbody id="segments" class="divide-y"></tbody>
        </table>
      </div>
    </div>

    <div class="mt-8">
      <h2 class="text-xl font-bold mb-3">Реакции по постам</h2>
      <div class="overflow-x-auto bg-white rounded-2xl shadow">
        <table class="min-w-full text-sm">
          <thead class="bg-slate-100">
            <tr>
              <th class="text-left p-3">post_id</th>
              <th class="text-left p-3">likes</th>
              <th class="text-left p-3">dislikes</th>
              <th class="text-left p-3">rating</th>
            </tr>
          </thead>
          <tbody id="posts" class="divide-y"></tbody>
        </table>
      </div>
    </div>

    <div class="mt-8">
      <h2 class="text-xl font-bold mb-3">Пожелания (последние)</h2>
      <div class="bg-white rounded-2xl shadow p-4">
        <ul id="wishes" class="space-y-2"></ul>
      </div>
    </div>
  </div>

<script>
const el = (id) => document.getElementById(id);

function fmt(n) {{
  if (n === null || n === undefined) return "—";
  try {{ return new Intl.NumberFormat("ru-RU").format(n); }} catch {{ return String(n); }}
}}

function showError(msg) {{
  const e = el("error");
  e.textContent = msg;
  e.classList.remove("hidden");
}}

function clearError() {{
  const e = el("error");
  e.textContent = "";
  e.classList.add("hidden");
}}

async function load() {{
  clearError();
  el("posts").innerHTML = "";
  el("wishes").innerHTML = "";
  el("segments").innerHTML = "";
  el("segments_wrap").classList.add("hidden");

  const service = el("service").value;
  const period = el("period").value;

  const r = await fetch(`/analytics?service=${{encodeURIComponent(service)}}&period=${{encodeURIComponent(period)}}`);
  if (!r.ok) {{
    showError(`Ошибка ${{r.status}}: ${{await r.text()}}`);
    return;
  }}
  const data = await r.json();

  el("total_users").textContent = fmt(data.total_users?.total_users);
  el("with_utm").textContent = fmt(data.utm_split?.with_utm);
  el("without_utm").textContent = fmt(data.utm_split?.without_utm);
  el("file_clicks").textContent = fmt(data.file_clicks?.clicks);

  if (service === "rpp" && Array.isArray(data.segments)) {{
    el("segments_wrap").classList.remove("hidden");
    for (const row of data.segments) {{
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="p-3">${{row.segment ?? ""}}</td>
        <td class="p-3">${{fmt(row.users)}}</td>
        <td class="p-3">${{fmt(row.pct)}}%</td>
      `;
      el("segments").appendChild(tr);
    }}
  }}

  if (Array.isArray(data.post_reactions)) {{
    for (const row of data.post_reactions.slice(0, 50)) {{
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="p-3">${{row.post_id ?? ""}}</td>
        <td class="p-3">${{fmt(row.likes)}}</td>
        <td class="p-3">${{fmt(row.dislikes)}}</td>
        <td class="p-3 font-semibold">${{fmt(row.rating)}}</td>
      `;
      el("posts").appendChild(tr);
    }}
  }}

  if (Array.isArray(data.wishes)) {{
    for (const w of data.wishes) {{
      const li = document.createElement("li");
      li.className = "p-3 rounded-xl bg-slate-50 border";
      li.innerHTML =
        `<div class="text-xs text-slate-500">${{w.timestamp ?? ""}}</div>` +
        `<div class="mt-1">${{(w.wish_text ?? "").replaceAll("<","&lt;")}}</div>`;
      el("wishes").appendChild(li);
    }}
  }}
}}

el("reload").addEventListener("click", load);
load();
</script>
</body>
</html>
"""


@app.get("/analytics")
async def analytics(
    service: Service = Query("rpp", pattern="^(rpp|farma)$"),
    period: Period = Query("day", pattern="^(day|week|month)$"),
):
    scoped = db_helper.get_scoped_session()
    session = scoped()
    try:
        total_users = await exec_one(session, queries.total_users(service))
        new_users = await exec_all(session, queries.new_users(service, period))
        utm_split = await exec_one(session, queries.utm_split(service))
        utm_timeseries = await exec_all(
            session, queries.utm_timeseries(service, period)
        )

        segments = None
        if service == "rpp":
            segments = await exec_all(session, queries.segments_rpp())

        post_reactions = await exec_all(session, queries.post_reactions(service))
        wishes = await exec_all(session, queries.wishes(service))

        file_clicks = await exec_one(session, queries.file_clicks(service))
        file_clicks_timeseries = await exec_all(
            session, queries.file_clicks_timeseries(service, period)
        )

        return {
            "service": service,
            "period": period,
            "total_users": total_users,
            "new_users": new_users,
            "utm_split": utm_split,
            "utm_timeseries": utm_timeseries,
            "segments": segments,
            "post_reactions": post_reactions,
            "wishes": wishes,
            "file_clicks": file_clicks,
            "file_clicks_timeseries": file_clicks_timeseries,
        }
    finally:
        await session.close()
        await scoped.remove()
