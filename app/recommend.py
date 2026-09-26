"""Taste engine: a per-visit preference vector nudged by taps, ranked against item embeddings.

No LLM call happens in the tap loop - it's pure vector math, so every tap is instant.

Café items all embed close together ("it's food/drink at a café"), so every vector is
centred on the menu's mean before comparing. That leaves only what makes an item
*different* - coffee vs tea, sweet vs savoury, light vs filling - which is what taste is.
"""
import os
from datetime import datetime, timedelta, timezone

import numpy as np

from . import ai

SET_SIZE = 4
TZ = timezone(timedelta(minutes=int(os.getenv("TZ_OFFSET_MINUTES", "330"))))  # IST default

MOODS = {
    "work": ("Working", "A focused work session at a laptop: steady caffeine, easy non-messy snacks, drinks to sip slowly"),
    "meet": ("Meeting", "Catching up with a friend or colleague: crowd-pleasing drinks and something to share"),
    "unwind": ("Unwinding", "Relaxing and unwinding: comforting, indulgent treats and calming, low-caffeine drinks"),
}
MOOD_REASON = {
    "work": "Good fuel for a focused session",
    "meet": "Easy to share and talk over",
    "unwind": "A cosy, slow-down pick",
}

# How far each tap moves the taste vector.
WEIGHTS = {"like": 1.0, "meh": 0.25, "nope": -0.7}

_ctx_cache: dict[tuple, dict[int, float]] = {}
_space_cache: dict[tuple, tuple] = {}


def daypart(now=None) -> str:
    h = (now or datetime.now(TZ)).hour
    if h < 11:
        return "morning, breakfast time"
    if h < 16:
        return "afternoon, lunch time"
    if h < 20:
        return "evening, snack time"
    return "late night"


def _unit(v):
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v)
    return v / n if n else v


def space(menu):
    """Centred, normalised item vectors for the whole menu + a 'strongly similar' threshold."""
    emb = [i for i in menu if i.embedding]
    key = tuple((i.id, len(i.embedding)) for i in emb)
    if key not in _space_cache:
        if not emb:
            return np.zeros(ai.EMB_DIM), {}, 1.0
        m = np.asarray([i.embedding for i in emb])
        mean = m.mean(axis=0)
        c = m - mean
        c /= np.linalg.norm(c, axis=1, keepdims=True).clip(min=1e-9)
        sims = c @ c.T
        np.fill_diagonal(sims, np.nan)
        strong = float(np.nanpercentile(sims, 90)) if len(emb) > 2 else 1.0
        _space_cache.clear()
        _space_cache[key] = (mean, {i.id: c[k] for k, i in enumerate(emb)}, strong)
    return _space_cache[key]


CTX_WEIGHT = 0.15  # how much the mood still counts once taps start


def context_scores(menu, mood) -> dict[int, float]:
    """Cold start: how well each item fits the mood + time of day (standardised).

    Raw (un-centred) similarity works best for this query-vs-item match.
    """
    if mood not in MOODS:
        return {}
    _, vecs, _ = space(menu)
    key = (mood, daypart(), tuple(sorted(vecs)))
    if key not in _ctx_cache:
        q = np.asarray(ai.embed([f"{MOODS[mood][1]}. It's {key[1]}."], task="SEMANTIC_SIMILARITY")[0])
        items = [i for i in menu if i.id in vecs]
        raw = np.asarray([np.dot(i.embedding, q) for i in items])
        z = (raw - raw.mean()) / (raw.std() or 1.0)
        if len(_ctx_cache) > 64:
            _ctx_cache.clear()
        _ctx_cache[key] = {i.id: float(v) for i, v in zip(items, z)}
    return _ctx_cache[key]


def initial_pref(menu, mood: str) -> list[float]:
    """Taste vector starts empty; the mood carries the first set on its own."""
    context_scores(menu, mood)  # warm the cache
    return [0.0] * len(next(iter(space(menu)[1].values()), np.zeros(ai.EMB_DIM)))


def nudge(pref, item, weight, menu):
    _, vecs, _ = space(menu)
    if item.id not in vecs:
        return pref
    return _unit(_unit(pref) + weight * vecs[item.id]).round(5).tolist()


def scores(items, visit, menu) -> dict[int, float]:
    _, vecs, _ = space(menu)
    p = _unit(visit.pref) if visit.pref else None
    ctx = context_scores(menu, visit.mood)
    return {
        i.id: (float(vecs[i.id] @ p) if p is not None else 0.0) + CTX_WEIGHT * ctx.get(i.id, 0.0)
        for i in items if i.id in vecs
    }


def pick(menu, visit, keep_ids=(), exclude_ids=(), n=SET_SIZE):
    """Pick a varied set: high match, but penalise near-duplicates (MMR-style)."""
    _, vecs, _ = space(menu)
    by_id = {i.id: i for i in menu}
    chosen = [by_id[k] for k in keep_ids if k in by_id]
    excl = set(exclude_ids) | {c.id for c in chosen}
    pool = [i for i in menu if i.available and i.id in vecs and i.id not in excl]
    sc = scores(pool, visit, menu)
    while len(chosen) < n and pool:
        def value(i):
            sim = max((float(vecs[i.id] @ vecs[c.id]) for c in chosen if c.id in vecs), default=0.0)
            same_cat = sum(1 for c in chosen if c.category == i.category)
            return sc[i.id] - 0.4 * max(sim, 0.0) - 0.08 * same_cat
        best = max(pool, key=value)
        chosen.append(best)
        pool.remove(best)
    return chosen


def reason(item, visit, menu, popular_ids) -> str:
    _, vecs, strong = space(menu)
    by_id = {i.id: i for i in menu}
    liked = [by_id[i] for i in visit.liked or [] if i in by_id and i != item.id and i in vecs]
    if liked and item.id in vecs:
        best = max(liked, key=lambda l: float(vecs[l.id] @ vecs[item.id]))
        if float(vecs[best.id] @ vecs[item.id]) >= strong:
            return f"Because you liked {best.name}"
    if item.id in popular_ids:
        return "Loved by other tables today"
    return MOOD_REASON.get(visit.mood or "", "Picked for you")
