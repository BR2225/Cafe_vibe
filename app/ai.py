"""All Gemini calls live here."""
import json
import logging
import os
import time

import numpy as np
from google import genai
from google.genai import types
from pydantic import BaseModel

GEN_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
# Tried in order when the main model is overloaded (503), rate-limited (429) or retired (404).
FALLBACK_MODELS = [m for m in os.getenv("GEMINI_FALLBACKS", "gemini-flash-latest,gemini-3.5-flash,gemini-flash-lite-latest").split(",") if m]
log = logging.getLogger("cafe.ai")
EMB_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
EMB_DIM = 256

_client = None


def client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def generate(contents, config):
    """generate_content with retry + model fallback, so a busy model never breaks the demo."""
    last = None
    for model in [GEN_MODEL, *FALLBACK_MODELS]:
        # "low" thinking keeps the main model fast (~7s vs ~40s); fallbacks use their defaults.
        cfg = config.model_copy(update={"thinking_config": types.ThinkingConfig(thinking_level="low")}) if model == GEN_MODEL else config
        for attempt in range(2):
            try:
                return client().models.generate_content(model=model, contents=contents, config=cfg)
            except genai.errors.APIError as e:
                last = e
                if e.code == 404:  # model retired / not enabled: try the next one
                    break
                if e.code not in (429, 500, 503, 504):
                    raise
                log.warning("Gemini %s failed with %s (attempt %d)", model, e.code, attempt + 1)
                time.sleep(1.5 * (attempt + 1))
    raise last


# ---------- embeddings ----------

def item_text(item) -> str:
    return (
        f"{item.name} ({item.category}). {item.description} {item.blurb} "
        f"Taste: {', '.join(item.tags or [])}. {'Vegetarian' if item.veg else 'Non-vegetarian'}."
    )


def embed(texts: list[str], task: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    out = []
    for i in range(0, len(texts), 100):
        resp = client().models.embed_content(
            model=EMB_MODEL,
            contents=texts[i:i + 100],
            config=types.EmbedContentConfig(task_type=task, output_dimensionality=EMB_DIM),
        )
        for e in resp.embeddings:
            v = np.asarray(e.values, dtype=float)
            out.append((v / (np.linalg.norm(v) or 1.0)).round(5).tolist())
    return out


# ---------- photo -> menu ----------

class DraftItem(BaseModel):
    name: str
    description: str
    price: float | None
    category: str
    veg: bool
    allergens: list[str]
    tags: list[str]
    blurb: str


EXTRACT_PROMPT = """You are digitising a café menu from a photo.
Extract EVERY orderable item you can read. For each item:
- name: as printed (fix obvious OCR-style typos only)
- description: as printed, or "" if none
- price: number only (no currency symbol), null if not visible
- category: one of Coffee, Tea, Cold Drinks, Breakfast, Bites, Mains, Desserts, Other
- veg: true unless it clearly contains meat, fish or egg
- allergens: LIKELY allergens from this list only: dairy, gluten, nuts, egg, soy, sesame, fish, shellfish
- tags: 3-6 short taste/mood words (e.g. strong, sweet, light, filling, refreshing, comforting, shareable, spicy, caffeine-free, indulgent)
- blurb: an appetising 6-12 word line a barista would say about it
Do not invent items that are not on the menu."""


def extract_menu(image_bytes: bytes, mime_type: str) -> list[dict]:
    resp = generate(
        contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime_type), EXTRACT_PROMPT],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=list[DraftItem],
            temperature=0.2,
        ),
    )
    items = resp.parsed or []
    return [i.model_dump() for i in items]


# ---------- owner insights ----------

class Insight(BaseModel):
    headline: str
    detail: str
    action: str


INSIGHT_PROMPT = """You advise the owner of a café called "{name}".
Customers at tables react to AI-suggested menu items with like / meh / nope, and sometimes order.
Here is today's anonymous tap data (JSON):

{data}

Give exactly 3 insights the owner can act on this week. Ground every claim in the numbers
(quote them). Look for: items loved but rarely ordered (price/visibility?), items often rejected,
what each mood (working / meeting / unwinding) gravitates to, and gaps in the menu.
Keep headline under 10 words, detail under 30 words, action under 15 words."""


def owner_insights(cafe_name: str, data: dict) -> list[dict]:
    resp = generate(
        contents=INSIGHT_PROMPT.format(name=cafe_name, data=json.dumps(data, indent=1)),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=list[Insight],
            temperature=0.4,
        ),
    )
    return [i.model_dump() for i in (resp.parsed or [])][:3]
