SCENES_SYSTEM = """You split a narration script into vertical short-video scenes for FFmpeg + still images.
Return ONLY valid JSON.

IMPORTANT: The script text below is a COMPLETE flowing narration. Split it into 6-10 scenes.
Each scene's "text" must be a CONTIGUOUS segment of the original script — word for word.
All scene texts concatenated must reproduce the ENTIRE original script with no gaps or additions.
Each scene should have 2-4 sentences — do NOT make scenes with only one short sentence.

image_prompt (English) must comply with OpenAI image safety: NO gore, injury, torture, execution, bound victims, weapons against people, nudity, or terrified faces.
Use stylized digital illustration / animated documentary art style. Each image must DIRECTLY DEPICT the event described in that scene's narration — not generic mood shots. Show the actual scene: people as distant silhouettes or stylized figures (no detailed faces), historical settings, key objects, actions. Use dramatic lighting, rich saturated colors, bold compositions. No text in image.
motion must be one of: zoom_in, zoom_out, pan_left, pan_right."""

SCENES_USER_TEMPLATE = """Script to adapt (language may be non-English; keep scene text in the SAME language as the script):
---
{script}
---

Rules:
- Produce between 6 and 10 scenes.
- Each scene: duration between 5 and 10 seconds (float).
- Total duration of all scenes should be between 40 and 65 seconds.
- scene_id starts at 1 and increments.
- text: a CONTIGUOUS segment of the script above (2-4 sentences). All texts joined = full script.
- image_prompt: English, stylized digital illustration that DEPICTS the narrated event. Policy-safe (see system rules).
- Vary motion across scenes.
- Include the full script text in the "narration" field.

JSON shape:
{{
  "narration": "Full script text here...",
  "scenes": [
    {{
      "scene_id": 1,
      "duration": 8.0,
      "text": "Contiguous segment of the script...",
      "image_prompt": "Stylized illustration of ...",
      "motion": "zoom_in"
    }}
  ]
}}
"""
