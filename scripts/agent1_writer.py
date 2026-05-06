"""
agent1_writer.py — Writer Agent
Uses OpenAI GPT-4o to write a kids educational animated poem with viral hook.
"""

import os
import json
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """You are an expert kids educational content writer specializing in
animated music videos for children aged 3-8. You create fun, rhyming, educational poems
with viral hooks. Your language is always simple, positive, and age-appropriate.
Always respond with valid JSON only — no markdown, no extra text."""

def run(topic: str, memory: dict) -> dict:
    """Generate script for today's topic. Uses memory to improve hooks over time."""

    best_hooks = memory.get("best_performing_hooks", [])
    hook_guidance = ""
    if best_hooks:
        hook_guidance = f"\nPreviously successful hook styles: {best_hooks[:3]}"

    prompt = f"""Write a kids animated educational music video script.
Topic: {topic}
{hook_guidance}

Return ONLY this JSON structure:
{{
  "hook": "One powerful opening sentence (max 12 words, starts with 'Did you know' or a question)",
  "verses": [
    ["line1", "line2", "line3", "line4"],
    ["line1", "line2", "line3", "line4"],
    ["line1", "line2", "line3", "line4"]
  ],
  "chorus": ["line1", "line2"],
  "style_prompt": "Detailed visual description for AI video generation: animation style, colors, characters, scene. Kid-friendly, bright, educational.",
  "educational_fact": "One amazing true fact about this topic that kids will love"
}}

Rules:
- AABB rhyme scheme per verse
- Max 6 words per line
- Include one real educational fact
- Characters should be friendly animals or cartoon kids
- Bright pastel colors, Pixar-style animation description"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=0.8,
        max_tokens=800
    )

    raw = response.choices[0].message.content.strip()
    # Strip markdown fences if present
    raw = raw.replace("```json", "").replace("```", "").strip()
    script = json.loads(raw)
    return script
