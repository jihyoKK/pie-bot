# shared.py - the PieGram board, shared by the Pie Bot page (app.py) and the PieGram page.
# It lives in the app's memory for the lesson, so it resets when the app restarts.

import re
import threading
import uuid
import streamlit as st

REACTIONS = {"wow": "😱 Surprised", "lol": "🤣 Funny", "clue": "🕵️ Found the clue"}
# Two AI-written twists hidden in the feed (handle, setup, twist, hashtags)
BOT_POSTS = [
    ("@sugar_rush_bakery",
     "Dad sent me to Jeremy's house to borrow some sugar. Jeremy's mom opened the door. Behind her, I saw a big photo on the wall.",
     "It was our baseball team, and Jeremy drew a circle around my face! Jeremy said, \"I wanted to be your friend, but I didn't know how.\" I was so surprised that I forgot about the sugar.",
     ["#SecretFan", "#ToMySurprise", "#Sugar"]),
    ("@midnight_crust",
     "Dad finished the pie and gave me a letter. \"Give this to Jeremy,\" he said. I opened it on the way.",
     "It was a dinner invitation, and my name was at the bottom! I was angry, but I knocked on Jeremy's door. Jeremy read the letter and smiled. \"I thought you hated me,\" he said. \"I'm sorry about the baseball game.\"",
     ["#Invitation", "#Sorry", "#PlotTwist"]),
]
TWIST_MARK = re.compile(r"\b(to my surprise|but actually)\b", re.I)


def new_post(handle, setup, twist, tags, is_bot=False):
    return {"id": uuid.uuid4().hex[:8], "handle": handle, "setup": setup, "twist": twist, "tags": tags,
            "bot": is_bot, "react": {k: set() for k in REACTIONS}, "bot_votes": set(), "comments": [],
            "guesses": [], "saw": {"yes": set(), "no": set()}, "label": ""}


@st.cache_resource
def board():
    b = {"lock": threading.Lock(), "posts": {}, "phase": "posting", "now": None, "card": 1}
    for h, s_, t_, tags in BOT_POSTS:
        p = new_post(h, s_, t_, tags, True)
        b["posts"][p["id"]] = p
    return b


def clean_handle(h):
    h = re.sub(r"[^A-Za-z0-9_@]", "_", h.strip())
    return h if h.startswith("@") else "@" + h


def clean_tags(text):
    return [t if t.startswith("#") else "#" + t for t in text.replace(",", " ").split() if t.strip("#")][:3]


def split_twist(paragraph):
    """Split the group's paragraph at 'To my surprise' / 'But actually'. Returns (setup, twist) or None."""
    m = TWIST_MARK.search(paragraph)
    if not m or not paragraph[:m.start()].strip():
        return None
    return paragraph[:m.start()].strip(), paragraph[m.start():].strip()


def upsert_post(handle, setup, twist, tags, old_handle=""):
    """Add or update a group's post. Returns (ok, message)."""
    b = board()
    with b["lock"]:
        if b["phase"] != "posting":
            return False, "The feed is already open. Ask your teacher."
        mine = next((p for p in b["posts"].values() if not p["bot"] and old_handle and p["handle"] == old_handle), None)
        if any(p["handle"].lower() == handle.lower() and p is not mine for p in b["posts"].values()):
            return False, "That account name is taken. Choose another."
        if mine:
            mine.update({"handle": handle, "setup": setup, "twist": twist, "tags": tags})
        else:
            p = new_post(handle, setup, twist, tags)
            b["posts"][p["id"]] = p
    return True, "Posted to PieGram!"
