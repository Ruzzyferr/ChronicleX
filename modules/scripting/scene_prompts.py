SCENES_SYSTEM = """You split a narration script into vertical short-video scenes for FFmpeg + still images.
Return ONLY valid JSON. Each scene is ONE short spoken sentence. image_prompt must be visually representable, cinematic, dark historical realism, fog, dramatic lighting, no text in image.
motion must be one of: zoom_in, zoom_out, pan_left, pan_right."""

SCENES_USER_TEMPLATE = """Script to adapt (language may be non-English; keep scene text in the SAME language as the script):
---
{script}
---

Rules:
- Produce between 6 and 10 scenes.
- Each scene: duration between 3 and 6 seconds (float).
- Total duration of all scenes should be between 35 and 55 seconds.
- scene_id starts at 1 and increments.
- text: one short sentence matching that part of the script.
- image_prompt: English visual description for an AI image model (no words on image).
- Vary motion across scenes.

JSON shape:
{{
  "scenes": [
    {{
      "scene_id": 1,
      "duration": 4.5,
      "text": "...",
      "image_prompt": "dark cinematic ...",
      "motion": "zoom_in"
    }}
  ]
}}
"""
