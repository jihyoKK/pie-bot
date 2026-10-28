# Pie Bot v2 - an online "Enemy Pie" worksheet where every group member has a role
# Group = 3 students (Idea banker, Writer, Grammar checker) + Pie Bot as the Word searcher.
# A 4th student can share a role. Runs on Streamlit with the Gemini API.
# The Gemini API key lives in Streamlit "Secrets", never in this file.

import re
import time
import streamlit as st
from google import genai
from google.genai import types, errors
from shared import board, upsert_post, split_twist, clean_handle, clean_tags

# ============================================================
# 1. Settings you can change
# ============================================================
# Pie Bot tries these models in order. If one is busy or retired, the next one is used.
MODELS = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite", "gemini-flash-lite-latest"]

ROLES = {
    "Idea banker":     "suggests ideas and opinions for the group",
    "Writer":          "writes the group's answers in the worksheet",
    "Grammar checker": "checks the past tense and grammar of the group's sentences",
}
# Pie Bot is always the group's Word searcher, in a limited "hint" version,
# so the students still read the story and find the sentences themselves.
BOT_ROLE = "Word searcher"
BOT_ROLE_RULE = ("You are the group's Word searcher, but a HINT version: when students ask where something is, "
                 "tell only the paragraph number and, if they are still stuck, one key word to look for. "
                 "Never quote or copy the answer sentence. The students must read it and say it themselves.")

st.set_page_config(page_title="Pie Bot", page_icon="🥧", layout="wide")

# ============================================================
# 2. The story and the worksheet
# ============================================================
STORY = [
    "It was all good until Jeremy Ross moved into the neighborhood, right next door to my best friend Stanley. I did not like Jeremy Ross. He laughed at me when he struck me out in a baseball game. He had a party on his trampoline, and I wasn't even invited. But my best friend Stanley was.",
    "Jeremy Ross was the one and only person on my enemy list. I never even had an enemy list until he moved into the neighborhood. But as soon as he came along, I needed one. I hung it up in my tree house, where Jeremy Ross was not allowed to go.",
    "Dad understood stuff like enemies. He told me that when he was my age, he had enemies, too. But he knew of a way to get rid of them. I asked him to tell me how.",
    "\"Tell you how? I'll show you how!\" he said. He pulled a really old recipe book off the kitchen shelf. Inside, there was a worn-out scrap of paper with faded writing. Dad held it up and squinted at it. \"Enemy Pie,\" he said, satisfied. You may be wondering what exactly is in Enemy Pie. I was wondering, too. But Dad said the recipe was so secret, he couldn't even tell me. I decided it must be magic. I begged him to tell me something—anything. \"I will tell you this,\" he said. \"Enemy Pie is the fastest known way to get rid of enemies.\" Now, of course, this got my mind working. What kinds of things—disgusting things—would I put into a pie for an enemy?",
    "I brought Dad some weeds from the garden, but he just shook his head. I brought him earthworms and rocks, but he didn't think he'd need those. I gave him the gum I'd been chewing on all morning. He gave it right back to me. I went out to play, alone. I shot baskets until the ball got stuck on the roof. I threw a boomerang that never came back to me. And all the while, I listened to the sounds of my dad chopping and stirring and blending the ingredients of Enemy Pie. This could be a great summer after all.",
    None,  # the missing middle part
    "Enemy Pie was delicious! After dessert, Jeremy rode his bike home but not before inviting me over to play on his trampoline in the morning. He said he'd teach me how to flip. As for Enemy Pie, I still don't know how to make it. I still wonder if enemies really do hate it or if their hair falls out or their breath turns bad. But I don't know if I'll ever get an answer, because I just lost my best enemy.",
]

def numbered_story():
    out, n = [], 0
    for p in STORY:
        if p is None:
            out.append((None, "(The middle part is missing. Your group will write it later!)"))
        else:
            n += 1
            out.append((n, p))
    return out

STORY_TEXT = "\n\n".join(
    f"[Paragraph {n}] {p}" if n else "[ ... The middle part is missing. Students will write it later. ... ]"
    for n, p in numbered_story()
)

BOT_SUMMARY = ("Jeremy Ross moved into the neighborhood, right next door to the narrator. "
               "Jeremy laughed at the narrator when he struck him out in a soccer game. "
               "Jeremy had a trampoline party, and Stanley was invited, but the narrator was not. "
               "The narrator hung his enemy list in his bedroom. "
               "Dad found a secret recipe for Enemy Pie in an old recipe book. "
               "The narrator brought weeds, earthworms, and rocks, and Dad put all of them in the pie. "
               "After dessert, Jeremy invited the narrator to his house to teach him how to swim. "
               "In the end, the narrator lost his best enemy because Jeremy became his friend.")

DRAFTS = {
    "A": "Dad made the pie all day. I helped him a little. In the evening, Jeremy came to our house for dinner. We ate the pie together. It was good. Then Jeremy went home.",
    "B": "Dad put the pie in the oven. Suddenly, a big dragon flew into our kitchen! It ate the whole pie and flew away. Jeremy and I were very scared. We hid under the table together.",
    "C": "Dad told me to invite Jeremy for dinner. I didn't want to, but I knocked on his door. To my surprise, Jeremy was holding a plate of cookies. He said, \"My mom made these Enemy Cookies for you.\" We looked at each other and laughed. Jeremy had an enemy list, too, and I was on it!",
}
CHECKS = ["Surprising?", "Makes sense?", "Connects?", "Past tense?"]

# Each task: what students see + what Pie Bot must do + which role leads each step
PARTS = [("character", "Character"), ("background", "Background"), ("conflict", "Conflict"), ("twist", "Plot twist")]
VERDICT = {"right": "✅ Right", "close": "🟡 Close", "wrong": "❌ Wrong"}

TASKS = {
    "open": {
        "label": "0 · Open the envelope",
        "intro": "Open the class predictions from the pre-reading. Were they right? Prove it with the story!",
        "lead": "Idea banker reads a prediction · everyone looks for the words in the story · Writer marks right / close / wrong",
        "rules": """TASK: OPEN THE ENVELOPE (checking the class predictions from the pre-reading)
Before reading, the class predicted four parts of the story. They are in GROUP WORK below.
Go through them ONE AT A TIME, in this order: Character -> Background -> Conflict -> Plot twist.
For each one:
1. Read the prediction aloud (quote it) and ask: "Was it right, close, or wrong? Find the words in the story that show it."
2. If they ask where to look, give only a paragraph number (you are the Word searcher).
3. Accept a verdict only when a member points to the sentence in the story. If the verdict does not match the story, ask them to read that paragraph again.
4. Then praise them and move on to the next part.
Facts for you (do NOT tell them; use them to check): Character = the narrator ("I"), Jeremy Ross, Stanley, Dad (paragraphs 1-3). Background = summer, the neighborhood, the narrator's tree house (paragraphs 1-2, 5). Conflict = Jeremy laughed at him in a baseball game and didn't invite him to the trampoline party, so Jeremy went on his enemy list (paragraphs 1-2).
Plot twist: the middle of the story is missing, so they can only compare with the ENDING in paragraph 6 (Jeremy invited him to play; "I just lost my best enemy" - the enemy became a friend). Ask: "Did the story end the way you predicted? Was it a surprise?" Never tell what happened in the missing middle; say "You will write that part later!"
If a prediction is empty, ask the group to make a quick prediction now, then check it.
Tag: <<pred:PART:VERDICT>> when a verdict is proven, PART = character / background / conflict / twist, VERDICT = right / close / wrong.""",
    },
    "main": {
        "label": "1 · Main Idea (p.3)",
        "intro": "Collect the 4 pie pieces with evidence, then write the main idea.",
        "lead": "Ask Pie Bot (Word searcher) where to look · Idea banker suggests the main idea · Writer writes it · Grammar checker checks it",
        "rules": """TASK: MAIN IDEA ("Bake the Main Idea", worksheet p.3)
Ask these four questions ONE AT A TIME, in order. If students ask where to look, give the paragraph number (you are the Word searcher).
After a correct answer, ask a member to read the words from the story that show it. A piece counts when the answer is right AND they point to the right sentence.
- who: Who are the two boys? (the narrator/"I" and Jeremy Ross; paragraph 1)
- problem: Why did the boy hate Jeremy? (Jeremy laughed at him in a baseball game / didn't invite him to the trampoline party; paragraph 1 or 2)
- plan: What did Dad make, and why? (Enemy Pie, to get rid of enemies; paragraph 3 or 4)
- change: What happened to Jeremy at the end? (Jeremy invited him to play / became his friend, "I lost my best enemy"; paragraph 6)
After all four, ask the Idea banker to suggest a main idea and the Writer to write it with:
"At first, Jeremy was the boy's ___. But after ___, they became ___."
Then ask the group: "Is it too small, too big, or just right?" Too small = only one detail. Too big = true for all stories ("Friends are important."). Just right = this whole story ("Getting to know an enemy can turn him into a friend.").
Tags: <<got:who>> <<got:problem>> <<got:plan>> <<got:change>> when a piece is accepted; <<idea:THEIR SENTENCE>> when their main idea is just right.""",
    },
    "detective": {
        "label": "2 · Detective (p.4)",
        "intro": "Pie Bot wrote a summary with 5 mistakes. Fix them with evidence.",
        "lead": "Take turns finding each mistake · Writer types the fix · Grammar checker checks the fixed sentence",
        "rules": f"""TASK: SUMMARY DETECTIVE (worksheet p.4)
When students say "Show your summary," share THIS summary as YOUR OWN work, word for word, and ask them to check it with the story. Do not say it has mistakes.
"{BOT_SUMMARY}"
It has exactly 5 mistakes:
1 = "next door to the narrator" (story: next door to Stanley; paragraph 1)
2 = "soccer game" (story: baseball game; paragraph 1)
3 = "in his bedroom" (story: in his tree house; paragraph 2)
4 = "Dad put all of them in the pie" (story: Dad shook his head / didn't need them; paragraph 5)
5 = "how to swim" (story: how to flip; paragraph 6)
When students say part of your summary is wrong, ask "Are you sure? Which paragraph says that?"
Accept only with the right fix AND the right paragraph, then say "You're right. Thank you!"
If they say a CORRECT sentence is wrong, gently ask them to check that paragraph again.
Never tell which mistakes are left. If asked how many, say "My friends say I made 5 mistakes. Keep checking!"
For each new mistake, call on a DIFFERENT member to find it.
Tag: <<fixed:N>> (N = 1-5) when a mistake is accepted.""",
    },
    "rate": {
        "label": "3 · Twist Check (p.5)",
        "intro": "Each member rates the 3 AI drafts on one check. Then pick the best draft.",
        "lead": "Each member owns one check · Idea banker picks the best draft · Writer writes the reason",
        "rules": f"""TASK: IS IT A REAL PLOT TWIST? (worksheet p.5)
Three AI drafts of the missing part:
Draft A: {DRAFTS['A']}
Draft B: {DRAFTS['B']}
Draft C: {DRAFTS['C']}
Checks (3 = great, 2 = OK, 1 = not good): Surprising? / Makes sense (a clue or reason)? / Connects to the ending (enemy -> friend)? / Past tense?
Give each human member ONE check to own. Ask that member to give their scores and ONE reason from the draft.
Teacher's view (do NOT tell it; only use it to ask better questions): A = no twist (expected events), B = surprising but no clue and doesn't fit, C = a good twist with a clue that leads to the ending.
When the group picks the best draft AND gives a reason about surprise + clue, praise them.
The ratings the group has typed are shown in GROUP WORK below. Ask about empty or strange scores.
Tag: <<rated>> when the group has picked a best draft with a good reason.""",
    },
    "twist": {
        "label": "4 · Our Twist (p.6)",
        "intro": "Plan your own twist and write the missing part. Don't copy the AI drafts!",
        "lead": "Idea banker leads the planner · Writer writes · Grammar checker checks past tense · Pie Bot only asks questions",
        "rules": """TASK: WRITE OUR PLOT TWIST (worksheet p.6)
The group plans a NEW twist (Readers expect... / But actually... / Clue / How it leads to the ending) and writes the missing part.
It starts after "I was wondering what dirty thing I had to put in the pie." and ends before "Jeremy invited me over to his house. I lost my best enemy."
Guideline: 5+ sentences, past tense, use "To my surprise," or "But actually," once, different from the AI drafts A-C.
NEVER write the twist, a sentence, or an idea for them. Ask questions instead: "What do readers expect?", "Where is the clue?", "How does it lead to the ending?"
If their twist copies an AI draft, say so kindly and ask for a new idea.
When the group asks for a check, look at GROUP WORK below. Point out problems by sentence number only (e.g., "Sentence 3: check the verb tense."). Count their sentences.
Tag: <<twist_ok>> when the paragraph has 5+ sentences, a real twist with a clue, and mostly correct past tense.""",
    },
}
TASK_KEYS = list(TASKS)

# ============================================================
# 3. Memory for this browser tab
# ============================================================
ss = st.session_state
defaults = {
    "setup_done": False, "group": "Group 1", "members": [],
    "messages": [], "talk": {}, "last_speaker": None,
    "got": set(), "fixed": set(), "idea": "", "rated": False, "twist_ok": False,
    "preds": {"character": "", "background": "", "conflict": "", "twist": ""}, "pred_check": {},
    "hint_level": 0, "unlocked": False,
    "ratings": {}, "best": "", "best_reason": "",
    "plan": {"expect": "", "actually": "", "clue": "", "ending": ""}, "paragraph": "",
}
for k, v in defaults.items():
    if k not in ss:
        ss[k] = v.copy() if isinstance(v, (dict, list, set)) else v

TAG = re.compile(r"<<[^>]*>>")
def strip_tags(t): return TAG.sub("", t).strip()

def apply_tags(text):
    for m in re.finditer(r"<<got:(who|problem|plan|change)>>", text, re.I):
        ss.got.add(m.group(1).lower()); ss.hint_level = 0
    for m in re.finditer(r"<<fixed:\s*([1-5])>>", text):
        ss.fixed.add(m.group(1)); ss.hint_level = 0
    m = re.search(r"<<idea:([^>]{3,200})>>", text)
    if m: ss.idea = m.group(1).strip()
    if "<<rated>>" in text: ss.rated = True
    if "<<twist_ok>>" in text: ss.twist_ok = True
    for m in re.finditer(r"<<pred:\s*(character|background|conflict|twist)\s*:\s*(right|close|wrong)>>", text, re.I):
        ss.pred_check[m.group(1).lower()] = m.group(2).lower()

def parse_predictions(raw):
    """Read the text copied from the pre-reading 'Seal' screen: 'Character: ... (2 stars)'."""
    out = {}
    for line in raw.splitlines():
        m = re.match(r"\s*(Character|Background|Conflict|Plot twist)\s*:\s*(.*)$", line, re.I)
        if m:
            key = {"plot twist": "twist"}.get(m.group(1).lower(), m.group(1).lower())
            text = re.sub(r"\(\s*\d\s*stars?\s*\)\s*$", "", m.group(2)).strip()
            out[key] = "" if text == "-" else text
    return out

def slices_done():
    return {"open": len(ss.pred_check) == 4, "main": bool(ss.idea), "detective": len(ss.fixed) == 5,
            "rate": ss.rated, "twist": ss.twist_ok}
BAKERY = ["main", "detective", "rate", "twist"]

# ============================================================
# 4. Pie Bot's instructions
# ============================================================
def team_text():
    lines = [f"- {m['name']} = {m['role']} ({ROLES[m['role']]}); has spoken {ss.talk.get(m['name'], 0)} times"
             for m in ss.members]
    lines.append(f"- Pie Bot (you) = {BOT_ROLE}. {BOT_ROLE_RULE}")
    return "\n".join(lines)

def work_text(task):
    if task == "open":
        return "\n".join(f"{label}: {ss.preds.get(k) or '(empty)'}  -> checked: {ss.pred_check.get(k, 'not yet')}" for k, label in PARTS)
    if task == "rate":
        rows = [f"Draft {d}: " + ", ".join(f"{c} {ss.ratings.get((d, c), '-')}" for c in CHECKS) for d in DRAFTS]
        return "\n".join(rows) + f"\nBest draft: {ss.best or '-'} / Reason: {ss.best_reason or '-'}"
    if task == "twist":
        p = ss.plan
        return (f"Readers expect: {p['expect'] or '-'}\nBut actually: {p['actually'] or '-'}\n"
                f"Clue: {p['clue'] or '-'}\nHow it leads to the ending: {p['ending'] or '-'}\n"
                f"Paragraph: {ss.paragraph or '-'}")
    return "(see the chat)"

def rules(task):
    quiet = min(ss.members, key=lambda m: ss.talk.get(m["name"], 0))["name"] if ss.members else "a member"
    return f"""You are "Pie Bot," an AI member of {ss.group} in a Korean middle school English class (Grade 3, mixed level).
The group is doing the "Enemy Pie" worksheet. You help like a friendly classmate, not like a teacher who gives answers.

THE TEAM
{team_text()}
Each student message starts with [name · role].

TEAMWORK RULES (most important)
- End EVERY reply by calling on ONE human member by name and role with a small, clear job. Example: "Mina (Word searcher), can you find it in paragraph 2?"
- Spread the talking. Prefer members who have spoken the least. The quietest member now is {quiet}. Do not call on the same person twice in a row.
- If one member answers many times in a row, say kindly: "Great! Let's hear from someone else," and call on a quiet member.
- Match jobs to roles: Idea banker -> give an idea or opinion, Writer -> write the sentence, Grammar checker -> check the verbs. Any member can read the story to find evidence; take turns.

HINT LADDER (for members who are stuck)
When a member writes "Hint, please (level N)":
- level 1: give only the paragraph number.
- level 2: give one key word to look for, with its Korean meaning in brackets.
- level 3: give a sentence frame with blanks, like "He laughed at me when ___." Never the full answer.

HOW TO TALK
- Easy English (CEFR A2). 1-3 short sentences, then the call-on sentence. No lists, no markdown.
- Never give the answer directly. Only use facts from the story. If not sure, say "Let's check the story together."
- The middle part of the story is missing. Never guess or tell what happened there (for example, Dad's real plan). If asked: "That's a secret! You will write it later."
- If students write in Korean, answer in English and add one key word in Korean in brackets, like "enemy (적)".
- Praise good evidence and good teamwork.

THE STORY (paragraph numbers are what students see):
{STORY_TEXT}

{TASKS[task]['rules']}

GROUP WORK SO FAR
{work_text(task)}

PROGRESS TAGS: At the very END of your reply, on its own line, add tags only for what was completed IN THIS REPLY. Students do not see tags. No tag if nothing new.
ALREADY DONE (do not award again): pieces {sorted(ss.got) or 'none'}; mistakes fixed {sorted(ss.fixed) or 'none'}; main idea {ss.idea or 'not yet'}; twist check {'done' if ss.rated else 'not yet'}; our twist {'ok' if ss.twist_ok else 'not yet'}; predictions checked {ss.pred_check or 'none'}."""

# ============================================================
# 5. Optional class code (so strangers can't use your free quota)
# ============================================================
class_code = st.secrets.get("CLASS_CODE", "")
if class_code and not ss.unlocked:
    st.title("🥧 Pie Bot")
    code = st.text_input("Class code", type="password")
    if st.button("Enter"):
        if code == class_code:
            ss.unlocked = True
            st.rerun()
        else:
            st.error("Wrong code. Ask your teacher.")
    st.stop()

# ============================================================
# 6. Team setup screen
# ============================================================
if not ss.setup_done:
    st.title("🥧 Pie Bot · Team setup")
    st.write("Every member needs a role. Use a nickname or your seat letter (not your full name).")
    group = st.text_input("Group name", value=ss.group, max_chars=20)
    size = st.radio("Our group", ["3 students + Pie Bot", "4 students + Pie Bot"], horizontal=True)
    n = 3 if size.startswith("3") else 4
    st.caption("🥧 Pie Bot is always your Word searcher. It tells you WHERE to look, and you read and find the words.")
    role_names = list(ROLES)
    names, roles = [], []
    cols = st.columns(n)
    for i in range(n):
        with cols[i]:
            names.append(st.text_input(f"Member {i+1}", value="ABCD"[i], max_chars=12, key=f"name{i}"))
            roles.append(st.selectbox("Role", role_names, index=i % 3, key=f"role{i}"))
    if n == 4:
        st.caption("With 4 students, two members share one role.")
    problems = []
    if set(roles) != set(role_names): problems.append("Every role needs at least one member: Idea banker, Writer, Grammar checker.")
    if len({x.strip().lower() for x in names}) != n or any(not x.strip() for x in names): problems.append("Each member needs a different nickname.")
    for p in problems: st.warning(p)
    if st.button("Start!", type="primary", disabled=bool(problems)):
        ss.group = group.strip() or "Group 1"
        ss.members = [{"name": nm.strip(), "role": r} for nm, r in zip(names, roles)]
        ss.talk = {m["name"]: 0 for m in ss.members}
        ss.setup_done = True
        st.rerun()
    st.stop()

# ============================================================
# 7. Talking to Gemini
# ============================================================
@st.cache_resource
def get_client():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

def ask_pie_bot(task):
    history = [types.Content(role="user", parts=[types.Part(text="(The group opened the chat.)")])]
    for m in ss.messages[-24:]:
        history.append(types.Content(role="user" if m["role"] == "user" else "model",
                                     parts=[types.Part(text=m["content"])]))
    config = types.GenerateContentConfig(system_instruction=rules(task), temperature=0.6)
    last_error = None
    for model in MODELS:
        for attempt in range(2):
            try:
                r = get_client().models.generate_content(model=model, contents=history, config=config)
                return r.text or ""
            except errors.ServerError as e:      # Google is busy -> wait, retry, then next model
                last_error = e
                time.sleep(1.5)
            except errors.ClientError as e:
                last_error = e
                if getattr(e, "code", None) in (404, 429):
                    break
                raise
    raise last_error

def explain(e):
    code = getattr(e, "code", None)
    msg = str(getattr(e, "message", "") or e)[:300]
    hints = {400: "The API key may be wrong. Copy it again into Secrets.", 401: "This key is not allowed. Make a new key.",
             403: "This key is not allowed. Make a new key.", 404: "Google could not find the model. Add a newer model to MODELS.",
             429: "The free limit is used up for now. Wait a minute.", 500: "Google's AI is busy. Wait a minute.",
             503: "Google's AI is busy. Wait a minute."}
    return f"{hints.get(code, 'See the message below.')}\n\nError {code}: {msg}"

# ============================================================
# 8. Screen
# ============================================================
done = slices_done()
with st.sidebar:
    st.header(f"🥧 {ss.group}")
    st.subheader("✉️ Envelope")
    for k, label in PARTS:
        st.markdown(f"{VERDICT.get(ss.pred_check.get(k), '⬜ not yet')} · {label}")
    st.divider()
    st.subheader("Our Pie Bakery")
    for k in BAKERY:
        st.markdown(("🟥 " if done[k] else "⬜ ") + TASKS[k]["label"])
    st.progress(sum(done[k] for k in BAKERY) / 4)
    st.caption(f"Pieces: {len(ss.got)}/4 · Mistakes fixed: {len(ss.fixed)}/5")
    if ss.idea: st.markdown(f"**Main idea:** {ss.idea}")
    st.divider()
    st.subheader("🗣️ Talk meter")
    top = max(ss.talk.values(), default=0) or 1
    for m in ss.members:
        c = ss.talk.get(m["name"], 0)
        st.markdown(f"**{m['name']}** · {m['role']} — {c}")
        st.progress(c / top)
    st.caption(f"🥧 Pie Bot · {BOT_ROLE} (hints only)")
    st.divider()
    with st.expander("Teacher"):
        if st.button("Reset this group", use_container_width=True):
            for k in list(ss.keys()):
                if k != "unlocked": del ss[k]
            st.rerun()

st.title("🥧 Pie Bot")
task = st.radio("Activity", TASK_KEYS, format_func=lambda k: ("✅ " if done[k] else "") + TASKS[k]["label"],
                horizontal=True, label_visibility="collapsed", key="task")
t = TASKS[task]
st.markdown(f"**{t['intro']}**")
st.caption("Who leads: " + t["lead"])

with st.expander("📖 Read the story"):
    for n_, p in numbered_story():
        st.markdown(f"**{n_}.** {p}" if n_ else f"*… {p}*")

# the envelope (class predictions)
if task == "open":
    with st.container(border=True):
        st.markdown("**✉️ Our class predictions**")
        raw = st.text_area("Paste the predictions from the pre-reading (Copy predictions), or type them.",
                           key="pred_paste", height=120,
                           placeholder="Our predictions:\nCharacter: ...\nBackground: ...\nConflict: ...\nPlot twist: ...")
        if st.button("Open the envelope", type="primary"):
            parsed = parse_predictions(raw)
            if parsed:
                ss.preds.update(parsed); ss.pred_check = {}
            else:
                st.warning("I can't read it. Write one line per part, like 'Character: a new boy'.")
        cols = st.columns(4)
        for (k, label), col in zip(PARTS, cols):
            with col:
                st.markdown(f"**{label}**")
                st.write(ss.preds.get(k) or "—")
                st.caption(VERDICT.get(ss.pred_check.get(k), "not checked yet"))

# worksheet boxes for p.5 and p.6
if task == "rate":
    with st.container(border=True):
        for d, text in DRAFTS.items():
            st.markdown(f"**Draft {d}.** {text}")
        st.markdown("**Rate each draft** (3 = great, 2 = OK, 1 = not good)")
        head = st.columns([2, 1, 1, 1])
        head[0].markdown("**Check**")
        for i, d in enumerate(DRAFTS): head[i + 1].markdown(f"**{d}**")
        for c in CHECKS:
            row = st.columns([2, 1, 1, 1])
            row[0].write(c)
            for i, d in enumerate(DRAFTS):
                ss.ratings[(d, c)] = row[i + 1].selectbox(f"{c} {d}", ["-", 3, 2, 1], key=f"r_{d}_{c}",
                                                          label_visibility="collapsed")
        b1, b2 = st.columns([1, 3])
        ss.best = b1.selectbox("Best draft", ["", "A", "B", "C"], key="best_sel")
        ss.best_reason = b2.text_input("Because...", key="best_reason_in")
if task == "twist":
    with st.container(border=True):
        st.markdown("**Twist Planner** · Don't copy the AI drafts!")
        a, b = st.columns(2)
        ss.plan["expect"] = a.text_area("1 · Readers expect...", key="p_expect", height=80)
        ss.plan["actually"] = b.text_area("2 · But actually... (the twist)", key="p_actually", height=80)
        ss.plan["clue"] = a.text_area("3 · Clue: why it makes sense", key="p_clue", height=80)
        ss.plan["ending"] = b.text_area("4 · How it leads to the ending", key="p_ending", height=80)
        st.caption("Word bank: was · found · saw · said · laughed · realized · knocked · thought")
        st.markdown("*I was wondering what dirty thing I had to put in the pie.*")
        ss.paragraph = st.text_area("Our paragraph (5+ sentences, past tense, use 'To my surprise,' once)",
                                    key="p_par", height=180)
        st.markdown("*Jeremy invited me over to his house. I lost my best enemy. Enemy pie turned the enemy into my friend.*")
        st.caption(f"Sentences: {len([s for s in re.split(r'[.!?]+', ss.paragraph) if s.strip()])}")
    with st.container(border=True):
        st.markdown("**📸 Share on PieGram** · Writer only, when your paragraph is ready")
        ss.setdefault("pg_handle", "")
        a, b = st.columns(2)
        handle_in = a.text_input("Group account name (your Bakery name)", value=ss.pg_handle or "@" + re.sub(r"\W+", "_", ss.group.lower()), key="pg_handle_in", max_chars=24)
        tags_in = b.text_input("3 hashtags", key="pg_tags_in", placeholder="#BestEnemy #ToMySurprise #EnemyCookies")
        if st.button("📸 Post to PieGram", type="primary"):
            parts = split_twist(ss.paragraph)
            if not parts:
                st.error("Start your twist with 'To my surprise,' or 'But actually,' so PieGram knows where the surprise begins.")
            elif not clean_tags(tags_in):
                st.error("Add your 3 hashtags first.")
            else:
                h = clean_handle(handle_in)
                ok, msg = upsert_post(h, parts[0], parts[1], clean_tags(tags_in), old_handle=ss.pg_handle)
                if ok:
                    ss.pg_handle = h
                    st.success(f"{msg} Your account: {h}. You can post again to update it until the feed opens.")
                else:
                    st.error(msg)
        elif ss.pg_handle:
            st.caption(f"Posted as {ss.pg_handle} ✓ (post again to update)")

# chat history
for m in ss.messages:
    if m["role"] == "user":
        with st.chat_message("user", avatar="🙋"):
            st.write(m["content"])
    else:
        with st.chat_message("assistant", avatar="🥧"):
            st.write(strip_tags(m["content"]))

# who is talking + quick buttons
labels = [f"{m['name']} · {m['role']}" for m in ss.members]
speaker = st.radio("Who is talking? (choose every time)", labels, horizontal=True, key="speaker", index=None)
starters = {"open": ("Let's check!", "We opened the envelope. Let's check our predictions!"),
            "main": ("Let's start!", "Let's find the main idea!"), "detective": ("Show your summary", "Show your summary"),
            "rate": ("Let's start!", "Let's rate the drafts!"), "twist": ("Check our twist", "Please check our twist.")}
c1, c2, c3 = st.columns(3)
quick = None
if c1.button(starters[task][0], use_container_width=True):
    quick = starters[task][1]
if c2.button(f"Where should we look? (hint {min(ss.hint_level + 1, 3)})", use_container_width=True):
    ss.hint_level = min(ss.hint_level + 1, 3)
    quick = f"Hint, please (level {ss.hint_level})"
if c3.button("I'm done. Next person!", use_container_width=True):
    quick = "I'm done with my part. Who is next?"

typed = st.chat_input("Type your answer...")
user_text = quick or typed

if user_text and speaker not in labels:
    st.warning("First choose who is talking, then send again.")
    user_text = None

if user_text:
    name = ss.members[labels.index(speaker)]["name"]
    line = f"[{speaker}] {user_text}"
    ss.messages.append({"role": "user", "content": line})
    ss.talk[name] = ss.talk.get(name, 0) + 1
    with st.chat_message("user", avatar="🙋"):
        st.write(line)
    with st.chat_message("assistant", avatar="🥧"):
        with st.spinner("Pie Bot is thinking..."):
            try:
                answer = ask_pie_bot(task)
            except KeyError:
                ss.messages.pop(); ss.talk[name] -= 1
                st.error("The API key is missing. In Streamlit, open Settings > Secrets and add GEMINI_API_KEY.")
                st.stop()
            except Exception as e:
                ss.messages.pop(); ss.talk[name] -= 1
                st.error("Pie Bot could not answer. Try again in a minute.")
                with st.expander("For the teacher: why it failed"):
                    st.code(explain(e), language=None)
                st.stop()
        st.write(strip_tags(answer) or "Hmm, can you say that again?")
    ss.messages.append({"role": "assistant", "content": answer})
    apply_tags(answer)
    ss.pop("speaker", None)          # next message: choose the speaker again
    st.rerun()
