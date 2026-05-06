"""
agent2_animator.py — Animator Agent
Uses Google Gemini Veo API to generate 2x 8-second animated video clips.
Falls back to Stability AI image frames + FFmpeg animation if Veo is unavailable.
"""

import os
import time
import requests
from pathlib import Path
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

def run(script: dict) -> list[str]:
    """Generate 2 video clips from style_prompt. Returns list of file paths."""

    style_prompt = script.get("style_prompt", "")
    educational_fact = script.get("educational_fact", "")

    # Two scene prompts based on the script
    scene_prompts = [
        f"Scene 1: {style_prompt}. Opening scene, bright and cheerful, establishing the world. {educational_fact}. 8 seconds, kids animation.",
        f"Scene 2: {style_prompt}. Action scene showing the main concept clearly. Colorful, engaging, educational. 8 seconds, kids animation."
    ]

    clips = []
    for i, prompt in enumerate(scene_prompts):
        clip_path = OUTPUT_DIR / f"clip{i+1}.mp4"
        try:
            clip_path = _generate_veo(prompt, clip_path)
        except Exception as e:
            print(f"[WARN] Veo failed for clip {i+1}: {e}. Trying fallback...")
            clip_path = _fallback_stability(prompt, i+1)
        clips.append(str(clip_path))
        time.sleep(2)  # Rate limit courtesy pause

    return clips


def _generate_veo(prompt: str, output_path: Path) -> Path:
    """Use Gemini Veo 2 to generate a video clip."""
    # Veo 2 via Gemini API (Preview — requires allowlist access)
    model = genai.GenerativeModel("veo-2.0-generate-001")

    operation = model.generate_video(
        prompt=prompt,
        config={
            "duration_seconds": 8,
            "aspect_ratio": "9:16",   # Vertical for Reels
            "resolution": "1080p"
        }
    )

    # Poll until complete
    while not operation.done:
        time.sleep(5)
        operation.refresh()

    video_data = operation.result.video.video_bytes
    output_path.write_bytes(video_data)
    print(f"[Veo] Generated: {output_path}")
    return output_path


def _fallback_stability(prompt: str, clip_number: int) -> Path:
    """
    Fallback: Generate image frames with Stability AI free tier,
    then animate with FFmpeg into a video clip.
    """
    import subprocess

    api_key = os.getenv("STABILITY_API_KEY", "")
    frames_dir = OUTPUT_DIR / f"frames_{clip_number}"
    frames_dir.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / f"clip{clip_number}.mp4"

    # Generate 4 frames (at 2-second intervals for 8s clip)
    for frame_idx in range(4):
        frame_prompt = f"{prompt} Frame {frame_idx + 1} of 4 showing motion progression."
        response = requests.post(
            "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
            headers={
                "Content-Type": "application/json",
                "Accept": "image/png",
                "Authorization": f"Bearer {api_key}"
            },
            json={
                "text_prompts": [{"text": frame_prompt, "weight": 1}],
                "cfg_scale": 7,
                "height": 1920,
                "width": 1080,
                "samples": 1,
                "steps": 30,
            }
        )
        frame_path = frames_dir / f"frame_{frame_idx:04d}.png"
        frame_path.write_bytes(response.content)

    # Animate frames into video with FFmpeg (each frame = 2 seconds)
    subprocess.run([
        "ffmpeg", "-y",
        "-framerate", "0.5",          # 0.5 fps = 2 sec per frame
        "-i", str(frames_dir / "frame_%04d.png"),
        "-vf", "scale=1080:1920,zoompan=z='min(zoom+0.0015,1.5)':d=48",
        "-c:v", "libx264",
        "-t", "8",
        "-pix_fmt", "yuv420p",
        str(output_path)
    ], check=True)

    print(f"[Fallback] Animated frames to: {output_path}")
    return output_path
