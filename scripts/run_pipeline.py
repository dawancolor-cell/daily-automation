"""
run_pipeline.py — Master Orchestrator (Agent 5 / Manager)
Runs all agents in sequence, manages shared memory, sends Telegram notifications.
"""

import json
import os
import sys
import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

STATE_FILE = "pipeline_state.json"

# ── Telegram ──────────────────────────────────────────────────────────────────
import requests

def telegram(msg: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(f"[TELEGRAM SKIPPED] {msg}")
        return
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}
    )

# ── Shared Memory ─────────────────────────────────────────────────────────────
def load_state() -> dict:
    if Path(STATE_FILE).exists():
        return json.loads(Path(STATE_FILE).read_text())
    return {
        "memory": {
            "topics_used": [],
            "best_performing_hooks": [],
            "lessons_learned": []
        }
    }

def save_state(state: dict):
    Path(STATE_FILE).write_text(json.dumps(state, indent=2))

def pick_topic(memory: dict) -> str:
    """Manager picks a fresh topic not used before."""
    topic_pool = [
        "The Water Cycle", "How Plants Grow", "The Solar System",
        "Why is the Sky Blue?", "How Do Birds Fly?", "The Human Heart",
        "Volcanoes", "Butterflies & Metamorphosis", "Ocean Animals",
        "How Rainbows Form", "Dinosaurs", "The Moon", "Bees & Pollination",
        "How Bread is Made", "What are Stars?", "Seasons", "Gravity",
        "How Eyes Work", "The Amazon Rainforest", "Mountains",
    ]
    used = set(memory.get("topics_used", []))
    available = [t for t in topic_pool if t not in used]
    if not available:
        # All topics used — reset cycle
        available = topic_pool
    return available[0]

# ── Quality Gate ──────────────────────────────────────────────────────────────
def quality_check(state: dict) -> tuple[bool, int, list]:
    issues = []
    score = 10

    script = state.get("script", {})
    if not script.get("hook"):
        issues.append("Missing hook"); score -= 3
    if len(script.get("verses", [])) < 3:
        issues.append("Less than 3 verses"); score -= 2

    final_video = state.get("final_video")
    if not final_video or not Path(f"output/{final_video}").exists():
        issues.append("Final video file missing"); score -= 5

    return score >= 7, score, issues

# ── Main Pipeline ─────────────────────────────────────────────────────────────
def run(test_mode=False):
    state = load_state()
    today = datetime.date.today().isoformat()
    topic = pick_topic(state.get("memory", {}))

    state.update({
        "date": today,
        "topic": topic,
        "status": "starting",
        "agent_logs": {
            "writer": "pending",
            "animator": "pending",
            "editor": "pending",
            "poster": "pending",
            "manager": "monitoring"
        },
        "script": {},
        "video_clips": [],
        "final_video": None,
        "quality_score": None,
        "post_results": {}
    })
    save_state(state)

    telegram(f"🎬 <b>Pipeline started</b>\n📚 Today's topic: <b>{topic}</b>\n📅 {today}")

    # ── Agent 1: Writer ────────────────────────────────────────────────────────
    try:
        from agent1_writer import run as write
        script = write(topic, state["memory"])
        state["script"] = script
        state["agent_logs"]["writer"] = "completed"
        save_state(state)
        telegram(f"✍️ <b>Agent 1 — Writer done ✅</b>\n🪝 Hook: <i>{script['hook'][:80]}...</i>")
    except Exception as e:
        state["agent_logs"]["writer"] = f"failed: {e}"
        save_state(state)
        telegram(f"❌ Agent 1 Writer FAILED: {e}")
        return

    # ── Agent 2: Animator ─────────────────────────────────────────────────────
    try:
        from agent2_animator import run as animate
        clips = animate(state["script"])
        state["video_clips"] = clips
        state["agent_logs"]["animator"] = "completed"
        save_state(state)
        telegram(f"🎨 <b>Agent 2 — Animator done ✅</b>\n🎥 Generated {len(clips)} clips")
    except Exception as e:
        state["agent_logs"]["animator"] = f"failed: {e}"
        save_state(state)
        telegram(f"❌ Agent 2 Animator FAILED: {e}")
        return

    # ── Agent 3: Editor ───────────────────────────────────────────────────────
    try:
        from agent3_editor import run as edit
        final = edit(state["video_clips"], state["script"], state["topic"])
        state["final_video"] = final
        state["agent_logs"]["editor"] = "completed"
        save_state(state)
        telegram(f"✂️ <b>Agent 3 — Editor done ✅</b>\n📹 {final}")
    except Exception as e:
        state["agent_logs"]["editor"] = f"failed: {e}"
        save_state(state)
        telegram(f"❌ Agent 3 Editor FAILED: {e}")
        return

    # ── Quality Gate ──────────────────────────────────────────────────────────
    passed, score, issues = quality_check(state)
    state["quality_score"] = score
    if not passed:
        save_state(state)
        telegram(f"⚠️ <b>Quality check FAILED (score {score}/10)</b>\nIssues: {', '.join(issues)}")
        return

    # ── Agent 4: Poster ───────────────────────────────────────────────────────
    if not test_mode:
        try:
            from agent4_poster import run as post
            results = post(state["final_video"], state["script"], state["topic"])
            state["post_results"] = results
            state["agent_logs"]["poster"] = "completed"
            save_state(state)
            links = "\n".join([f"  {k}: {v}" for k, v in results.items()])
            telegram(f"📱 <b>Agent 4 — Posted ✅</b>\n{links}")
        except Exception as e:
            state["agent_logs"]["poster"] = f"failed: {e}"
            save_state(state)
            telegram(f"❌ Agent 4 Poster FAILED: {e}")
            return
    else:
        telegram("🧪 TEST MODE — skipping actual posting")

    # ── Manager: Self-Update Memory ───────────────────────────────────────────
    memory = state.get("memory", {})
    memory.setdefault("topics_used", []).append(topic)
    memory.setdefault("lessons_learned", []).append({
        "date": today,
        "topic": topic,
        "quality_score": score,
        "hook": state["script"].get("hook", "")
    })
    state["memory"] = memory
    state["status"] = "completed"
    save_state(state)

    telegram(
        f"🏆 <b>Pipeline Complete!</b>\n"
        f"📚 Topic: {topic}\n"
        f"⭐ Quality score: {score}/10\n"
        f"📅 {today}\n"
        f"✅ Posted to: Instagram, TikTok, YouTube, Facebook"
    )
    print(f"[DONE] Pipeline completed for topic: {topic} | Score: {score}/10")


if __name__ == "__main__":
    test = "--test" in sys.argv
    run(test_mode=test)
