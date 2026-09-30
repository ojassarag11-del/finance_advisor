const $ = id => document.getElementById(id);
const inr = n => "₹" + Math.round(n).toLocaleString("en-IN");
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
$("month").value = new Date().toISOString().slice(0, 7);

const qs = () => `month=${$("month").value}&profile=${$("profile").value}&goal=${$("goal").value || 20}`;
const day = () => { const t = new Date().toISOString().slice(0, 10); return t.startsWith($("month").value) ? t : $("month").value + "-01"; };
const post = (url, body) => fetch(url, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});

async function load() {
  const s = await (await fetch("/api/summary?" + qs())).json();
  const cats = Object.keys(s.limits);
  $("stats").innerHTML = [
    ["Income", inr(s.income), ""], ["Expenses", inr(s.expenses), ""],
    ["Saved", inr(s.saved), s.saved < 0 ? "neg" : "pos"],
    ["Savings rate", s.income ? s.savings_rate.toFixed(1) + "%" : "–", s.savings_rate >= s.goal ? "pos" : "neg"]
  ].map(x => `<div class="card"><span class="mute">${x[0]}</span><b class="${x[2]}">${x[1]}</b></div>`).join("");

  $("budget").innerHTML = s.income ? cats.map(c => {
    const p = s.limits[c] ? s.by_category[c] / s.limits[c] * 100 : 0;
    return `<div class="cat"><span>${c}</span><span>${inr(s.by_category[c])} / ${inr(s.limits[c])}</span></div>
      <div class="bar"><i class="${p > 100 ? "over" : ""}" style="width:${Math.min(p, 100)}%"></i></div>`;
  }).join("") : `<p class="mute">Add income to see your budget.</p>`;

  $("incList").innerHTML = s.income_list.length ? `<table>${s.income_list.map(x =>
    `<tr><td>${x.day}</td><td>${esc(x.source)}</td><td>${inr(x.amount)}</td><td><button class="x" data-k="income" data-id="${x.id}">✕</button></td></tr>`).join("")}</table>` : `<p class="mute">No income yet.</p>`;
  $("expList").innerHTML = s.expense_list.length ? `<table>${s.expense_list.map(x =>
    `<tr><td>${x.day}</td><td>${x.category}</td><td>${esc(x.note)}</td><td>${inr(x.amount)}</td><td><button class="x" data-k="expenses" data-id="${x.id}">✕</button></td></tr>`).join("")}</table>` : `<p class="mute">No expenses yet.</p>`;

  const top = cats.filter(c => s.by_category[c] > 0).sort((a, b) => s.by_category[b] - s.by_category[a])[0];
  $("report").innerHTML = s.income || s.expenses
    ? `<p>In ${s.month} you earned ${inr(s.income)} and spent ${inr(s.expenses)}, leaving ${inr(s.saved)}. ${top ? "Biggest category: " + top + " (" + inr(s.by_category[top]) + ")." : ""}</p>
       <p>Next month, keep spending under ${inr(s.income * (1 - s.goal / 100))} to save ${inr(s.income * s.goal / 100)}.</p>`
    : `<p class="mute">Your report appears once you log data.</p>`;
  loadAdvice();
}

async function loadAdvice() {
  $("tips").textContent = "Thinking…";
  try {
    const a = await (await fetch("/api/advice?" + qs())).json();
    $("tips").innerHTML = a.tips.map(t => `<div class="tip">${esc(t)}</div>`).join("") +
      `<p class="mute">Source: ${a.source === "gemini" ? "Gemini AI" : "built-in rules (set GEMINI_API_KEY for AI advice)"}</p>`;
  } catch { $("tips").textContent = "Could not load advice."; }
}

$("addInc").onclick = async () => {
  const a = +$("iamt").value; if (!(a > 0)) return $("iamt").focus();
  await post("/api/income", {day: day(), source: $("isrc").value, amount: a});
  $("iamt").value = $("isrc").value = ""; load();
};
$("addExp").onclick = async () => {
  const a = +$("eamt").value; if (!(a > 0)) return $("eamt").focus();
  await post("/api/expenses", {day: day(), category: $("ecat").value, note: $("enote").value, amount: a});
  $("eamt").value = $("enote").value = ""; load();
};
document.addEventListener("click", async e => {
  const b = e.target.closest(".x"); if (!b) return;
  await fetch(`/api/${b.dataset.k}/${b.dataset.id}`, {method: "DELETE"}); load();
});
["month", "profile", "goal"].forEach(id => $(id).onchange = load);
$("refresh").onclick = loadAdvice;
load();
