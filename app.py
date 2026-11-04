"""energy-agent dashboard: tell the home brain about your day, watch it plan, check and run it.

Run with: .venv/bin/streamlit run app.py
"""
import json
import time

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import agent
import household as home
import live_view
import llm
from preferences import DEFAULT_PREFERENCES, extract_plan, transcribe_preferences
from ui_style import STYLE

st.set_page_config(page_title="energy-agent", page_icon="⚡", layout="wide")
st.html(STYLE)

PRESETS = {
    "Morning routine": DEFAULT_PREFERENCES,
    "Laundry night": "The dryer can run any time after 8pm, as long as it's done by midnight. Not between 9pm "
                     "and 10:30pm though, the kids are falling asleep. Keep the whole flat under 4 kW.",
    "Whole home": "Turn the water heater on at 6:30am for 30 minutes and open the curtains at 6:45. Charge the "
                  "car for 3 hours some time before 7am, whenever it's cheapest. Run the dishwasher after dinner, "
                  "any time between 8pm and midnight. Bedroom AC on at 10pm. Never go above 9 kW.",
}
PACE = {"Demo": (1.3, 1), "Fast": (0.0, 3)}  # pause after each step of the flow, replay speed
STAGES = [("listen", "🎙️", "Listen"), ("understand", "🧠", "Understand"), ("plan", "🗓️", "Plan"),
          ("verify", "🛡️", "Verify"), ("act", "⚡", "Act"), ("explain", "💬", "Explain")]
PROTOCOLS = ["Matter", "Zigbee", "Wi-Fi plug", "Home Assistant"]


def model_label(model):
    return {llm.SPARK_OPEN_MODEL: "Muse Spark Open", llm.META_SPARK_MODEL: "Muse Spark (Meta API)"}.get(model, "code")


def current_model():
    return model_label(llm.SPARK_OPEN_MODEL if llm.baseten_error is None else llm.META_SPARK_MODEL)


def esc(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def set_prefs(text):
    st.session_state.prefs = text


def flow_html(stages, log):
    """The process flow: six stages lit up as the brain works, and a plain-language log under it."""
    nodes = "".join(
        f'<div class="node {stages.get(k, ("idle", ""))[0]}"><div class="ic">{ic}</div><b>{name}</b>'
        f'<small>{esc(stages.get(k, ("", ""))[1])}</small></div>' + ('<div class="link"></div>' if k != "explain" else "")
        for k, ic, name in STAGES)
    lines = "".join(f'<div class="ln {kind}"><span>{ic}</span><div>{text}</div></div>' for ic, text, kind in log[-6:])
    return f'<div class="pipeline">{nodes}</div><div class="log">{lines}</div>'


def approve(option):
    """Add an approved savings option to the plan and run the day again."""
    st.session_state.plan = home.apply_option(st.session_state.plan, option)
    st.session_state.pop("record", None)
    st.session_state.auto_run = True


def transcribe(audio):
    """Replace the typed text with the transcript of the recording."""
    try:
        text = transcribe_preferences(audio.getvalue())
    except Exception as e:
        st.session_state.transcribe_error = f"Transcription failed ({type(e).__name__}). Type it instead."
        return
    if not text.strip():
        st.session_state.transcribe_error = "I couldn't hear anything in that recording. Try again, a bit closer to the mic."
        return
    st.session_state.prefs = text
    st.session_state.voice = True


def item_rows(plan):
    """(icon, what, when, quote) for every instruction in a plan, in plain language."""
    devs, rows = plan["devices"], []
    for c in plan["commands"]:
        d = devs[c["device"]]
        rows.append((home.DEVICE_TYPES[d["type"]][1], f"{d['name']} {c['state']}", f"at {c['at']} exactly", c["quote"]))
    for k in plan["keep"]:
        d = devs[k["device"]]
        rows.append((home.DEVICE_TYPES[d["type"]][1], f"Keep {d['name']} {k['state']}", f"{k['from']}–{k['until']}", k["quote"]))
    for t in plan["tasks"]:
        d = devs[t["device"]]
        when = f"starts {t['start']}" if t["start"] else f"cheapest time {t['earliest']}–{t['finish_by']}"
        rows.append((home.DEVICE_TYPES[d["type"]][1], f"{d['name']} · {t['minutes']} min", when, t["quote"]))
    if plan["max_household_kw"]:
        rows.append(("⚡", "Whole home under", f"{plan['max_household_kw']:g} kW", plan["limit_quote"]))
    return rows


def first_problem(a):
    return esc(a["problems"][0]) if a["problems"] else ""


# Nav, hero and how to use ------------------------------------------------------------
model_ok = llm.baseten_error is None
st.html(f"""<nav class="nav">
  <div class="brand"><div class="logo">⚡</div><div><b>energy<span>agent</span></b><small>THE BRAIN FOR YOUR HOME</small></div></div>
  <div class="status {'ok' if model_ok else 'warn'}"><i></i>{'Muse Spark Open · Baseten' if model_ok else 'Backup: Muse Spark · Meta API'}</div>
</nav>
<section class="hero">
  <div class="eyebrow">✦ Powered by Meta's open-weights Muse Spark Open</div>
  <h1>Say how you live.<br><span class="grad">Your home just does it.</span></h1>
  <p>Describe your day in your own words. The brain turns it into a plan for every device, picks the cheapest times,
     and plain code checks every action against what you said before anything switches.</p>
</section>
<div class="howto">
  <div class="hs"><span>1</span><div><b>Tell it about your day</b><p>Type, speak, or pick an example. Any device: lights, curtains, heaters, washing machine, AC, EV.</p></div></div>
  <div class="hs"><span>2</span><div><b>Press “Understand my day”</b><p>Check the plan cards. Each one quotes the words it came from.</p></div></div>
  <div class="hs"><span>3</span><div><b>Press “Run my day”</b><p>Watch it plan, catch mistakes, and run your home hour by hour.</p></div></div>
  <div class="hs"><span>4</span><div><b>Optional: Integrations</b><p>Pair your devices so the brain can control them.</p></div></div>
</div>""")

st.session_state.setdefault("prefs", DEFAULT_PREFERENCES)
st.session_state.setdefault("paired", {})
tab_home, tab_int, tab_how = st.tabs(["🏠  Home brain", "🔌  Integrations", "⚙️  How it works"])

# 1. Tell it ---------------------------------------------------------------------------
with tab_home:
    st.html('<div class="section-head"><span class="num">STEP 1</span><h2>Tell it about your day</h2></div>')
    with st.container(key="card_tell"):
        with st.container(key="presets", horizontal=True, vertical_alignment="center"):
            st.html('<span class="try">Try an example:</span>')
            for name, text in PRESETS.items():
                st.button(name, on_click=set_prefs, args=(text,))
        col_text, col_voice = st.columns([2.2, 1], gap="large")
        with col_text:
            prefs = st.text_area("Your day, in your own words", key="prefs", height=130)
        with col_voice:
            audio = st.audio_input("Or say it")
            # A callback runs before the text box is drawn, so it may replace the box's text.
            st.button("Transcribe", icon="🎙️", disabled=audio is None, width="stretch", on_click=transcribe, args=(audio,))
            if st.session_state.get("transcribe_error"):
                st.error(st.session_state.pop("transcribe_error"))
        if st.button("Understand my day", type="primary", icon="✨", disabled=not prefs.strip()):
            with st.spinner(f"{current_model()} is reading what you said..."):
                try:
                    plan, reasoning, warnings = extract_plan(prefs)
                except Exception as e:
                    st.error(f"The model call failed ({type(e).__name__}). Check the API keys in .env.")
                else:
                    st.session_state.update(plan=plan, plan_reasoning=reasoning, plan_warnings=warnings,
                                            plan_model=llm.last_model, as_said=plan)
                    st.session_state.pop("record", None)

        plan = st.session_state.get("plan")
        if plan:
            cards = "".join(f'<div class="item"><div class="ii">{ic}</div><div><b>{esc(what)}</b><span>{esc(when)}</span>'
                            f'{f"<q>{esc(q)}</q>" if q else ""}</div></div>' for ic, what, when, q in item_rows(plan))
            st.html(f'<div class="understood"><div class="lbl">Understood by {model_label(st.session_state.plan_model)}'
                    f' · {home.instruction_count(plan)} instructions · {len(plan["devices"])} devices</div>'
                    f'<p class="summary">{esc(plan["summary"])}</p><div class="items">{cards}</div></div>')
        for w in st.session_state.get("plan_warnings", []):
            st.warning(w, icon="📝")
        if plan:
            with st.expander("Edit the plan by hand"):
                edited = st.text_area("Plan (JSON)", json.dumps(plan, indent=1), height=260, label_visibility="collapsed")
                if st.button("Use this plan"):
                    try:
                        raw = json.loads(edited)
                        raw["devices"] = [{"id": d, **v} for d, v in raw["devices"].items()]
                        new_plan, warnings = home.validate_plan(raw)
                    except (ValueError, KeyError, AttributeError, TypeError) as e:
                        st.error(f"That isn't a valid plan ({type(e).__name__}).")
                    else:
                        st.session_state.update(plan=new_plan, plan_warnings=warnings, plan_model=None, as_said=new_plan)
                        st.session_state.pop("record", None)
                        st.rerun()

    # 2. Run it -----------------------------------------------------------------------
    st.html('<div class="section-head"><span class="num">STEP 2</span><h2>Watch it run your home</h2></div>')
    ready = bool(plan and home.instruction_count(plan))
    with st.container(key="card_run"):
        with st.container(key="controls", horizontal=True, vertical_alignment="center"):
            go = st.button("Run my day", type="primary", icon="▶", disabled=not ready)
            auto = st.session_state.pop("auto_run", False) and ready  # re-run after approving a saving
            drill = st.toggle("Safety drill", value=True,
                              help="Slips one deliberately wrong plan in first, so you can watch the checks catch it "
                                   "and the brain fix it.")
            pace = st.segmented_control("Pace", list(PACE), default="Demo", label_visibility="collapsed") or "Demo"
        flow = st.empty()
        pause, speed = PACE[pace]
        base = {"listen": ("done", "voice note" if st.session_state.get("voice") else "typed")}
        if plan:
            base["understand"] = ("done", f"{home.instruction_count(plan)} instructions")
        if not ready:
            flow.html(flow_html(base, [("👆", "Start with step 1: tell it about your day and press "
                                              "<b>Understand my day</b>.", "")]))

        if go or auto:
            stages, log = dict(base), []

            def show(kind, data):
                if kind == "planning":
                    stages["plan"] = ("active", f"{current_model()} · try {data['attempt']}")
                    log.append(("🧠", f"<b>{current_model()}</b> is planning your day"
                                     + (" again, with the problems it was sent" if data["attempt"] > 1 else "") + "…", "think"))
                elif kind == "attempt":
                    if data["source"] == "drill":
                        stages["plan"] = ("done", "drill plan")
                        what = data["reason"].split("(", 1)[-1].split(")")[0]
                        log.append(("🧪", f"<b>Safety drill:</b> slipped in a wrong plan ({esc(what)}).", "drill"))
                    elif data["source"] == "model":
                        stages["plan"] = ("done", model_label(data.get("model")))
                        if log and log[-1][2] == "think":
                            log.pop()  # the "planning…" line is replaced by its result
                        log.append(("🗓️", f"<b>{model_label(data.get('model'))}</b> made a plan: "
                                          f"{len(data['events'])} switches, {len(data['runs'])} appliance runs.", ""))
                    else:
                        log.append(("↩︎", f"The model couldn't be used: {esc(data['reason'])}.", "bad"))
                    if data["problems"]:
                        n = len(data["problems"])
                        stages["verify"] = ("caught", f"caught {n} problem{'s' * (n > 1)}")
                        log.append(("🛡️", f"<b>Caught it:</b> {first_problem(data)} Sent back to the brain.", "bad"))
                    else:
                        stages["verify"] = ("done", "every check passed")
                        log.append(("✅", "<b>Every check passed:</b> exact times, keep windows, task windows, "
                                          "power limit and cost.", "ok"))
                elif kind == "acting":
                    if data["source"] == "fallback":
                        log.append(("🛟", "No model plan passed, so the brain does exactly what you said.", "bad"))
                    stages["act"] = ("active", "running your day")
                elif kind == "done":
                    m = data["metrics"]
                    stages.update(act=("done", f"{len(data['timeline'])} actions"),
                                  explain=("done", f"{m['instructions'] - m['held']}/{m['instructions']} followed"))
                    log.append(("⚡", "Your day is running below.", "ok"))
                flow.html(flow_html(stages, log))
                time.sleep(pause)

            stages.update(plan=("active", "starting"))
            flow.html(flow_html(stages, log))
            try:
                st.session_state.record = agent.run(plan, drill=drill and not auto, on_event=show,
                                                    as_said=st.session_state.get("as_said"))
                st.session_state.update(flow_state=stages, flow_log=log, autoplay=True)
            except Exception as e:
                st.error(f"The run stopped: {type(e).__name__}. Check your API keys and try again.")
        elif st.session_state.get("record") and st.session_state.get("flow_log"):
            flow.html(flow_html(st.session_state.flow_state, st.session_state.flow_log))
        elif ready:
            flow.html(flow_html(base, [("▶", "Ready. Press <b>Run my day</b>.", "")]))

        record = st.session_state.get("record")
        if record and record["plan"] == plan:
            components.html(live_view.render(record, st.session_state.paired,
                                             autoplay=st.session_state.pop("autoplay", False), speed=speed),
                            height=720, scrolling=False)

    # 3. Results ----------------------------------------------------------------------
    if record and record["plan"] == plan:
        m = record["metrics"]
        caught = sum(1 for a in record["attempts"] if a["problems"])
        saved = m.get("saved_sgd", 0)
        st.html('<div class="section-head"><span class="num">STEP 3</span><h2>What the brain did</h2></div>')
        options = record.get("options", [])
        extra = sum(o["saving_sgd"] for o in options)
        with st.container(key="card_money"):
            st.html(f'''<div class="money"><div class="mm">
  <div class="lbl">💰 Saved today</div><div class="big">{saved:.2f}<small> SGD</small></div>
  <div class="sub">≈ <b>{saved * 30:.0f} SGD a month</b> · <b>{saved * 365:.0f} SGD a year</b>, compared with doing
  exactly what you said by hand (every appliance switched on straight away). Today’s bill: {m["cost_sgd"]:.2f} SGD.</div></div>
  <div class="mm"><div class="lbl">🔍 Still on the table</div><div class="big">{extra:.2f}<small> SGD/day</small></div>
  <div class="sub">{f"≈ <b>{extra * 365:.0f} SGD a year</b> more if you approve the {len(options)} suggestion"
                    f"{'s' * (len(options) > 1)} below. Nothing changes until you say yes."
                    if options else "No more savings found without breaking one of your instructions."}</div></div></div>''')
            for i, o in enumerate(options):
                with st.container(key=f"opt_{i}", horizontal=True, vertical_alignment="center"):
                    st.html(f'<div class="opt"><b>{esc(o["title"])}</b><span>{esc(o["detail"])}</span></div>')
                    st.html(f'<div class="optsave">+{o["saving_sgd"]:.2f} SGD/day<br><small>≈ {o["saving_sgd"] * 365:.0f} SGD/year</small></div>')
                    st.button("Approve", key=f"approve_{i}", icon="✅", on_click=approve, args=(o,))
        kpis = [("Instructions followed", f"{m['instructions'] - m['held']}/{m['instructions']}", "",
                 "exactly as you said" if not m["held"] else f"{m['held']} held for you to decide"),
                ("Mistakes caught", f"{caught}", "", "before anything switched"),
                ("Cost today", f"{m['cost_sgd']:.2f}", "SGD", f"whole home · {m['baseline_cost_sgd']:.2f} SGD without the brain"),
                ("Peak load", f"{m['peak_kw']:.2f}", "kW",
                 (f"limit {plan['max_household_kw']:g} kW · without the brain {m['baseline_over_limit_min']} min over"
                  if m["baseline_over_limit_min"] else f"limit {plan['max_household_kw']:g} kW")
                 if plan["max_household_kw"] else f"{m['baseline_peak_kw']:.2f} kW without the brain")]
        st.html('<div class="kpis">' + "".join(
            f'<div class="kpi"><div class="lbl">{a}</div><div class="big">{b}<small> {u}</small></div><div class="sub">{d}</div></div>'
            for a, b, u, d in kpis) + "</div>")
        offered = {plan["devices"][o["device"]]["name"] for o in options}
        notes = [("❓", q) for q in record["questions"] if not any(f"The {n} " in q for n in offered)]
        if notes:
            st.html('<div class="notes">' + "".join(f'<div class="note"><span>{ic}</span>{esc(t)}</div>'
                                                    for ic, t in notes) + "</div>")

        with st.container(key="card_results"):
            tab_day, tab_hood = st.tabs(["Your day", "Under the hood"])
            with tab_day:
                rows = [{"device": plan["devices"][d]["name"], "start": a, "end": b, "from": home.hhmm(a),
                         "to": home.hhmm(min(b, 1439))} for d, ivs in record["intervals"].items() for a, b in ivs]
                keeps = []
                for k in plan["keep"]:
                    s, e = home.to_min(k["from"]), home.to_min(k["until"])
                    for a, b in ([(s, e)] if s < e else [(s, 1440), (0, e)]):
                        keeps.append({"device": plan["devices"][k["device"]]["name"], "start": a, "end": b,
                                      "label": f"keep {k['state']}"})
                order = [v["name"] for v in plan["devices"].values()]
                x = alt.X("start:Q", title=None, scale=alt.Scale(domain=[0, 1440]),
                          axis=alt.Axis(values=list(range(0, 1441, 180)), labelColor="#64748B", gridColor="#EEF2F1",
                                        labelExpr="timeFormat(datum.value * 60000, '%H:%M')"))
                y = alt.Y("device:N", title=None, sort=order, axis=alt.Axis(labelColor="#0E2A24", labelFontSize=12))
                layers = []
                if keeps:
                    layers.append(alt.Chart(pd.DataFrame(keeps)).mark_bar(color="#818CF8", opacity=0.15, height=26)
                                  .encode(x=x, x2="end:Q", y=y, tooltip=["device:N", "label:N"]))
                if rows:
                    layers.append(alt.Chart(pd.DataFrame(rows)).mark_bar(cornerRadius=6, height=16, color="#10B981")
                                  .encode(x=x, x2="end:Q", y=y, tooltip=["device:N", "from:N", "to:N"]))
                if layers:
                    st.altair_chart(alt.layer(*layers).properties(height=50 + 44 * len(order))
                                    .configure_view(stroke=None), width="stretch")
                    st.caption("Green: when each device is on. Purple: when you asked to keep it in a state.")
                st.html('<div class="timeline">' + "".join(
                    f'<div class="tl"><b>{e["at"]}</b><div><span>{esc(e["text"])}</span><small>{esc(e["why"])}</small></div></div>'
                    for e in record["timeline"]) + "</div>")
            with tab_hood:
                st.html('<p class="why">Each plan goes through <code>verify()</code>, plain code that replays the day '
                        'minute by minute. A failed plan goes back to the model with the exact problems, up to 3 times.</p>')
                for n, a in enumerate(record["attempts"], 1):
                    who = ("🧪 Safety drill" if a["source"] == "drill" else f"🧠 {model_label(a.get('model'))}"
                           if a["source"] == "model" else "↩︎ Fallback")
                    kind, verdict = ("bad", "Rejected") if a["problems"] else ("ok", "Passed")
                    probs = "".join(f"<li>{esc(p)}</li>" for p in a["problems"])
                    st.html(f'<div class="attempt"><div class="dh"><b>Plan {n} · {who}</b><span class="badge {kind}">'
                            f'{verdict}</span></div><p class="why">{esc(a["reason"])}</p>{f"<ul>{probs}</ul>" if probs else ""}</div>')
                    if a.get("reasoning"):
                        with st.expander(f"Raw model reasoning for plan {n}"):
                            st.code(a["reasoning"].strip(), language=None, wrap_lines=True)
                if record["final"]["source"] == "fallback":
                    st.info("No model plan passed, so the brain carried out the literal plan built by code.")
                with st.expander("The plan as data"):
                    st.json(plan, expanded=False)
                    if st.session_state.get("plan_reasoning"):
                        st.code(st.session_state.plan_reasoning.strip(), language=None, wrap_lines=True)

# Integrations -------------------------------------------------------------------------
with tab_int:
    st.html('<div class="section-head"><span class="num">INTEGRATIONS</span><h2>Connect your home</h2>'
            '<p>Pair your devices so the brain can switch them. Each device is paired once; after that, every '
            'verified plan is sent to it at the right time.</p></div>'
            '<div class="demo-note">Demo mode: pairing here is simulated. No real hardware is contacted, and the brain '
            'drives a simulated home.</div>')
    in_use = set(st.session_state.paired.values())
    hubs = [("Matter", "◈", "Lights, plugs, curtains and sensors from any Matter-certified brand"),
            ("Zigbee", "⬡", "Low-power mesh devices through a Zigbee hub"),
            ("Wi-Fi plug", "⏻", "Any appliance on a smart plug with power metering"),
            ("Home Assistant", "⌂", "Every device your Home Assistant server already controls")]
    st.html('<div class="hubs">' + "".join(
        f'<div class="hub"><div class="hi">{ic}</div><b>{name}</b><p>{desc}</p>'
        f'<span class="{"on" if name in in_use else ""}">{"● In use" if name in in_use else "Available"}</span></div>'
        for name, ic, desc in hubs) + "</div>")
    devices = (st.session_state.get("plan") or {}).get("devices") or {}
    with st.container(key="card_pair"):
        st.html(f'<div class="lbl">{"Devices in your plan" if devices else "Understand your day first to see its devices"}</div>')
        for d, v in devices.items():
            linked = st.session_state.paired.get(d)
            with st.container(key=f"pair_{d}", horizontal=True, vertical_alignment="center"):
                st.html(f'<div class="pd"><span>{home.DEVICE_TYPES[v["type"]][1]}</span><div><b>{esc(v["name"])}</b>'
                        f'<small>{v["kw"]:g} kW · {"🔗 linked via " + linked if linked else "not paired"}</small></div></div>')
                proto = st.selectbox("Protocol", PROTOCOLS, key=f"proto_{d}", label_visibility="collapsed",
                                     index=PROTOCOLS.index(linked) if linked else 0, disabled=bool(linked))
                if linked:
                    if st.button("Unpair", key=f"unpair_{d}"):
                        st.session_state.paired.pop(d)
                        st.rerun()
                elif st.button("Pair", key=f"pairbtn_{d}", type="primary"):
                    with st.spinner(f"Looking for {v['name']} on {proto}..."):
                        time.sleep(1.4)
                    st.session_state.paired[d] = proto
                    st.toast(f"{v['name']} paired via {proto} (simulated)", icon="🔗")
                    st.rerun()

# How it works -------------------------------------------------------------------------
with tab_how:
    st.html("""<div class="section-head"><span class="num">HOW IT WORKS</span><h2>An AI plans. Plain code checks.</h2>
<p>Nothing switches until the check passes.</p></div>
<div class="how">
  <div class="hw"><div class="n">🎙️</div><h3>Listen</h3><p><b>Muse Voice Transcribe</b> (Meta Model API) turns a voice note into text.</p></div>
  <div class="hw"><div class="n">🧠</div><h3>Understand</h3><p><b>Muse Spark Open</b> (open weights, on Baseten) turns your words into devices, exact times, keep windows, appliance tasks and a power limit, quoting what you said.</p></div>
  <div class="hw"><div class="n">🗓️</div><h3>Plan</h3><p>Muse Spark Open writes the day's timeline and picks the cheapest valid time for flexible tasks from the price forecast.</p></div>
  <div class="hw"><div class="n">🛡️</div><h3>Verify</h3><p><code>verify()</code> replays the day minute by minute: every exact time, keep window, task window, the power limit and cost. Problems go back to the model, up to 3 times; after that it does exactly what you said.</p></div>
  <div class="hw"><div class="n">⚡</div><h3>Act</h3><p>The verified timeline drives the home: each device switches at its time.</p></div>
  <div class="hw"><div class="n">💬</div><h3>Explain</h3><p>Every action says why, in your words, with tips to save money and questions where you left something open.</p></div>
</div>
<p class="foot">Prices and background load are representative <b>synthetic</b> Singapore data, not real meter readings.
The home is simulated. If Baseten is unreachable, Muse Spark on the Meta Model API takes over, and the badge at the top says so.</p>""")
