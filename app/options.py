"""Item customisations (size, milk, sweetness, ...).

Every item gets sensible option groups from its category, so demo menus and photo-onboarded
menus work with zero setup. Options printed on the menu (read by Gemini into item.options)
replace the category default group with the same name.

Group:  {"name", "type": "single" | "multi", "choices": [{"label", "price", "default"?}]}
Prices are deltas on top of the item's base price. The server always recomputes them.
"""

SIZE = {"name": "Size", "type": "single", "choices": [
    {"label": "Regular", "price": 0, "default": True}, {"label": "Large", "price": 40}]}
SWEET = {"name": "Sweetness", "type": "single", "choices": [
    {"label": "No sugar", "price": 0}, {"label": "Less sugar", "price": 0},
    {"label": "Regular", "price": 0, "default": True}, {"label": "Extra sweet", "price": 0}]}
MILK = {"name": "Milk", "type": "single", "choices": [
    {"label": "Regular milk", "price": 0, "default": True}, {"label": "Oat milk", "price": 40},
    {"label": "Almond milk", "price": 40}, {"label": "Skimmed milk", "price": 0}]}
MILK_BLACK = {"name": "Milk", "type": "single", "choices": [
    {"label": "No milk", "price": 0, "default": True}, {"label": "Splash of milk", "price": 0},
    {"label": "Oat milk", "price": 40}]}
TEMP = {"name": "Temperature", "type": "single", "choices": [
    {"label": "Hot", "price": 0, "default": True}, {"label": "Extra hot", "price": 0}, {"label": "Iced", "price": 20}]}
COFFEE_EXTRAS = {"name": "Extras", "type": "multi", "choices": [
    {"label": "Extra shot", "price": 50}, {"label": "Hazelnut syrup", "price": 30},
    {"label": "Vanilla syrup", "price": 30}, {"label": "Caramel syrup", "price": 30},
    {"label": "Whipped cream", "price": 30}]}
TEA_SWEET = {"name": "Sweetness", "type": "single", "choices": [
    {"label": "No sugar", "price": 0}, {"label": "Less sugar", "price": 0},
    {"label": "Regular", "price": 0, "default": True}, {"label": "Honey instead", "price": 20}]}
ICE = {"name": "Ice", "type": "single", "choices": [
    {"label": "Regular ice", "price": 0, "default": True}, {"label": "Less ice", "price": 0}, {"label": "No ice", "price": 0}]}
SPICE = {"name": "Spice level", "type": "single", "choices": [
    {"label": "Mild", "price": 0}, {"label": "Medium", "price": 0, "default": True}, {"label": "Spicy", "price": 0}]}
WARM = {"name": "Serve", "type": "single", "choices": [
    {"label": "As is", "price": 0, "default": True}, {"label": "Warmed up", "price": 0}]}
DESSERT_ADDONS = {"name": "Add-ons", "type": "multi", "choices": [{"label": "Scoop of vanilla ice cream", "price": 60}]}

BLACK_COFFEE = ("espresso", "americano", "pour-over", "pour over", "black", "ristretto", "cold brew", "long black")
SPICY_WORDS = ("masala", "tikka", "chilli", "chili", "spicy", "jalape", "bhurji", "peri")


def _has(item, words):
    text = f"{item.name} {item.description} {' '.join(item.tags or [])}".lower()
    return any(w in text for w in words)


def default_groups(item) -> list[dict]:
    cat = (item.category or "").lower()
    dairy = "dairy" in (item.allergens or [])
    if cat == "coffee":
        # Judge "black coffee" by the name only: a cappuccino's description mentions espresso too.
        black = not dairy and any(w in item.name.lower() for w in BLACK_COFFEE)
        return [SIZE, MILK_BLACK if black else MILK, SWEET, TEMP, COFFEE_EXTRAS]
    if cat == "tea":
        groups = [SIZE]
        if dairy or _has(item, ("chai", "latte", "milk")):
            groups.append(MILK)
        return groups + [TEA_SWEET, TEMP]
    if cat == "cold drinks":
        groups = [SIZE, SWEET, ICE]
        if _has(item, ("coffee", "brew", "mocha", "latte")):
            groups.append({**COFFEE_EXTRAS, "choices": COFFEE_EXTRAS["choices"][:4]})
        return groups
    if cat in ("breakfast", "bites", "mains"):
        groups = []
        if _has(item, SPICY_WORDS):
            groups.append(SPICE)
        addons = [{"label": "Cut in half to share", "price": 0}]
        if dairy and _has(item, ("cheese", "paneer", "sandwich", "panini", "nachos", "toast")):
            addons.insert(0, {"label": "Extra cheese", "price": 30})
        groups.append({"name": "Add-ons", "type": "multi", "choices": addons})
        return groups
    if cat == "desserts":
        return [WARM, DESSERT_ADDONS]
    return []


def options_for(item) -> list[dict]:
    """Category defaults, with any menu-specific groups (item.options) replacing same-named ones."""
    own = [g for g in (item.options or []) if g.get("name") and g.get("choices")]
    own_names = {g["name"].lower() for g in own}
    groups = [dict(g) for g in default_groups(item) if g["name"].lower() not in own_names] + [dict(g) for g in own]
    for g in groups:  # make sure every single-choice group has exactly one default
        if g.get("type", "single") == "single" and not any(c.get("default") for c in g["choices"]):
            g["choices"] = [{**c, "default": i == 0} for i, c in enumerate(g["choices"])]
    return groups


def price_line(item, chosen: dict | None) -> tuple[float | None, list[str], dict]:
    """Validate a customer's choices and return (unit price, summary labels, clean choices)."""
    chosen = chosen or {}
    delta, summary, clean = 0.0, [], {}
    for g in options_for(item):
        valid = {c["label"]: c for c in g["choices"]}
        picked = [lab for lab in (chosen.get(g["name"]) or []) if lab in valid]
        if g.get("type", "single") == "single":
            default = next(c["label"] for c in g["choices"] if c.get("default"))
            picked = picked[:1] or [default]
            if picked[0] != default:
                summary.append(picked[0])
        else:
            picked = list(dict.fromkeys(picked))
            summary.extend(picked)
        clean[g["name"]] = picked
        delta += sum(float(valid[p].get("price") or 0) for p in picked)
    price = None if item.price is None else round(item.price + delta, 2)
    return price, summary, clean
