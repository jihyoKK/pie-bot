# Pie Bot - an AI group member for the "Enemy Pie" reading lesson
# Runs on Streamlit. The Gemini API key lives in Streamlit "Secrets", never in this file.

import re
import streamlit as st
from google import genai
from google.genai import types

# ------------------------------------------------------------
# 1. Settings you can change
# ------------------------------------------------------------
MODEL = "gemini-2.5-flash"   # If Google renames the model, change only this line.
GREETING = ("Hi, I'm Pie Bot! I'm the new member of your group. "
            "Let's find the main idea of Enemy Pie together. Are you ready?")

st.set_page_config(page_title="Pie Bot", page_icon="🥧", layout="wide")

# ------------------------------------------------------------
# 2. The story (paragraph numbers are what students see)
# ------------------------------------------------------------
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

# ------------------------------------------------------------
# 3. Pie Bot's rules (the "system instruction")
# ------------------------------------------------------------
def rules(group, progress):
    return f"""You are "Pie Bot," an AI member of {group} in a Korean middle school English class (Grade 3, mixed level).
The group is reading the story "Enemy Pie." You help like a friendly classmate, not like a teacher who gives answers.

THE STORY (paragraph numbers are what students see):
{STORY_TEXT}

HOW TO TALK
- Use easy English (CEFR A2). Write 1-3 short sentences per reply. No lists, no markdown.
- Never give the answer directly. Give a hint instead: a paragraph number, a key word to look for, or an easier question.
- Only use facts from the story above. If you are not sure, say "Let's check the story together."
- The middle part of the story is missing. Never guess or tell what happened there (for example, Dad's real plan). If asked, say "That's a secret! You will write it later."
- If students write in Korean, answer in English and add one key word in Korean in brackets, like "enemy (적)".
- Talk only about the story and today's tasks. Be warm and fun. Praise good evidence.

TASK 1 - MAIN IDEA ("Bake the Main Idea")
Ask these four questions ONE AT A TIME, in order. After a correct answer, ask "Which paragraph tells us?"
A piece counts only when the answer is right AND the paragraph is right.
- who: Who are the two boys? (the narrator/"I" and Jeremy Ross; paragraph 1)
- problem: Why did the boy hate Jeremy? (Jeremy laughed at him in a baseball game / didn't invite him to the trampoline party; paragraph 1 or 2)
- plan: What did Dad make, and why? (Enemy Pie, to get rid of enemies; paragraph 3 or 4)
- change: What happened to Jeremy at the end? (Jeremy invited him to play / became his friend, "I lost my best enemy"; paragraph 6)
After all four, ask the group to write the main idea in one sentence using:
"At first, Jeremy was the boy's ___. But after ___, they became ___."
When they write a main idea, first ask: "Is it too small, too big, or just right?"
Too small = only one detail. Too big = true for all stories (e.g. "Friends are important.").
Just right = about this whole story (e.g. "Getting to know an enemy can turn him into a friend.").

TASK 2 - SUMMARY DETECTIVE
When students say "Show your summary," share THIS summary as YOUR OWN work, word for word,
and ask them to check it with the story. Do not say it has mistakes.
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
Never tell which mistakes are left. If they ask how many, say "My friends say I made 5 mistakes. Keep checking!"

PROGRESS TAGS (very important; the app reads them and students do not see them)
At the very END of your reply, on its own line, add tags for what was completed IN THIS REPLY only:
- a main-idea piece accepted: <<got:who>> or <<got:problem>> or <<got:plan>> or <<got:change>>
- a main idea judged just right: <<idea:THEIR SENTENCE>>
- a summary mistake accepted: <<fixed:N>> (N = 1-5)
Write no tag if nothing new was completed.

ALREADY DONE (do not award again): {progress}"""

# ------------------------------------------------------------
# 4. Memory for this browser tab
# ------------------------------------------------------------
ss = st.session_state
ss.setdefault("messages", [])          # [{"role": "user"/"assistant", "content": "..."}]
ss.setdefault("got", set())            # main-idea pieces
ss.setdefault("fixed", set())          # summary mistakes fixed
ss.setdefault("idea", "")
ss.setdefault("unlocked", False)

TAG = re.compile(r"<<[^>]*>>")

def strip_tags(text):
    return TAG.sub("", text).strip()

def apply_tags(text):
    for m in re.finditer(r"<<got:(who|problem|plan|change)>>", text, re.I):
        ss.got.add(m.group(1).lower())
    for m in re.finditer(r"<<fixed:\s*([1-5])>>", text):
        ss.fixed.add(m.group(1))
    m = re.search(r"<<idea:([^>]{3,200})>>", text)
    if m:
        ss.idea = m.group(1).strip()

def progress_text():
    return (f"pieces: {', '.join(sorted(ss.got)) or 'none'}; "
            f"mistakes fixed: {', '.join(sorted(ss.fixed)) or 'none'}; "
            f"main idea: {ss.idea or 'not yet'}.")

# ------------------------------------------------------------
# 5. Optional class code (so strangers can't use your free quota)
# ------------------------------------------------------------
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

# ------------------------------------------------------------
# 6. Talking to Gemini
# ------------------------------------------------------------
@st.cache_resource
def get_client():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

def ask_pie_bot(group):
    history = [types.Content(role="model", parts=[types.Part(text=GREETING)])]
    for m in ss.messages[-24:]:
        role = "user" if m["role"] == "user" else "model"
        history.append(types.Content(role=role, parts=[types.Part(text=m["content"])]))
    # Gemini wants the conversation to start with a user turn
    history.insert(0, types.Content(role="user", parts=[types.Part(text="(The group opened the chat.)")]))
    response = get_client().models.generate_content(
        model=MODEL,
        contents=history,
        config=types.GenerateContentConfig(
            system_instruction=rules(group, progress_text()),
            temperature=0.6,
        ),
    )
    return response.text or ""

# ------------------------------------------------------------
# 7. Screen
# ------------------------------------------------------------
with st.sidebar:
    st.header("🥧 Our pie pieces")
    group = st.text_input("Group name", value="Group 1", max_chars=20)
    for key, label in [("who", "Who?"), ("problem", "Problem?"), ("plan", "Plan?"), ("change", "Change?")]:
        st.markdown(("🟥 " if key in ss.got else "⬜ ") + label)
    st.progress(len(ss.got) / 4)
    st.markdown(f"**Main idea:** {ss.idea or 'not yet'}")
    st.divider()
    st.header("🔍 Summary Detective")
    st.markdown(" ".join("🔴" if str(i) in ss.fixed else "⚪" for i in range(1, 6)))
    st.caption(f"Fixed {len(ss.fixed)} of 5 mistakes")
    st.divider()
    if st.button("New chat", use_container_width=True):
        ss.messages, ss.got, ss.fixed, ss.idea = [], set(), set(), ""
        st.rerun()

st.title("🥧 Pie Bot")
st.caption("Enemy Pie · your AI group member")

with st.expander("📖 Read the story"):
    for n, p in numbered_story():
        if n:
            st.markdown(f"**{n}.** {p}")
        else:
            st.markdown(f"*… {p}*")

# show the chat so far
with st.chat_message("assistant", avatar="🥧"):
    st.write(GREETING)
for m in ss.messages:
    with st.chat_message(m["role"], avatar="🥧" if m["role"] == "assistant" else "🙋"):
        st.write(strip_tags(m["content"]) if m["role"] == "assistant" else m["content"])

# quick buttons + typing box
c1, c2, c3 = st.columns(3)
quick = None
if c1.button("Start: main idea", use_container_width=True):
    quick = "Let's find the main idea!"
if c2.button("Hint, please", use_container_width=True):
    quick = "Can you give us a hint?"
if c3.button("Show your summary", use_container_width=True):
    quick = "Show your summary"

typed = st.chat_input("Type your group's answer...")
user_text = quick or typed

if user_text:
    ss.messages.append({"role": "user", "content": user_text})
    with st.chat_message("user", avatar="🙋"):
        st.write(user_text)
    with st.chat_message("assistant", avatar="🥧"):
        with st.spinner("Pie Bot is thinking..."):
            try:
                answer = ask_pie_bot(group or "the group")
            except Exception as e:
                ss.messages.pop()
                st.error("Pie Bot lost the connection. Try again in a minute.")
                st.caption(f"(for the teacher: {type(e).__name__})")
                st.stop()
        st.write(strip_tags(answer) or "Hmm, can you say that again?")
    ss.messages.append({"role": "assistant", "content": answer})
    apply_tags(answer)
    st.rerun()
