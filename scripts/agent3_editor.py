"""
agent3_editor.py — Editor Agent
Uses FFmpeg to stitch clips, add music, captions, intro/outro, and export final video.
"""

import os
import subprocess
import json
from pathlib import Path

OUTPUT_DIR = Path("output")
ASSETS_DIR = Path("assets")
OUTPUT_DIR.mkdir(exist_ok=True)

def run(clips: list, script: dict, topic: str) -> str:
    """
    Stitch clips, add music and captions, export final vertical + horizontal videos.
    Returns filename of final vertical video.
    """
    verses = script.get("verses", [])
    hook = script.get("hook", "")
    chorus = script.get("chorus", [])

    # Build caption lines list (hook + all verse lines + chorus)
    caption_lines = [hook]
    for verse in verses:
        caption_lines.extend(verse)
    caption_lines.extend(chorus)

    vertical_out = OUTPUT_DIR / "final_output_vertical.mp4"
    horizontal_out = OUTPUT_DIR / "final_output_horizontal.mp4"

    # Step 1: Stitch clips
    stitched = _stitch_clips(clips)

    # Step 2: Add background music
    with_music = _add_music(stitched)

    # Step 3: Add captions
    with_captions = _add_captions(with_music, caption_lines, topic)

    # Step 4: Add intro/outro
    final_vertical = _add_intro_outro(with_captions, topic, str(vertical_out))

    # Step 5: Export horizontal version for YouTube
    _export_horizontal(final_vertical, str(horizontal_out))

    print(f"[Editor] Done. Vertical: {vertical_out} | Horizontal: {horizontal_out}")
    return "final_output_vertical.mp4"


def _stitch_clips(clips: list) -> str:
    """Concatenate all clips using FFmpeg concat."""
    concat_list = OUTPUT_DIR / "concat_list.txt"
    lines = [f"file '{Path(c).resolve()}'" for c in clips if Path(c).exists()]

    if not lines:
        # Create a test placeholder if clips don't exist (test mode)
        _create_placeholder(str(OUTPUT_DIR / "clip1.mp4"), color="blue", duration=8)
        _create_placeholder(str(OUTPUT_DIR / "clip2.mp4"), color="green", duration=8)
        lines = [
            f"file '{(OUTPUT_DIR / 'clip1.mp4').resolve()}'",
            f"file '{(OUTPUT_DIR / 'clip2.mp4').resolve()}'",
        ]

    concat_list.write_text("\n".join(lines))
    out = str(OUTPUT_DIR / "stitched.mp4")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        out
    ], check=True, capture_output=True)
    print(f"[Editor] Stitched clips → {out}")
    return out


def _add_music(video_path: str) -> str:
    """Mix background music at low volume under the video."""
    out = str(OUTPUT_DIR / "with_music.mp4")
    music_dir = ASSETS_DIR / "music"
    music_files = list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav")) if music_dir.exists() else []

    if not music_files:
        print("[Editor] No music found in assets/music — skipping music step")
        return video_path

    music = str(music_files[0])
    subprocess.run([
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", music,
        "-filter_complex",
        "[1:a]volume=0.15,aloop=loop=-1:size=2e+09[bg];"
        "[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", out
    ], check=True, capture_output=True)
    print(f"[Editor] Added music → {out}")
    return out


def _add_captions(video_path: str, lines: list, topic: str) -> str:
    """Burn animated captions using FFmpeg drawtext filter."""
    out = str(OUTPUT_DIR / "with_captions.mp4")

    # Build drawtext filter — show each line for ~2.5 seconds
    duration_per_line = 2.5
    filters = []

    for i, line in enumerate(lines[:8]):  # Max 8 caption lines
        t_start = i * duration_per_line
        t_end = t_start + duration_per_line
        safe_line = line.replace("'", "\\'").replace(":", "\\:")
        filters.append(
            f"drawtext=text='{safe_line}':"
            f"fontsize=52:fontcolor=white:bordercolor=black:borderw=3:"
            f"x=(w-text_w)/2:y=h*0.75:"
            f"enable='between(t,{t_start},{t_end})'"
        )

    # Add topic label at top
    topic_safe = topic.replace("'", "\\'")
    filters.append(
        f"drawtext=text='📚 {topic_safe}':"
        f"fontsize=36:fontcolor=yellow:bordercolor=black:borderw=2:"
        f"x=(w-text_w)/2:y=60:enable='1'"
    )

    vf = ",".join(filters)
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "copy", out
    ], check=True, capture_output=True)
    print(f"[Editor] Added captions → {out}")
    return out


def _add_intro_outro(video_path: str, topic: str, out_path: str) -> str:
    """Add 1-second color intro card and 2-second outro with CTA."""
    intro = str(OUTPUT_DIR / "intro.mp4")
    outro = str(OUTPUT_DIR / "outro.mp4")
    concat_list = OUTPUT_DIR / "final_concat.txt"

    # Create intro: bright yellow card with topic
    _create_title_card(intro, topic, color="0x4A90D9", duration=1.5)

    # Create outro: subscribe CTA
    _create_title_card(outro, "Like & Follow for more! 🌟", color="0xFF6B35", duration=2.0)

    concat_list.write_text(
        f"file '{Path(intro).resolve()}'\n"
        f"file '{Path(video_path).resolve()}'\n"
        f"file '{Path(outro).resolve()}'\n"
    )

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        out_path
    ], check=True, capture_output=True)
    print(f"[Editor] Added intro/outro → {out_path}")
    return out_path


def _export_horizontal(vertical_path: str, out_path: str):
    """Export 16:9 horizontal version for YouTube."""
    subprocess.run([
        "ffmpeg", "-y", "-i", vertical_path,
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,"
               "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "copy", out_path
    ], check=True, capture_output=True)
    print(f"[Editor] Exported horizontal → {out_path}")


def _create_placeholder(path: str, color: str = "blue", duration: int = 8):
    """Create a placeholder colored video for testing."""
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c={color}:size=1080x1920:duration={duration}:rate=30",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-c:v", "libx264", "-c:a", "aac",
        "-pix_fmt", "yuv420p", path
    ], check=True, capture_output=True)


def _create_title_card(path: str, text: str, color: str = "0x4A90D9", duration: float = 1.5):
    """Create a title card with text overlay."""
    safe_text = text.replace("'", "\\'").replace(":", "\\:").replace("&", "and")
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c={color}:size=1080x1920:duration={duration}:rate=30",
        "-f", "lavfi", "-i", f"sine=frequency=528:duration={duration}",
        "-vf", f"drawtext=text='{safe_text}':fontsize=60:fontcolor=white:"
               f"bordercolor=black:borderw=3:x=(w-text_w)/2:y=(h-text_h)/2",
        "-c:v", "libx264", "-c:a", "aac",
        "-pix_fmt", "yuv420p", path
    ], check=True, capture_output=True)
