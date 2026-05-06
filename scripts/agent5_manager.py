"""
agent5_manager.py — Manager Agent
Orchestrates all agents, enforces quality, shares info between agents,
self-updates memory after each run to improve future content.
"""

import json
import os
import datetime
from pathlib import Path

STATE_FILE = "pipeline_state.json"


# ── Shared Memory API (used by ALL agents) ─────────────────────────────────────

def read_shared(key: str = None):
    """Any agent calls this to read shared pipeline state."""
    state = _load()
    if key:
        return state.get(key)
    return state


def write_shared(key: str, value):
    """Any agent calls this to write to shared state."""
    state = _load()
    state[key] = value
    _save(state)
    return True


def agent_log(agent_name: str, status: str, detail: str = ""):
    """Agents call this to update their status in shared memory."""
    state = _load()
    state.setdefault("agent_logs", {})[agent_name] = status
    state.setdefault("agent_timeline", []).append({
        "agent": agent_name,
        "status": status,
        "detail": detail,
        "time": datetime.datetime.now().isoformat()
    })
    _save(state)


# ── Quality Control ────────────────────────────────────────────────────────────

def quality_check_script(script: dict) -> tuple[bool, list[str]]:
    """Manager reviews script quality before animation."""
    issues = []

    hook = script.get("hook", "")
    if len(hook) < 10:
        issues.append("Hook too short")
    if len(hook.split()) > 15:
        issues.append("Hook too long (max 12 words)")

    verses = script.get("verses", [])
    if len(verses) < 3:
        issues.append("Need at least 3 verses")

    for i, verse in enumerate(verses):
        for line in verse:
            if len(line.split()) > 8:
                issues.append(f"Verse {i+1} has line too long: '{line}'")

    if not script.get("educational_fact"):
        issues.append("Missing educational fact")

    if not script.get("style_prompt"):
        issues.append("Missing style prompt for Animator")

    return len(issues) == 0, issues


def quality_check_video(video_path: str) -> tuple[bool, list[str]]:
    """Manager checks final video quality."""
    import subprocess, json as _json
    issues = []

    if not Path(video_path).exists():
        return False, ["Video file does not exist"]

    try:
        result = subprocess.run([
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-show_format", video_path
        ], capture_output=True, text=True, timeout=30)

        info = _json.loads(result.stdout)
        video_stream = next(
            (s for s in info.get("streams", []) if s.get("codec_type") == "video"), None
        )

        if video_stream:
            width = int(video_stream.get("width", 0))
            height = int(video_stream.get("height", 0))
            if width < 720:
                issues.append(f"Video width too low: {width}px (min 720)")
            if height < 1280:
                issues.append(f"Video height too low: {height}px (min 1280)")

        duration = float(info.get("format", {}).get("duration", 0))
        if duration < 10:
            issues.append(f"Video too short: {duration:.1f}s (min 10s)")
        if duration > 60:
            issues.append(f"Video too long: {duration:.1f}s (max 60s)")

        size_mb = Path(video_path).stat().st_size / (1024 * 1024)
        if size_mb > 100:
            issues.append(f"File too large: {size_mb:.1f}MB (max 100MB)")

    except Exception as e:
        issues.append(f"Could not probe video: {e}")

    return len(issues) == 0, issues


# ── Self-Update Memory ─────────────────────────────────────────────────────────

def self_update(state: dict, post_results: dict):
    """
    After each run, Manager updates shared memory with lessons learned.
    Future agents will use this to improve content quality automatically.
    """
    memory = state.get("memory", {})
    topic = state.get("topic", "")
    script = state.get("script", {})
    quality_score = state.get("quality_score", 0)
    date = state.get("date", datetime.date.today().isoformat())

    # Track used topics
    topics_used = memory.get("topics_used", [])
    if topic and topic not in topics_used:
        topics_used.append(topic)
    memory["topics_used"] = topics_used

    # Determine if hook was effective (simple heuristic: quality score >= 8)
    hook = script.get("hook", "")
    if hook and quality_score >= 8:
        best_hooks = memory.get("best_performing_hooks", [])
        # Extract hook pattern (first 3 words)
        pattern = " ".join(hook.split()[:3])
        if pattern not in best_hooks:
            best_hooks.append(pattern)
        memory["best_performing_hooks"] = best_hooks[-10:]  # Keep last 10

    # Log lesson from this run
    lesson = {
        "date": date,
        "topic": topic,
        "quality_score": quality_score,
        "hook": hook,
        "post_success": {k: "FAILED" not in v for k, v in post_results.items()},
        "notes": _generate_improvement_notes(state, post_results)
    }
    lessons = memory.get("lessons_learned", [])
    lessons.append(lesson)
    memory["lessons_learned"] = lessons[-30:]  # Keep last 30 days

    # Update run stats
    memory["total_runs"] = memory.get("total_runs", 0) + 1
    memory["last_run"] = date

    state["memory"] = memory
    _save(state)

    return memory


def _generate_improvement_notes(state: dict, post_results: dict) -> str:
    """Auto-generate notes for future improvement."""
    notes = []
    quality_score = state.get("quality_score", 0)

    if quality_score < 7:
        notes.append("Low quality score — review script complexity next time")
    if quality_score >= 9:
        notes.append("High quality run — replicate this style")

    failed_platforms = [k for k, v in post_results.items() if "FAILED" in str(v)]
    if failed_platforms:
        notes.append(f"Posting failed on: {', '.join(failed_platforms)} — check API tokens")

    return "; ".join(notes) if notes else "Smooth run"


# ── Agent Info Sharing ─────────────────────────────────────────────────────────

def get_context_for_agent(agent_name: str) -> dict:
    """
    Any agent can call this to get relevant context from other agents' work.
    This is how agents share information with each other.
    """
    state = _load()

    shared_context = {
        "date": state.get("date"),
        "topic": state.get("topic"),
        "memory": state.get("memory", {}),
        "agent_logs": state.get("agent_logs", {}),
    }

    # Give each agent what it specifically needs from others
    if agent_name == "animator":
        shared_context["script"] = state.get("script", {})

    elif agent_name == "editor":
        shared_context["script"] = state.get("script", {})
        shared_context["video_clips"] = state.get("video_clips", [])

    elif agent_name == "poster":
        shared_context["script"] = state.get("script", {})
        shared_context["final_video"] = state.get("final_video")

    elif agent_name == "manager":
        shared_context.update(state)  # Manager sees everything

    return shared_context


# ── Weekly Review ──────────────────────────────────────────────────────────────

def weekly_review() -> dict:
    """
    Called once a week. Analyzes last 7 lessons and generates recommendations
    that are stored back in memory for agents to use next week.
    """
    state = _load()
    memory = state.get("memory", {})
    lessons = memory.get("lessons_learned", [])[-7:]

    if not lessons:
        return {"status": "no_data"}

    avg_quality = sum(l.get("quality_score", 0) for l in lessons) / len(lessons)
    all_notes = [l.get("notes", "") for l in lessons if l.get("notes")]

    review = {
        "week_ending": datetime.date.today().isoformat(),
        "runs": len(lessons),
        "avg_quality_score": round(avg_quality, 1),
        "topics_covered": [l.get("topic") for l in lessons],
        "recommendations": _build_recommendations(lessons, avg_quality),
        "raw_notes": all_notes
    }

    memory["weekly_review"] = review
    state["memory"] = memory
    _save(state)

    return review


def _build_recommendations(lessons: list, avg_quality: float) -> list:
    recs = []
    if avg_quality < 7:
        recs.append("Simplify verse language — aim for 4-word lines")
    if avg_quality >= 8.5:
        recs.append("Content quality is excellent — maintain current style")

    failed_counts = {}
    for lesson in lessons:
        for platform, success in lesson.get("post_success", {}).items():
            if not success:
                failed_counts[platform] = failed_counts.get(platform, 0) + 1

    for platform, count in failed_counts.items():
        if count >= 3:
            recs.append(f"Refresh {platform} API token — failed {count} times this week")

    return recs if recs else ["All systems running well"]


# ── Internal helpers ───────────────────────────────────────────────────────────

def _load() -> dict:
    if Path(STATE_FILE).exists():
        try:
            return json.loads(Path(STATE_FILE).read_text())
        except Exception:
            pass
    return {"memory": {"topics_used": [], "best_performing_hooks": [], "lessons_learned": []}}


def _save(state: dict):
    Path(STATE_FILE).write_text(json.dumps(state, indent=2))
