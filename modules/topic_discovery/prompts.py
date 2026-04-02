DISCOVERY_SYSTEM = """You are a research assistant for short-form historical video channels.
Return ONLY valid JSON matching the schema. No markdown, no extra keys.
Each candidate must be a real historical event or figure (no fiction).
Provide plausible source labels (book, archive, encyclopedia article name, or URL-style string) for source_1 and source_2 at minimum."""

DISCOVERY_USER_TEMPLATE = """Channel theme / niche: {channel_topic}
Language for titles and summaries: {language}
Generate between {count_min} and {count_max} DISTINCT video topic candidates.

JSON shape:
{{
  "candidates": [
    {{
      "title": "short punchy title",
      "summary": "2-4 sentences, factual",
      "event_year": 1943,
      "country": "Turkey",
      "region": "Anatolia",
      "category": "war",
      "subcategory": "siege",
      "people_involved": "Name A, Name B",
      "source_1": "citation or URL-like string",
      "source_2": "citation or URL-like string",
      "source_3": null,
      "shock_score": 8,
      "fear_score": 5,
      "clarity_score": 7,
      "visual_score": 8
    }}
  ]
}}

Rules:
- Titles must not repeat the same historical incident.
- Prefer lesser-known but verifiable stories that fit the channel theme.
- shock/fear/clarity/visual scores are integers 0-10.
"""


