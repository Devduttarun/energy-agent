"""The live home view: plays a verified day in the browser, so it animates smoothly without Streamlit reruns.

render(record, paired) returns a self-contained HTML page (shown with components.html). The
clock runs through the day, speeding past quiet hours and slowing down before each action;
device cards switch on and off as the brain acts, and the feed says why, in the household's words.
"""
import html
import json

import household as home

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@700;800&display=swap" rel="stylesheet">
<style>
:root { --ink:#0E2A24; --muted:#5B6B67; --mint:#10B981; --cyan:#06B6D4; --line:rgba(14,42,36,.09); }
* { box-sizing:border-box; } body { margin:0; font-family:Inter,system-ui,sans-serif; color:var(--ink); background:transparent; }
.top { display:flex; align-items:center; gap:1rem; flex-wrap:wrap; }
.clock { font-family:'Plus Jakarta Sans',sans-serif; font-size:3rem; font-weight:800; letter-spacing:-.03em; line-height:1; min-width:9rem; }
.meta { display:flex; flex-direction:column; gap:.3rem; font-size:.85rem; color:var(--muted); }
.pill { display:inline-block; font-size:.74rem; font-weight:600; padding:.22rem .6rem; border-radius:999px; }
.pill.peak { background:rgba(245,158,11,.15); color:#92400E; } .pill.off { background:rgba(16,185,129,.13); color:#047857; }
.ctrl { margin-left:auto; display:flex; gap:.4rem; }
.ctrl button { font:600 .85rem Inter,sans-serif; border:1px solid var(--line); background:white; color:var(--ink);
  padding:.5rem .9rem; border-radius:999px; cursor:pointer; }
.ctrl button.on { background:linear-gradient(135deg,var(--mint),var(--cyan)); color:white; border:none; }
.stats { display:grid; grid-template-columns:repeat(4,1fr); gap:.7rem; margin:1rem 0; }
.stat { background:white; border:1px solid var(--line); border-radius:18px; padding:.8rem 1rem; }
.lbl { font-size:.68rem; font-weight:700; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); }
.val { font-family:'Plus Jakarta Sans',sans-serif; font-size:1.5rem; font-weight:800; margin-top:.2rem; }
.val small { font-size:.8rem; color:var(--muted); font-weight:600; }
.bar { position:relative; height:8px; border-radius:99px; background:#E8F0EE; margin-top:.45rem; }
.bar i { display:block; height:100%; border-radius:99px; background:linear-gradient(90deg,var(--mint),var(--cyan)); transition:width .2s; }
.bar b { position:absolute; top:-4px; width:2px; height:16px; background:#EF4444; }
.next { font-size:.95rem; font-weight:600; margin-top:.3rem; }
.main { display:grid; grid-template-columns:1.35fr 1fr; gap:1rem; }
.devices { display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr)); gap:.7rem; align-content:start; }
.dev { position:relative; background:white; border:1px solid var(--line); border-radius:20px; padding:1rem; transition:all .35s ease; overflow:hidden; }
.dev .ic { width:46px; height:46px; border-radius:14px; display:grid; place-items:center; font-size:1.45rem; background:#F1F5F4; transition:all .35s; }
.dev .nm { font-weight:600; font-size:.92rem; margin-top:.7rem; }
.dev .st { font-family:'Plus Jakarta Sans',sans-serif; font-weight:800; font-size:1.2rem; color:#94A3B8; text-transform:uppercase; }
.dev .via { font-size:.68rem; color:var(--muted); margin-top:.35rem; }
.dev .via.linked { color:#047857; font-weight:600; }
.dev .prog { height:5px; border-radius:99px; background:#E8F0EE; margin-top:.5rem; display:none; } .dev .prog i { display:block; height:100%; border-radius:99px; background:var(--mint); }
.dev.on { border-color:var(--glow); box-shadow:0 0 0 5px var(--halo), 0 14px 30px -16px var(--glow); }
.dev.on .ic { background:var(--halo); box-shadow:0 0 22px var(--glow); }
.dev.on .st { color:var(--deep); }
.dev.flash { animation:flash 1s ease; }
@keyframes flash { 0% { transform:scale(1); } 30% { transform:scale(1.04); } 100% { transform:scale(1); } }
.dev.spin.on .ic span { display:inline-block; animation:spin 1.2s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }
.dev > *:not(.curtain) { position:relative; z-index:1; }
.curtain { position:absolute; top:0; bottom:0; width:50%; z-index:0; background:repeating-linear-gradient(90deg,#E3ECEA 0 6px,#F4F8F7 6px 12px); transition:transform 1.2s ease; opacity:.45; pointer-events:none; }
.curtain.l { left:0; } .curtain.r { right:0; }
.dev.on .curtain.l { transform:translateX(-100%); } .dev.on .curtain.r { transform:translateX(100%); }
.feed { background:white; border:1px solid var(--line); border-radius:20px; padding:.9rem; max-height:360px; overflow:auto; }
.ev { display:flex; gap:.7rem; padding:.55rem .5rem; border-radius:12px; opacity:.38; transition:all .4s; }
.ev .t { font-family:'Plus Jakarta Sans',sans-serif; font-weight:800; font-size:.9rem; min-width:3.1rem; }
.ev .x { font-weight:600; font-size:.9rem; } .ev .w { font-size:.8rem; color:var(--muted); margin-top:.1rem; }
.ev.done { opacity:1; } .ev.done .x::before { content:"✓ "; color:var(--mint); }
.ev.now { opacity:1; background:linear-gradient(90deg,rgba(16,185,129,.13),rgba(6,182,212,.06)); }
svg { width:100%; height:120px; display:block; background:white; border:1px solid var(--line); border-radius:18px; }
.chartbox { margin-top:1rem; } .axis { display:flex; justify-content:space-between; font-size:.7rem; color:var(--muted); padding:.25rem .3rem 0; }
.legend { display:flex; gap:1rem; font-size:.75rem; color:var(--muted); margin-bottom:.35rem; } .legend i { display:inline-block; width:14px; height:3px; border-radius:2px; vertical-align:middle; margin-right:.3rem; }
@media (max-width:760px) { .main { grid-template-columns:1fr; } .stats { grid-template-columns:1fr; } }
</style></head><body>
<div class="top">
  <div class="clock" id="clock">00:00</div>
  <div class="meta"><span id="date"></span><span><span class="pill" id="tariff"></span></span></div>
  <div class="ctrl"><button id="play" class="on">❚❚ Pause</button><button id="speed">Speed 1×</button><button id="again">↺ Replay</button></div>
</div>
<div class="stats">
  <div class="stat"><div class="lbl">Home load now</div><div class="val" id="load">0<small> kW</small></div><div class="bar"><i id="loadbar"></i><b id="limitmark"></b></div></div>
  <div class="stat"><div class="lbl">Spent so far today</div><div class="val" id="spent">0.00<small> SGD</small></div></div>
  <div class="stat"><div class="lbl">Saved so far</div><div class="val" id="saved" style="color:#059669">0.00<small> SGD</small></div></div>
  <div class="stat"><div class="lbl">Next action</div><div class="next" id="next"></div></div>
</div>
<div class="main"><div class="devices" id="devices"></div><div class="feed" id="feed"></div></div>
<div class="chartbox"><div class="legend"><span><i style="background:#10B981"></i>Home load with the brain</span><span><i style="background:#94A3B8"></i>Without it</span><span id="lg-limit"><i style="background:#EF4444"></i>Your limit</span><span><i style="background:rgba(16,185,129,.25);height:9px"></i>Off-peak price</span></div><svg id="chart" viewBox="0 0 1000 120" preserveAspectRatio="none"></svg><div class="axis"><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span></div></div>
<script>
const D = __DATA__;
const COLORS = {light:["#F59E0B","rgba(245,158,11,.16)","#B45309"], heater:["#F97316","rgba(249,115,22,.15)","#C2410C"],
  water_heater:["#F97316","rgba(249,115,22,.15)","#C2410C"], air_conditioner:["#06B6D4","rgba(6,182,212,.15)","#0E7490"],
  fan:["#06B6D4","rgba(6,182,212,.15)","#0E7490"], curtains:["#10B981","rgba(16,185,129,.14)","#047857"]};
const SPIN = ["washing_machine","dryer","dishwasher","fan","vacuum"];
const $ = id => document.getElementById(id);
const fmt = m => String(Math.floor(m/60)).padStart(2,"0")+":"+String(Math.floor(m%60)).padStart(2,"0");
const START = D.timeline.length ? Math.max(0, Math.floor((D.timeline[0].t - 60) / 30) * 30) : 0;  // skip the quiet night
let t = START, playing = true, speed = 1, pauseUntil = 0, last = null, shown = -1;

$("date").textContent = D.date;
const devEl = {};
for (const d of D.devices) {
  const c = COLORS[d.type] || ["#10B981","rgba(16,185,129,.14)","#047857"];
  const el = document.createElement("div");
  el.className = "dev" + (SPIN.includes(d.type) ? " spin" : "");
  el.style.setProperty("--glow", c[0]); el.style.setProperty("--halo", c[1]); el.style.setProperty("--deep", c[2]);
  el.innerHTML = (d.type === "curtains" ? '<div class="curtain l"></div><div class="curtain r"></div>' : "") +
    `<div class="ic"><span>${d.icon}</span></div><div class="nm">${d.name}</div><div class="st">${d.states[1]}</div>` +
    `<div class="prog"><i></i></div><div class="via ${d.via ? "linked" : ""}">${d.via ? "🔗 Linked via " + d.via : "Simulated device"}</div>`;
  $("devices").appendChild(el); devEl[d.id] = el;
}
$("feed").innerHTML = D.timeline.map((e, i) =>
  `<div class="ev" id="ev${i}"><div class="t">${e.at}</div><div><div class="x">${e.text}</div><div class="w">${e.why}</div></div></div>`).join("")
  || '<div class="ev done"><div class="x">Nothing to do today</div></div>';

// chart: load (green), without the brain (grey dashed), limit (red), off-peak shading, playhead
const maxKw = Math.max(D.limit || 0, ...D.series.map(s => Math.max(s.load, s.baseline))) * 1.15;
const X = m => m / 1440 * 1000, Y = kw => 112 - kw / maxKw * 100;
const path = key => D.series.map((s, i) => (i ? "L" : "M") + X(s.t).toFixed(1) + " " + Y(s[key]).toFixed(1)).join(" ");
let svg = "";
D.series.forEach(s => { if (s.price < 0.28) svg += `<rect x="${X(s.t)}" y="0" width="${X(5)+0.4}" height="120" fill="rgba(16,185,129,.07)"/>`; });
svg += `<path d="${path("baseline")}" fill="none" stroke="#94A3B8" stroke-width="1.5" stroke-dasharray="4 3"/>`;
svg += `<path d="${path("load")}" fill="none" stroke="#10B981" stroke-width="2.4"/>`;
if (D.limit) svg += `<line x1="0" x2="1000" y1="${Y(D.limit)}" y2="${Y(D.limit)}" stroke="#EF4444" stroke-dasharray="6 4"/>`;
svg += `<line id="head" x1="0" x2="0" y1="0" y2="120" stroke="#0E2A24" stroke-width="1.5"/>`;
$("chart").innerHTML = svg;
if (!D.limit) $("lg-limit").style.display = "none";
if (D.limit) $("limitmark").style.left = Math.min(D.limit / maxKw, 1) * 100 + "%"; else $("limitmark").style.display = "none";

const spentAt = [0], baseAt = [0];
for (let m = 0; m < 1440; m++) { const s = D.series[Math.floor(m/5)]; spentAt.push(spentAt[m] + s.load / 60 * s.price); baseAt.push(baseAt[m] + s.baseline / 60 * s.price); }

function stateAt(m) {
  const on = {};
  for (const id in D.intervals) on[id] = D.intervals[id].find(([a, b]) => a <= m && m < b);
  return on;
}
function draw() {
  const m = Math.min(t, 1439.9), s = D.series[Math.floor(m / 5)];
  $("clock").textContent = fmt(m);
  const off = s.price < 0.28; $("tariff").className = "pill " + (off ? "off" : "peak");
  $("tariff").textContent = (off ? "Off-peak " : "Peak ") + s.price.toFixed(3) + " SGD/kWh";
  $("load").innerHTML = s.load.toFixed(2) + "<small> kW" + (D.limit ? " · limit " + D.limit + " kW" : "") + "</small>";
  $("loadbar").style.width = Math.min(s.load / maxKw, 1) * 100 + "%";
  $("spent").innerHTML = spentAt[Math.floor(m)].toFixed(2) + "<small> SGD</small>";
  $("saved").innerHTML = Math.max(baseAt[Math.floor(m)] - spentAt[Math.floor(m)], 0).toFixed(2) + "<small> SGD</small>";
  $("head").setAttribute("x1", X(m)); $("head").setAttribute("x2", X(m));
  const on = stateAt(m);
  for (const d of D.devices) {
    const el = devEl[d.id], iv = on[d.id], isOn = !!iv;
    el.classList.toggle("on", isOn); el.querySelector(".st").textContent = isOn ? d.states[0] : d.states[1];
    const prog = el.querySelector(".prog");
    if (isOn && d.cycle && iv[1] < 1440) { prog.style.display = "block"; prog.firstChild.style.width = ((m - iv[0]) / (iv[1] - iv[0]) * 100) + "%"; }
    else prog.style.display = "none";
  }
  let cur = -1;
  D.timeline.forEach((e, i) => { const el = $("ev" + i); el.classList.toggle("done", e.t <= m); el.classList.remove("now"); if (e.t <= m) cur = i; });
  if (cur >= 0 && D.timeline[cur].t > m - 30) $("ev" + cur).classList.add("now");
  if (cur !== shown && cur >= 0) {
    shown = cur; $("ev" + cur).scrollIntoView({block: "nearest", behavior: "smooth"});
    const el = devEl[D.timeline[cur].device]; if (el) { el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash"); }
  }
  const nxt = D.timeline.find(e => e.t > m);
  $("next").textContent = nxt ? nxt.at + " · " + nxt.text : (t >= 1440 ? "Day complete ✓" : "Nothing else today");
}
function tick(now) {
  if (last === null) last = now;
  const dt = (now - last) / 1000; last = now;
  if (playing && t < 1440 && now >= pauseUntil) {
    const nxt = D.timeline.find(e => e.t > t);
    const near = nxt && nxt.t - t < 20;
    const before = t;
    t += dt * speed * (near ? 8 : 80);
    const hit = D.timeline.find(e => e.t > before && e.t <= t);
    if (hit) { t = hit.t; pauseUntil = now + 1100 / speed; }
    if (t >= 1440) { t = 1440; playing = false; $("play").textContent = "▶ Play"; $("play").classList.remove("on"); }
    draw();
  }
  requestAnimationFrame(tick);
}
$("play").onclick = () => { if (t >= 1440) t = START; playing = !playing; $("play").textContent = playing ? "❚❚ Pause" : "▶ Play"; $("play").classList.toggle("on", playing); };
$("speed").onclick = () => { speed = speed === 1 ? 3 : speed === 3 ? 8 : 1; $("speed").textContent = "Speed " + speed + "×"; };
$("again").onclick = () => { t = START; shown = -1; playing = true; $("play").textContent = "❚❚ Pause"; $("play").classList.add("on"); draw(); };
if (!D.autoplay) { t = 1440; playing = false; $("play").textContent = "▶ Play"; $("play").classList.remove("on"); }
draw(); requestAnimationFrame(tick);
</script></body></html>"""


def render(record, paired=None, autoplay=True, speed=1):
    """A self-contained HTML page that replays the record's day."""
    plan, paired = record["plan"], paired or {}
    # Names and quotes come from the household and the model, and the page inserts them as HTML.
    timeline = [{**e, "text": html.escape(e["text"]), "why": html.escape(e["why"])} for e in record["timeline"]]
    devices = [{"id": d, "name": html.escape(v["name"]), "type": v["type"], "icon": home.DEVICE_TYPES[v["type"]][1],
                "states": list(home.DEVICE_TYPES[v["type"]][3]), "via": paired.get(d),
                "cycle": any(t["device"] == d for t in plan["tasks"])}
               for d, v in plan["devices"].items()]
    data = {"date": record["date"], "devices": devices, "timeline": timeline,
            "intervals": record["intervals"], "series": record["series"], "limit": plan["max_household_kw"],
            "autoplay": autoplay}
    # json.dumps output is safe inside <script> once "</" is escaped.
    page = PAGE.replace("__DATA__", json.dumps(data).replace("</", "<\\/"))
    return (page.replace("let t = START, playing = true, speed = 1,", f"let t = START, playing = true, speed = {speed},")
            .replace(">Speed 1×<", f">Speed {speed}×<"))
