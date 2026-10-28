# PieGram - a pretend social feed for sharing the groups' plot twists (Enemy Pie, Response 4)
# Every student uses their own device. Shared state lives in the app's memory for the lesson
# (it resets when the app restarts), so no database is needed.
#
# Secrets used: CLASS_CODE (students, optional) and TEACHER_CODE (teacher controls).

import html
import random
import threading
import uuid
import streamlit as st
from shared import REACTIONS, BOT_POSTS, new_post, board, upsert_post, clean_handle, clean_tags

st.set_page_config(page_title="PieGram", page_icon="📸", layout="wide")

# ============================================================
# 1. Settings
# ============================================================
COMMENT_FRAMES = ["I didn't expect ___!", "The clue was ___.", "My favorite part was ___.", "I think this is AI because ___."]
CARD_NAMES = {1: "Profile", 2: "Setup", 3: "What happens next?", 4: "Twist!"}
START_LINE = "I was wondering what dirty thing I had to put in the pie."
END_LINE = "Jeremy invited me over to his house. I lost my best enemy."

# ============================================================
# 2. The shared board (one per app, shared by every student)
# ============================================================
B = board()
ss = st.session_state
ss.setdefault("me", "")
ss.setdefault("my_handle", "")
ss.setdefault("teacher", False)
ss.setdefault("unlocked", False)
esc = lambda t: html.escape(str(t))                      # for our own HTML cards
import re
md = lambda t: re.sub(r"([\\`*_{}\[\]()#+\-.!|>~<])", r"\\\1", str(t))  # for plain Markdown text

def human_posts(): return [p for p in B["posts"].values() if not p["bot"]]
def all_posts(): return list(B["posts"].values())

def assign_labels():
    posts = all_posts()
    random.shuffle(posts)
    for i, p in enumerate(posts):
        p["label"] = f"Post {chr(65 + i)}"

def ranked():
    return sorted(all_posts(), key=lambda p: (len(p["react"]["wow"]), len(p["react"]["lol"])), reverse=True)

# ============================================================
# 3. Look
# ============================================================
st.markdown("""<style>
.pg-card{border-radius:22px;padding:22px 22px 26px;color:#fff;min-height:460px;display:flex;flex-direction:column;gap:14px;box-shadow:0 10px 30px rgba(0,0,0,.25)}
.pg-bars{display:flex;gap:6px}.pg-bars i{flex:1;height:5px;border-radius:3px;background:rgba(255,255,255,.35)}.pg-bars i.on{background:#fff}
.pg-user{display:flex;align-items:center;gap:10px;font-weight:800;font-size:18px}
.pg-ava{width:44px;height:44px;border-radius:50%;background:#fff;color:#1F1D2B;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:20px;border:3px solid #FFD34D}
.pg-text{font-size:clamp(20px,2.4vw,30px);font-weight:700;line-height:1.4}
.pg-muted{opacity:.85;font-style:italic;font-size:18px}
.pg-tags{font-weight:800;font-size:20px;color:#FFE7A3}
.pg-sticker{background:#fff;color:#1F1D2B;border-radius:16px;padding:14px 16px;font-weight:900;font-size:24px;text-align:center}
.pg-big{font-size:clamp(28px,3.4vw,44px);font-weight:900;letter-spacing:.02em}
.pg-chip{display:inline-block;background:rgba(255,255,255,.95);color:#1F1D2B;border-radius:999px;padding:4px 12px;margin:3px;font-weight:700;font-size:16px}
.pg-post{border:2px solid rgba(128,128,128,.35);border-radius:18px;padding:14px 16px;margin-bottom:6px}
.pg-head{display:flex;justify-content:space-between;align-items:center;font-weight:800}
.pg-bot{background:#1F1D2B;color:#fff;border-radius:999px;padding:2px 10px;font-size:14px}
.pg-trend{background:#F2B134;color:#1F1D2B;border-radius:999px;padding:2px 10px;font-size:14px;font-weight:900}
</style>""", unsafe_allow_html=True)
GRADS = ["linear-gradient(160deg,#D9483B,#F2B134)", "linear-gradient(160deg,#2E5E9E,#8E5EC2)",
         "linear-gradient(160deg,#2F7D62,#7FC3A0)", "linear-gradient(160deg,#8E2E3B,#D9485A)",
         "linear-gradient(160deg,#3B3452,#C05C7E)", "linear-gradient(160deg,#B7791F,#E9A85C)"]
grad = lambda h: GRADS[sum(map(ord, h)) % len(GRADS)]

def story_card(p, card, show_guesses=False):
    bars = "".join(f'<i class="{"on" if i <= card else ""}"></i>' for i in range(1, 5))
    ava = esc(p["handle"].lstrip("@")[:1].upper() or "?")
    body = ""
    if card == 1:
        body = f'<div class="pg-big">{esc(p["handle"])}</div><div class="pg-muted">posted a new story...</div><div class="pg-text">🥧 Enemy Pie: the missing part</div>'
    elif card == 2:
        body = f'<div class="pg-muted">{esc(START_LINE)}</div><div class="pg-text">{esc(p["setup"])}</div>'
    elif card == 3:
        body = f'<div class="pg-text">{esc(p["setup"])}</div><div class="pg-sticker">🤔 What happens next?<br><span style="font-size:16px;font-weight:700">Type your guess on your device!</span></div>'
        if show_guesses and p["guesses"]:
            body += "<div>" + "".join(f'<span class="pg-chip">{esc(g)}</span>' for _, g in p["guesses"][-18:]) + "</div>"
    else:
        body = (f'<div class="pg-big">💥 TO MY SURPRISE...</div><div class="pg-text">{esc(p["twist"])}</div>'
                f'<div class="pg-muted">{esc(END_LINE)}</div><div class="pg-tags">{esc(" ".join(p["tags"]))}</div>')
        if show_guesses:
            y, n = len(p["saw"]["yes"]), len(p["saw"]["no"])
            body += f'<div class="pg-sticker">Did you see it coming?  👀 {y} yes · 😱 {n} no</div>'
    return (f'<div class="pg-card" style="background:{grad(p["handle"])}"><div class="pg-bars">{bars}</div>'
            f'<div class="pg-user"><span class="pg-ava">{ava}</span>{esc(p["handle"])} · {CARD_NAMES[card]}</div>{body}</div>')

# ============================================================
# 4. Join screen
# ============================================================
class_code = st.secrets.get("CLASS_CODE", "")
teacher_code = st.secrets.get("TEACHER_CODE", "")
if not ss.me:
    st.title("📸 PieGram")
    st.write("Share your group's plot twist like a social media post!")
    nick = st.text_input("Your nickname (not your full name)", max_chars=12)
    code = st.text_input("Class code", type="password") if class_code else ""
    with st.expander("Teacher"):
        tcode = st.text_input("Teacher code", type="password")
    if st.button("Join", type="primary"):
        if class_code and code != class_code and not (teacher_code and tcode == teacher_code):
            st.error("Wrong class code. Ask your teacher.")
        elif not nick.strip():
            st.error("Write a nickname.")
        else:
            ss.me = nick.strip()
            ss.teacher = bool(teacher_code) and tcode == teacher_code
            st.rerun()
    st.stop()

# ============================================================
# 5. Teacher controls
# ============================================================
def teacher_panel():
    with st.sidebar:
        st.header("🧑‍🏫 Teacher")
        phase = B["phase"]
        st.caption(f"Now: **{phase}** · {len(human_posts())} group posts + {len(BOT_POSTS)} bot posts")
        c1, c2 = st.columns(2)
        if c1.button("1 · Drop the feed", use_container_width=True, disabled=phase != "posting"):
            with B["lock"]:
                assign_labels(); B["phase"] = "feed"
            st.rerun()
        if c2.button("2 · Reveal bots", use_container_width=True, disabled=phase != "feed"):
            with B["lock"]: B["phase"] = "reveal"
            st.rerun()
        st.divider()
        st.subheader("3 · Live stories")
        hp = human_posts()
        if hp:
            names = [p["handle"] for p in hp]
            cur = next((i for i, p in enumerate(hp) if p["id"] == B["now"]), 0)
            pick = st.selectbox("Presenting now", names, index=cur)
            chosen = hp[names.index(pick)]
            a, b, c = st.columns(3)
            if a.button("◀", use_container_width=True):
                with B["lock"]: B["now"] = chosen["id"]; B["card"] = max(1, B["card"] - 1); B["phase"] = "live"
                st.rerun()
            if b.button("Start", use_container_width=True):
                with B["lock"]: B["now"] = chosen["id"]; B["card"] = 1; B["phase"] = "live"
                st.rerun()
            if c.button("▶", use_container_width=True):
                with B["lock"]: B["now"] = chosen["id"]; B["card"] = min(4, B["card"] + 1); B["phase"] = "live"
                st.rerun()
            st.caption(f"Card {B['card']}/4 · {CARD_NAMES[B['card']]}")
        else:
            st.caption("No group posts yet.")
        st.divider()
        with st.expander("Delete a comment"):
            for p in all_posts():
                for cm in list(p["comments"]):
                    if st.button(f"🗑 {p['handle']}: {cm['nick']} — {cm['text'][:30]}", key="del" + cm["id"]):
                        with B["lock"]: p["comments"].remove(cm)
                        st.rerun()
        with st.expander("Reset the board"):
            if st.button("Delete all group posts and start again"):
                with B["lock"]:
                    for pid in [p["id"] for p in human_posts()]: del B["posts"][pid]
                    for p in all_posts():
                        p.update({"react": {k: set() for k in REACTIONS}, "bot_votes": set(), "comments": [], "guesses": [],
                                  "saw": {"yes": set(), "no": set()}, "label": ""})
                    B.update({"phase": "posting", "now": None, "card": 1})
                st.rerun()

if ss.teacher:
    teacher_panel()

# ============================================================
# 6. Screens
# ============================================================
st.title("📸 PieGram")
st.caption(f"Signed in as **{ss.me}**" + (" · teacher" if ss.teacher else ""))

def post_form():
    st.subheader("📝 Post your group's twist")
    st.caption("Only the Writer posts, once per group. Copy your paragraph from the worksheet.")
    mine = next((p for p in human_posts() if p["handle"] == ss.my_handle), None)
    with st.form("post"):
        handle = st.text_input("Group account name (your Bakery name)", value=(mine or {}).get("handle", "@"), max_chars=24)
        setup = st.text_area("Part 1 · Before the twist (stop right before the surprise!)", value=(mine or {}).get("setup", ""), height=110)
        twist = st.text_area("Part 2 · The twist (start with 'To my surprise,' or 'But actually,')", value=(mine or {}).get("twist", ""), height=110)
        tags = st.text_input("3 hashtags that sum up your twist", value=" ".join((mine or {}).get("tags", [])), placeholder="#BestEnemy #ToMySurprise #EnemyCookies")
        sent = st.form_submit_button("Post", type="primary")
    if sent:
        h = clean_handle(handle)
        if len(h) < 3 or not setup.strip() or not twist.strip():
            st.error("Fill in the account name and both parts.")
        else:
            ok, msg = upsert_post(h, setup.strip(), twist.strip(), clean_tags(tags), old_handle=ss.my_handle)
            if ok:
                ss.my_handle = h
                st.success(msg + " Wait for the teacher to drop the feed.")
            else:
                st.error(msg)

def toggle(sset):
    with B["lock"]:
        if ss.me in sset: sset.discard(ss.me)
        else: sset.add(ss.me)

@st.fragment(run_every=3)
def feed():
    phase = B["phase"]
    reveal = phase in ("reveal", "live")
    posts = sorted(all_posts(), key=lambda p: p["label"])
    if reveal:
        top = ranked()[0] if posts else None
        st.subheader("🤖 Bots revealed! · 🔥 Trending")
        for i, p in enumerate(ranked()[:3]):
            st.markdown(f"**#{i+1}** {md(p['handle'])} — 😱 {len(p['react']['wow'])} · 🤣 {len(p['react']['lol'])} · 🕵️ {len(p['react']['clue'])}" + (" 🤖" if p["bot"] else ""))
    else:
        st.subheader("📱 Feed")
        st.caption("Read every post. React, comment, and tap 🤖 if you think an AI wrote it. Account names are hidden until the reveal!")
    for p in posts:
        with st.container(border=True):
            name = esc(p["handle"]) if reveal else p["label"]
            badge = (' <span class="pg-bot">🤖 BOT · written by AI</span>' if p["bot"] else ' <span class="pg-trend">🙋 human</span>') if reveal else ""
            if reveal and top and p["id"] == top["id"]: badge += ' <span class="pg-trend">🔥 Trending #1</span>'
            st.markdown(f'<div class="pg-head"><span>{name}{badge}</span><span>🤖 suspects: {len(p["bot_votes"])}</span></div>', unsafe_allow_html=True)
            st.markdown(f"*{md(START_LINE)}* {md(p['setup'])} **{md(p['twist'])}** *{md(END_LINE)}*")
            if p["tags"]: st.markdown(f"**{md(' '.join(p['tags']))}**")
            cols = st.columns(4)
            for (k, label), col in zip(REACTIONS.items(), cols):
                on = ss.me in p["react"][k]
                if col.button(f"{label.split()[0]} {len(p['react'][k])}", key=f"r{k}{p['id']}", type="primary" if on else "secondary",
                              help=label, use_container_width=True):
                    toggle(p["react"][k]); st.rerun()
            if not reveal:
                on = ss.me in p["bot_votes"]
                if cols[3].button("🤖 AI?" + (" ✓" if on else ""), key=f"b{p['id']}", type="primary" if on else "secondary", use_container_width=True):
                    toggle(p["bot_votes"]); st.rerun()
            for cm in p["comments"][-6:]:
                st.markdown(f"💬 **{md(cm['nick'])}**: {md(cm['text'])}")
            with st.expander("💬 Comment"):
                f = st.selectbox("Sentence frame", COMMENT_FRAMES, key=f"f{p['id']}")
                blank = st.text_input("Fill in the blank", key=f"t{p['id']}", max_chars=50)
                if st.button("Send comment", key=f"s{p['id']}"):
                    if blank.strip():
                        with B["lock"]:
                            p["comments"].append({"id": uuid.uuid4().hex[:6], "nick": ss.me, "text": f.replace("___", blank.strip())[:90]})
                        st.rerun()

@st.fragment(run_every=2)
def live():
    p = B["posts"].get(B["now"])
    if not p:
        st.info("Waiting for the first story...")
        return
    card = B["card"]
    left, right = st.columns([3, 2]) if ss.teacher else (st.container(), st.container())
    with left:
        st.markdown(story_card(p, card, show_guesses=ss.teacher), unsafe_allow_html=True)
    with right:
        if card == 3:
            already = any(n == ss.me for n, _ in p["guesses"])
            if ss.teacher:
                st.metric("Guesses", len(p["guesses"]))
            elif already:
                st.success("Guess sent! Look at the big screen.")
            else:
                g = st.text_input("What happens next? (one short sentence)", key=f"g{p['id']}", max_chars=60)
                if st.button("Send my guess", type="primary", key=f"gs{p['id']}") and g.strip():
                    with B["lock"]: p["guesses"].append((ss.me, g.strip()))
                    st.rerun()
        if card == 4:
            if not ss.teacher:
                st.markdown("**Did you see it coming?**")
                a, b = st.columns(2)
                if a.button(f"👀 Yes {len(p['saw']['yes'])}", key=f"sy{p['id']}", use_container_width=True):
                    with B["lock"]: p["saw"]["no"].discard(ss.me); p["saw"]["yes"].add(ss.me)
                    st.rerun()
                if b.button(f"😱 No {len(p['saw']['no'])}", key=f"sn{p['id']}", use_container_width=True):
                    with B["lock"]: p["saw"]["yes"].discard(ss.me); p["saw"]["no"].add(ss.me)
                    st.rerun()
            else:
                st.metric("Didn't see it coming 😱", len(p["saw"]["no"]))
                st.caption("Ask: Who guessed it? What was the clue?")

phase = B["phase"]
if phase == "posting":
    if ss.teacher:
        st.subheader("Group posts so far")
        for p in human_posts():
            st.markdown(f"✅ {md(p['handle'])}")
        st.caption("When every group has posted, press **1 · Drop the feed**.")
    else:
        post_form()
elif phase in ("feed", "reveal"):
    feed()
else:  # live
    tab1, tab2 = st.tabs(["🎬 Live story", "📱 Feed"])
    with tab1: live()
    with tab2: feed()
