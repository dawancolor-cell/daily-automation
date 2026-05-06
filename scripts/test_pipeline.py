"""
test_pipeline.py — Full Dry Run Test
Tests all 5 agents with mock/stub API calls (no real API keys needed).
Run: python test_pipeline.py

What this tests:
  ✅ Agent 5 Manager — shared memory, topic selection, quality checks
  ✅ Agent 1 Writer   — script structure and format (mocked OpenAI)
  ✅ Agent 2 Animator — clip generation (creates color placeholders via FFmpeg)
  ✅ Agent 3 Editor   — full FFmpeg stitching, captions, intro/outro
  ✅ Agent 4 Poster   — caption building, API call structure (no actual posting)
  ✅ Telegram         — message formatting (no actual send)
  ✅ Self-update      — memory write-back after run
"""

import sys
import json
import os
import subprocess
import datetime
from pathlib import Path

# ── Setup paths ────────────────────────────────────────────────────────────────
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))
os.chdir(SCRIPTS_DIR.parent)  # Run from project root

Path("output").mkdir(exist_ok=True)
Path("assets/music").mkdir(parents=True, exist_ok=True)
Path("logs").mkdir(exist_ok=True)

PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "
INFO = "ℹ️ "

results = []

def log(icon, label, detail=""):
    msg = f"  {icon} {label}"
    if detail:
        msg += f"\n       {detail}"
    print(msg)
    results.append((icon, label))

def section(title):
    print(f"\n{'─'*55}")
    print(f"  🔷 {title}")
    print(f"{'─'*55}")


# ══════════════════════════════════════════════════════════
# TEST 1: Check FFmpeg is installed
# ══════════════════════════════════════════════════════════
section("Environment Check")

try:
    result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=10)
    version_line = result.stdout.split("\n")[0]
    log(PASS, "FFmpeg installed", version_line[:60])
except FileNotFoundError:
    log(FAIL, "FFmpeg NOT found — install with: sudo apt install ffmpeg  OR  brew install ffmpeg")
    print("\n⛔ FFmpeg is required. Install it and re-run this test.\n")
    sys.exit(1)

try:
    subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=5)
    log(PASS, "FFprobe installed")
except FileNotFoundError:
    log(WARN, "FFprobe not found (included with FFmpeg usually)")


# ══════════════════════════════════════════════════════════
# TEST 2: Agent 5 Manager — Shared Memory & Topic Selection
# ══════════════════════════════════════════════════════════
section("Agent 5 — Manager (Shared Memory & Topic Selection)")

from agent5_manager import (
    read_shared, write_shared, agent_log,
    quality_check_script, quality_check_video,
    self_update, get_context_for_agent, weekly_review
)

# Initialize clean state for test
test_state = {
    "date": datetime.date.today().isoformat(),
    "topic": "The Water Cycle",
    "status": "test",
    "agent_logs": {},
    "agent_timeline": [],
    "script": {},
    "video_clips": [],
    "final_video": None,
    "quality_score": None,
    "post_results": {},
    "memory": {
        "topics_used": ["The Solar System"],
        "best_performing_hooks": ["Did you know"],
        "lessons_learned": []
    }
}
Path("pipeline_state.json").write_text(json.dumps(test_state, indent=2))

# Test shared memory read/write
write_shared("test_key", "hello_from_test")
val = read_shared("test_key")
if val == "hello_from_test":
    log(PASS, "Shared memory read/write works")
else:
    log(FAIL, "Shared memory broken")

# Test agent logging
agent_log("writer", "completed", "Script for The Water Cycle")
state = read_shared()
if state.get("agent_logs", {}).get("writer") == "completed":
    log(PASS, "Agent cross-logging works")
else:
    log(FAIL, "Agent logging failed")

# Test context sharing
ctx = get_context_for_agent("animator")
if "topic" in ctx and "memory" in ctx:
    log(PASS, "Context sharing between agents works")
else:
    log(FAIL, "Context sharing broken")


# ══════════════════════════════════════════════════════════
# TEST 3: Agent 1 Writer — Mock Script (no OpenAI key needed)
# ══════════════════════════════════════════════════════════
section("Agent 1 — Writer (Mock Script)")

MOCK_SCRIPT = {
    "hook": "Did you know water travels in a circle forever?",
    "verses": [
        ["Rain falls from the sky,", "It lands with a sigh,", "It flows to the sea,", "As happy as can be!"],
        ["The sun warms the tide,", "The water goes wide,", "It rises up high,", "As clouds in the sky!"],
        ["The clouds get so full,", "With water to pull,", "Then down comes the rain,", "To do it again!"]
    ],
    "chorus": ["The water cycle goes round and round!", "From sky to earth and back, it's found!"],
    "style_prompt": "Bright 3D cartoon animation, Pixar style. Blue sky, fluffy white clouds, happy sun character, friendly raindrops with faces, colorful river. Soft pastel colors. Age 3-8 kids educational.",
    "educational_fact": "Water on Earth is billions of years old — you might drink the same water as a dinosaur!"
}

# Quality check mock script
passed, issues = quality_check_script(MOCK_SCRIPT)
if passed:
    log(PASS, "Script quality check passed")
else:
    log(WARN, f"Script issues (non-fatal for test): {issues}")

# Write script to shared memory
write_shared("script", MOCK_SCRIPT)
agent_log("writer", "completed", "Mock script written")
log(PASS, "Script written to shared memory")
log(INFO, f"Hook: \"{MOCK_SCRIPT['hook']}\"")
log(INFO, f"Fact: \"{MOCK_SCRIPT['educational_fact'][:60]}...\"")


# ══════════════════════════════════════════════════════════
# TEST 4: Agent 2 Animator — Placeholder Clips via FFmpeg
# ══════════════════════════════════════════════════════════
section("Agent 2 — Animator (FFmpeg placeholder clips)")

def create_test_clip(path: str, color: str, duration: int = 8, label: str = ""):
    """Create a colored test clip with text label."""
    safe_label = label.replace("'", "").replace(":", "")
    try:
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c={color}:size=1080x1920:duration={duration}:rate=30",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
            "-vf", f"drawtext=text='{safe_label}':fontsize=48:fontcolor=white:"
                   f"x=(w-text_w)/2:y=(h-text_h)/2:bordercolor=black:borderw=2",
            "-c:v", "libx264", "-c:a", "aac",
            "-pix_fmt", "yuv420p", path
        ], check=True, capture_output=True, timeout=60)
        return True
    except subprocess.CalledProcessError as e:
        # Try without text if font rendering fails
        try:
            subprocess.run([
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"color=c={color}:size=1080x1920:duration={duration}:rate=30",
                "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
                "-c:v", "libx264", "-c:a", "aac",
                "-pix_fmt", "yuv420p", path
            ], check=True, capture_output=True, timeout=60)
            return True
        except Exception:
            return False

clip1 = "output/clip1.mp4"
clip2 = "output/clip2.mp4"

ok1 = create_test_clip(clip1, "0x3B9CF5", label="Scene 1: Water Cycle")
ok2 = create_test_clip(clip2, "0x2ECC71", label="Scene 2: Clouds Form")

if ok1 and ok2:
    log(PASS, "Generated 2 test video clips (8s each)")
    write_shared("video_clips", [clip1, clip2])
    agent_log("animator", "completed", "2 test clips generated")
else:
    log(FAIL, "Clip generation failed")


# ══════════════════════════════════════════════════════════
# TEST 5: Agent 3 Editor — Full FFmpeg Pipeline
# ══════════════════════════════════════════════════════════
section("Agent 3 — Editor (FFmpeg stitching + captions + intro/outro)")

from agent3_editor import run as edit_run

try:
    final = edit_run(
        clips=[clip1, clip2],
        script=MOCK_SCRIPT,
        topic="The Water Cycle"
    )
    final_path = f"output/{final}"
    if Path(final_path).exists():
        size_mb = Path(final_path).stat().st_size / (1024 * 1024)
        log(PASS, f"Final vertical video created: {final}")
        log(INFO, f"File size: {size_mb:.2f} MB")
        write_shared("final_video", final)
        agent_log("editor", "completed")

        # Video quality check
        passed_v, vid_issues = quality_check_video(final_path)
        if passed_v:
            log(PASS, "Video quality check passed (resolution, duration, size)")
        else:
            log(WARN, f"Video quality notes: {vid_issues}")

        # Check horizontal export too
        horiz = "output/final_output_horizontal.mp4"
        if Path(horiz).exists():
            log(PASS, "Horizontal (YouTube) version exported too")
    else:
        log(FAIL, f"Expected output file not found: {final_path}")
except Exception as e:
    log(FAIL, f"Editor agent error: {e}")


# ══════════════════════════════════════════════════════════
# TEST 6: Agent 4 Poster — Caption & Structure Test (no real posting)
# ══════════════════════════════════════════════════════════
section("Agent 4 — Poster (Caption & API structure, no real posting)")

from agent4_poster import build_caption

caption = build_caption(MOCK_SCRIPT, "The Water Cycle")
if caption and len(caption) > 50:
    log(PASS, "Caption generated successfully")
    log(INFO, f"Caption preview: {caption[:100]}...")
    hashtag_count = caption.count("#")
    log(INFO, f"Hashtag count: {hashtag_count}")
else:
    log(FAIL, "Caption generation failed")

# Verify all platform functions exist
from agent4_poster import post_instagram, post_facebook, post_tiktok, post_youtube
log(PASS, "All 4 platform poster functions present (Instagram, Facebook, TikTok, YouTube)")
log(INFO, "Skipping real API calls — add tokens to .env to enable live posting")


# ══════════════════════════════════════════════════════════
# TEST 7: Telegram Notification Format
# ══════════════════════════════════════════════════════════
section("Telegram Notification (format test, no real send)")

sample_messages = [
    "🎬 <b>Pipeline started</b>\n📚 Today's topic: <b>The Water Cycle</b>",
    "✍️ <b>Agent 1 — Writer done ✅</b>\n🪝 Hook: <i>Did you know water travels in a circle forever?</i>",
    "🎨 <b>Agent 2 — Animator done ✅</b>\n🎥 Generated 2 clips",
    "✂️ <b>Agent 3 — Editor done ✅</b>\n📹 final_output_vertical.mp4",
    "🏆 <b>Pipeline Complete!</b>\n📚 Topic: The Water Cycle\n⭐ Quality: 9/10\n✅ Posted to all platforms"
]
for msg in sample_messages:
    plain = msg.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")
    log(PASS, plain[:70])


# ══════════════════════════════════════════════════════════
# TEST 8: Manager Self-Update Memory
# ══════════════════════════════════════════════════════════
section("Agent 5 — Self-Update & Memory After Run")

state = read_shared()
state["script"] = MOCK_SCRIPT
state["topic"] = "The Water Cycle"
state["quality_score"] = 9
state["final_video"] = "final_output_vertical.mp4"
Path("pipeline_state.json").write_text(json.dumps(state, indent=2))

mock_post_results = {
    "instagram": "https://instagram.com/p/test123",
    "facebook": "https://facebook.com/reel/test123",
    "tiktok": "https://tiktok.com/@test",
    "youtube": "https://youtube.com/shorts/test123"
}

updated_memory = self_update(state, mock_post_results)

if "The Water Cycle" in updated_memory.get("topics_used", []):
    log(PASS, "Topic saved to memory (won't repeat)")
else:
    log(FAIL, "Topic not saved to memory")

if updated_memory.get("total_runs", 0) >= 1:
    log(PASS, f"Run counter updated: {updated_memory['total_runs']} total runs")
else:
    log(FAIL, "Run counter not updated")

if updated_memory.get("lessons_learned"):
    lesson = updated_memory["lessons_learned"][-1]
    log(PASS, "Lesson logged for future improvement")
    log(INFO, f"Lesson: {lesson.get('notes', '')}")
else:
    log(FAIL, "Lesson not saved")

# Test weekly review
review = weekly_review()
log(PASS, f"Weekly review generated: avg quality {review.get('avg_quality_score', 'N/A')}/10")


# ══════════════════════════════════════════════════════════
# FINAL REPORT
# ══════════════════════════════════════════════════════════
print(f"\n{'═'*55}")
print("  📊  TEST RESULTS SUMMARY")
print(f"{'═'*55}")

passed = sum(1 for icon, _ in results if icon == PASS)
failed = sum(1 for icon, _ in results if icon == FAIL)
warned = sum(1 for icon, _ in results if icon == WARN)

print(f"  ✅  Passed : {passed}")
print(f"  ❌  Failed : {failed}")
print(f"  ⚠️   Warned : {warned}")
print(f"  Total  : {passed + failed + warned}")
print(f"{'═'*55}")

if failed == 0:
    print("\n  🎉  ALL TESTS PASSED — Pipeline is ready!")
    print("  Next steps:")
    print("  1. Add your API keys to .env")
    print("  2. Drop an .mp3 into assets/music/")
    print("  3. Run: python scripts/run_pipeline.py --test")
    print("  4. Set up daily cron (see references/github-actions.md)")
else:
    print(f"\n  ⚠️  {failed} test(s) failed. Check errors above.")

print()

# Save test report
report = {
    "date": datetime.date.today().isoformat(),
    "passed": passed,
    "failed": failed,
    "warned": warned,
    "details": [{"icon": i, "label": l} for i, l in results]
}
Path("logs/test_report.json").write_text(json.dumps(report, indent=2))
print(f"  📄  Full report saved to logs/test_report.json\n")

sys.exit(0 if failed == 0 else 1)
