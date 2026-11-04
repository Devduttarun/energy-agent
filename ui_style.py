"""Styles for the dashboard (app.py): a light, minimal look with glass cards and a mint accent."""

STYLE = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap');

:root { --ink:#0E2A24; --muted:#5B6B67; --mint:#10B981; --cyan:#06B6D4; --line:rgba(14,42,36,.08);
        --glass:rgba(255,255,255,.72); --shadow:0 12px 40px -16px rgba(16,94,74,.25); }
html, body, .stApp, button, input, textarea, select { font-family:'Inter',system-ui,sans-serif !important; }
.stApp { color:var(--ink);
  background:
    radial-gradient(700px 480px at 6% 4%, rgba(16,185,129,.20), transparent 60%),
    radial-gradient(620px 460px at 94% 12%, rgba(6,182,212,.16), transparent 60%),
    radial-gradient(640px 520px at 60% 70%, rgba(190,242,100,.14), transparent 60%),
    #F4FBF8;
  background-attachment:fixed; }
header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] { display:none !important; }
.block-container { max-width:1160px; padding:1.2rem 1.5rem 5rem; }
h1, h2, h3 { font-family:'Plus Jakarta Sans','Inter',sans-serif !important; letter-spacing:-.02em; color:var(--ink); }
code { background:rgba(16,185,129,.10) !important; color:#047857 !important; border-radius:6px; padding:.05rem .35rem; }

/* nav */
.nav { position:sticky; top:.6rem; z-index:50; display:flex; align-items:center; justify-content:space-between; gap:1rem;
  padding:.6rem .8rem .6rem .7rem; border-radius:20px; background:var(--glass); backdrop-filter:blur(18px);
  border:1px solid var(--line); box-shadow:var(--shadow); }
.brand { display:flex; align-items:center; gap:.6rem; }
.brand .logo { width:38px; height:38px; border-radius:12px; display:grid; place-items:center; font-size:1.1rem;
  background:linear-gradient(135deg,var(--mint),var(--cyan)); box-shadow:0 6px 16px -6px rgba(16,185,129,.7); }
.brand b { font-family:'Plus Jakarta Sans',sans-serif; font-size:1.05rem; display:block; line-height:1.1; }
.brand b span { color:var(--mint); }
.brand small { font-size:.62rem; letter-spacing:.14em; color:var(--muted); }
.links { display:flex; gap:.2rem; }
.links a { color:var(--ink) !important; text-decoration:none !important; font-size:.88rem; font-weight:500;
  padding:.45rem .8rem; border-radius:12px; }
.links a:hover { background:rgba(16,185,129,.10); }
.status { display:flex; align-items:center; gap:.45rem; font-size:.8rem; font-weight:600; padding:.5rem .85rem;
  border-radius:12px; }
.status i { width:8px; height:8px; border-radius:50%; }
.status.ok { background:rgba(16,185,129,.12); color:#047857; } .status.ok i { background:var(--mint); box-shadow:0 0 0 4px rgba(16,185,129,.18); }
.status.warn { background:rgba(245,158,11,.14); color:#92400E; } .status.warn i { background:#F59E0B; }
@media (max-width:820px) { .links { display:none; } }

/* hero + how to use */
.hero { text-align:center; padding:3.6rem .4rem 1.6rem; }
.eyebrow { display:inline-block; font-size:.8rem; font-weight:600; color:#047857; padding:.4rem .8rem;
  border-radius:999px; background:rgba(255,255,255,.7); border:1px solid rgba(16,185,129,.25); }
.hero h1 { font-size:clamp(2.3rem,5vw,3.8rem); line-height:1.04; font-weight:800; margin:1rem 0 .9rem; padding:0; }
.grad { background:linear-gradient(90deg,var(--mint),var(--cyan)); -webkit-background-clip:text; background-clip:text; color:transparent; }
.hero p { font-size:1.1rem; line-height:1.6; color:var(--muted); max-width:44rem; margin:0 auto; }
.howto { display:grid; grid-template-columns:repeat(4,1fr); gap:.7rem; margin:.4rem 0 1.4rem; }
.hs { display:flex; gap:.75rem; background:var(--glass); backdrop-filter:blur(14px); border:1px solid var(--line);
  border-radius:20px; padding:1rem 1.05rem; box-shadow:var(--shadow); }
.hs > span { flex:none; width:28px; height:28px; border-radius:9px; display:grid; place-items:center; font-weight:800; font-size:.85rem;
  color:white; background:linear-gradient(135deg,var(--mint),var(--cyan)); }
.hs b { font-size:.92rem; } .hs p { margin:.2rem 0 0; font-size:.8rem; color:var(--muted); line-height:1.45; }
@media (max-width:900px) { .howto { grid-template-columns:1fr 1fr; } }
@media (max-width:560px) { .howto { grid-template-columns:1fr; } }

/* sections + cards */
.section-head { padding:2rem .2rem .8rem; scroll-margin-top:6rem; }
.section-head .num { font-family:'Plus Jakarta Sans',sans-serif; font-weight:800; font-size:.85rem; color:var(--mint); letter-spacing:.1em; }
.section-head h2 { font-size:1.9rem; font-weight:800; margin:.2rem 0 .3rem; padding:0; }
.section-head p { color:var(--muted); margin:0; font-size:1.02rem; }
[class*="st-key-card_"] { background:var(--glass); backdrop-filter:blur(18px); border:1px solid var(--line);
  border-radius:28px; padding:1.6rem 1.7rem; box-shadow:var(--shadow); }

/* widgets */
button[data-testid="stBaseButton-primary"] { background:linear-gradient(135deg,var(--mint),var(--cyan)) !important;
  border:none !important; border-radius:999px !important; padding:.55rem 1.4rem !important; font-weight:600 !important;
  box-shadow:0 10px 24px -10px rgba(16,185,129,.8); transition:transform .15s ease; }
button[data-testid="stBaseButton-primary"]:hover { transform:translateY(-1px); }
button[data-testid="stBaseButton-primary"]:disabled { background:#CBD5D1 !important; box-shadow:none; }
button[data-testid="stBaseButton-secondary"] { border-radius:999px !important; border:1px solid var(--line) !important;
  background:white !important; font-weight:500 !important; }
button[data-testid="stBaseButton-secondary"]:hover { border-color:var(--mint) !important; color:#047857 !important; }
[data-testid="stTextArea"] textarea { border-radius:16px !important; background:white !important; font-size:1rem !important; line-height:1.55 !important; }
[data-testid="stExpander"] details { border-radius:16px !important; border:1px solid var(--line) !important; background:rgba(255,255,255,.6); }
[data-testid="stAudioInput"] > div { border-radius:16px; }
.stTabs [data-baseweb="tab-list"] { gap:.3rem; }
.stTabs [data-baseweb="tab"] { border-radius:999px; padding:.3rem 1rem; }

/* results */
.money { display:grid; grid-template-columns:1.2fr 1fr; gap:.8rem; margin-bottom:.6rem; }
.money .mm { background:var(--glass); border:1px solid var(--line); border-radius:24px; padding:1.3rem 1.4rem; box-shadow:var(--shadow); }
.money .mm:first-child { background:linear-gradient(135deg,rgba(16,185,129,.14),rgba(6,182,212,.10)); }
.money .lbl { font-weight:700; color:var(--muted); font-size:.85rem; }
.money .big { font-family:'Plus Jakarta Sans',sans-serif; font-size:3rem; font-weight:800; letter-spacing:-.03em; margin:.2rem 0; }
.money .mm:first-child .big { background:linear-gradient(90deg,var(--mint),var(--cyan)); -webkit-background-clip:text; background-clip:text; color:transparent; }
.money .big small { font-size:1rem; color:var(--muted); font-weight:600; }
.money .sub { font-size:.88rem; color:var(--muted); }
[class*="st-key-opt_"] { background:white; border:1px solid var(--line); border-radius:18px; padding:.7rem 1rem; margin-bottom:.45rem; }
.opt { flex:1; } .opt b { display:block; } .opt span { font-size:.82rem; color:var(--muted); }
.optsave { font-weight:800; color:#059669; text-align:right; white-space:nowrap; } .optsave small { font-weight:600; color:var(--muted); }
@media (max-width:900px) { .money { grid-template-columns:1fr; } }
.kpis { display:grid; grid-template-columns:repeat(4,1fr); gap:.8rem; margin-bottom:1rem; }
.kpi { background:var(--glass); backdrop-filter:blur(14px); border:1px solid var(--line); border-radius:24px; padding:1.2rem 1.3rem; box-shadow:var(--shadow); }
.kpi .big { font-family:'Plus Jakarta Sans',sans-serif; font-size:2.3rem; font-weight:800; letter-spacing:-.03em; margin:.3rem 0 .15rem; }
.kpi .big small { font-size:.9rem; color:var(--muted); font-weight:600; }
.kpi:first-child .big { background:linear-gradient(90deg,var(--mint),var(--cyan)); -webkit-background-clip:text; background-clip:text; color:transparent; }
.kpi .sub { font-size:.82rem; color:var(--muted); }
@media (max-width:900px) { .kpis { grid-template-columns:1fr 1fr; } }
.why { color:var(--muted); font-size:.9rem; margin:0; }

/* how it works */
.how { display:grid; grid-template-columns:repeat(4,1fr); gap:.8rem; }
.hw { background:var(--glass); backdrop-filter:blur(14px); border:1px solid var(--line); border-radius:24px; padding:1.3rem; box-shadow:var(--shadow); }
.hw .n { width:32px; height:32px; border-radius:10px; display:grid; place-items:center; font-weight:800; color:white;
  background:linear-gradient(135deg,var(--mint),var(--cyan)); }
.hw h3 { font-size:1.15rem; margin:.8rem 0 .3rem; padding:0; } .hw p { color:var(--muted); font-size:.9rem; line-height:1.5; margin:0; }
@media (max-width:900px) { .how { grid-template-columns:1fr 1fr; } }
.foot { color:var(--muted); font-size:.82rem; margin-top:1.5rem; text-align:center; }

/* stop Streamlit fading old content while a run updates the page */
[data-stale="true"], .stale-element { opacity:1 !important; transition:none !important; }
.stTabs [data-baseweb="tab-list"] { background:var(--glass); border:1px solid var(--line); border-radius:999px; padding:.3rem;
  width:fit-content; margin:0 auto; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display:none; }
.stTabs [aria-selected="true"] { background:linear-gradient(135deg,var(--mint),var(--cyan)) !important; color:white !important; }
.stTabs [aria-selected="true"] p { color:white !important; font-weight:600; }
.lbl { font-size:.7rem; font-weight:700; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); }
.try { font-size:.85rem; color:var(--muted); font-weight:600; }

/* understood plan */
.understood { margin-top:1.2rem; }
.summary { margin:.35rem 0 .7rem; font-size:1rem; }
.items { display:grid; grid-template-columns:repeat(auto-fill,minmax(250px,1fr)); gap:.6rem; }
.item { display:flex; gap:.75rem; background:white; border:1px solid rgba(16,185,129,.25); border-radius:18px; padding:.8rem .95rem; }
.item .ii { flex:none; width:38px; height:38px; border-radius:12px; display:grid; place-items:center; font-size:1.2rem; background:#F1F8F5; }
.item b { display:block; font-size:.93rem; } .item span { display:block; font-family:'Plus Jakarta Sans',sans-serif; font-weight:800; color:#047857; font-size:.95rem; }
.item q { display:block; font-size:.78rem; color:var(--muted); font-style:italic; margin-top:.2rem; }

/* process flow */
.pipeline { display:flex; align-items:center; margin:1.1rem 0 .9rem; }
.node { flex:none; width:118px; text-align:center; transition:all .3s; }
.node .ic { width:54px; height:54px; margin:0 auto .45rem; border-radius:18px; display:grid; place-items:center; font-size:1.45rem;
  background:#F1F5F4; border:2px solid #E2EAE7; filter:grayscale(1); opacity:.6; transition:all .3s; }
.node b { display:block; font-size:.88rem; color:#94A3B8; } .node small { display:block; font-size:.72rem; color:var(--muted); min-height:1.1em; }
.node.done .ic { filter:none; opacity:1; background:white; border-color:var(--mint); } .node.done b { color:var(--ink); }
.node.active .ic { filter:none; opacity:1; background:white; border-color:var(--cyan); animation:pulse 1.3s ease-in-out infinite; }
.node.active b { color:#0891B2; }
.node.caught .ic { filter:none; opacity:1; background:#FEF2F2; border-color:#EF4444; } .node.caught b, .node.caught small { color:#B91C1C; }
@keyframes pulse { 50% { box-shadow:0 0 0 9px rgba(6,182,212,.14); } }
.link { flex:1; height:3px; border-radius:3px; background:#E2EAE7; margin-bottom:2.1rem; min-width:12px; }
.log { display:flex; flex-direction:column; gap:.4rem; margin-bottom:1rem; }
.ln { display:flex; gap:.7rem; align-items:flex-start; background:white; border:1px solid var(--line); border-radius:14px;
  padding:.6rem .9rem; font-size:.92rem; animation:rise .3s ease; }
.ln > span { flex:none; width:1.4rem; text-align:center; }
.ln.ok { border-color:rgba(16,185,129,.4); background:rgba(236,253,245,.7); } .ln.bad { border-color:rgba(239,68,68,.35); background:rgba(254,242,242,.85); }
.ln.drill { border-color:rgba(129,140,248,.45); background:rgba(238,242,255,.85); } .ln.think { color:#0E7490; }
@keyframes rise { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:none; } }
@media (max-width:820px) { .node { width:70px; } .node small { display:none; } .node .ic { width:42px; height:42px; } }

/* results */
.notes { display:flex; flex-direction:column; gap:.5rem; margin-bottom:1rem; }
.note { display:flex; gap:.7rem; background:white; border:1px solid rgba(245,158,11,.35); border-radius:16px; padding:.75rem 1rem; font-size:.92rem; }
.timeline { display:flex; flex-direction:column; margin-top:.6rem; }
.tl { display:flex; gap:1rem; padding:.6rem .2rem; border-bottom:1px solid var(--line); }
.tl b { font-family:'Plus Jakarta Sans',sans-serif; min-width:3.2rem; } .tl span { display:block; font-weight:600; font-size:.93rem; }
.tl small { color:var(--muted); font-size:.82rem; }
.attempt { background:white; border:1px solid var(--line); border-radius:18px; padding:.9rem 1.1rem; margin:.6rem 0 .3rem; }
.attempt ul { margin:.4rem 0 0; padding-left:1.2rem; color:#B91C1C; font-size:.88rem; }
.dh { display:flex; justify-content:space-between; align-items:center; gap:1rem; font-size:.95rem; }

/* integrations */
.demo-note { background:rgba(245,158,11,.10); border:1px solid rgba(245,158,11,.35); color:#92400E; border-radius:14px;
  padding:.6rem .9rem; font-size:.86rem; margin-bottom:1rem; }
.hubs { display:grid; grid-template-columns:repeat(4,1fr); gap:.7rem; margin-bottom:1rem; }
.hub { background:var(--glass); border:1px solid var(--line); border-radius:20px; padding:1rem; box-shadow:var(--shadow); }
.hub .hi { width:40px; height:40px; border-radius:12px; display:grid; place-items:center; font-size:1.3rem; color:white;
  background:linear-gradient(135deg,var(--mint),var(--cyan)); }
.hub b { display:block; margin-top:.6rem; } .hub p { font-size:.8rem; color:var(--muted); margin:.2rem 0 .5rem; line-height:1.4; }
.hub span { font-size:.72rem; font-weight:700; color:var(--muted); } .hub span.on { color:#047857; }
@media (max-width:900px) { .hubs { grid-template-columns:1fr 1fr; } }
[class*="st-key-pair_"] { background:white; border:1px solid var(--line); border-radius:16px; padding:.55rem .8rem; margin-top:.5rem; }
[class*="st-key-pair_"] [data-testid="stSelectbox"] { max-width:180px; }
.pd { display:flex; gap:.7rem; align-items:center; min-width:240px; } .pd > span { font-size:1.4rem; }
.pd b { display:block; font-size:.93rem; } .pd small { color:var(--muted); font-size:.78rem; }
</style>"""
