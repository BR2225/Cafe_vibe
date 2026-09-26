"""Demo menu so the app works before a real menu is photographed."""

# (name, category, price, veg, allergens, tags, description, blurb)
DEMO_MENU = [
    ("Espresso", "Coffee", 140, True, [], ["strong", "bold", "quick"], "Double shot, single origin.", "A short, intense wake-up call."),
    ("Cappuccino", "Coffee", 190, True, ["dairy"], ["classic", "creamy", "balanced"], "Espresso with velvety foam.", "The foam-topped classic, done properly."),
    ("Oat Flat White", "Coffee", 230, True, [], ["smooth", "nutty", "dairy-free"], "Ristretto with steamed oat milk.", "Silky, nutty and naturally dairy-free."),
    ("Hazelnut Latte", "Coffee", 240, True, ["dairy", "nuts"], ["sweet", "nutty", "comforting"], "Latte with house hazelnut syrup.", "Like a warm hug in a cup."),
    ("Pour-over (Chikmagalur)", "Coffee", 260, True, [], ["fruity", "light", "slow"], "Hand-brewed single estate.", "Bright, fruity and worth the wait."),
    ("Masala Chai", "Tea", 120, True, ["dairy"], ["spiced", "comforting", "warm"], "Ginger, cardamom and clove.", "Spiced, milky and deeply comforting."),
    ("Matcha Latte", "Tea", 260, True, ["dairy"], ["earthy", "calm", "creamy"], "Ceremonial matcha with milk.", "Calm, green energy without the jitters."),
    ("Chamomile Honey Tea", "Tea", 170, True, [], ["caffeine-free", "calming", "floral"], "Chamomile with wildflower honey.", "Floral and soothing, zero caffeine."),
    ("Cold Brew", "Cold Drinks", 220, True, [], ["strong", "refreshing", "smooth"], "Steeped 18 hours.", "Smooth, strong and ice cold."),
    ("Vietnamese Iced Coffee", "Cold Drinks", 240, True, ["dairy"], ["sweet", "strong", "indulgent"], "Dark roast with condensed milk.", "Bold coffee meets sweet condensed milk."),
    ("Mango Lassi", "Cold Drinks", 180, True, ["dairy"], ["sweet", "fruity", "refreshing"], "Alphonso mango and yoghurt.", "Thick, sunny and very mango."),
    ("Mint Lime Cooler", "Cold Drinks", 150, True, [], ["refreshing", "light", "caffeine-free"], "Fresh lime, mint, soda.", "Zingy, fizzy and instantly cooling."),
    ("Avocado Toast", "Breakfast", 320, True, ["gluten"], ["fresh", "light", "healthy"], "Sourdough, chilli flakes, lime.", "Creamy avo on crunchy sourdough."),
    ("Masala Omelette", "Breakfast", 220, False, ["egg"], ["savoury", "spicy", "filling"], "Onion, tomato, green chilli.", "Desi-style omelette with a kick."),
    ("Granola Bowl", "Breakfast", 260, True, ["dairy", "nuts"], ["light", "healthy", "fresh"], "Yoghurt, berries, house granola.", "Crunchy, fruity and feel-good."),
    ("Butter Croissant", "Bites", 160, True, ["dairy", "gluten"], ["flaky", "buttery", "light"], "Baked every morning.", "Flaky layers, all butter."),
    ("Paneer Tikka Sandwich", "Bites", 280, True, ["dairy", "gluten"], ["spicy", "filling", "savoury"], "Grilled paneer, mint chutney.", "Smoky paneer with a chutney punch."),
    ("Chicken Pesto Panini", "Bites", 320, False, ["dairy", "gluten", "nuts"], ["filling", "savoury", "herby"], "Grilled chicken, basil pesto.", "Hearty, herby and pressed hot."),
    ("Loaded Nachos", "Bites", 290, True, ["dairy"], ["shareable", "spicy", "indulgent"], "Cheese sauce, salsa, jalapeños.", "Built for sharing (or not)."),
    ("Hummus & Pita Platter", "Bites", 270, True, ["gluten", "sesame"], ["shareable", "healthy", "savoury"], "Hummus, warm pita, veggies.", "A table-friendly platter to graze on."),
    ("Chocolate Brownie", "Desserts", 180, True, ["dairy", "gluten", "egg", "nuts"], ["indulgent", "rich", "sweet"], "Warm, fudgy, walnut.", "Warm, fudgy and unapologetically rich."),
    ("Basque Cheesecake", "Desserts", 290, True, ["dairy", "egg"], ["creamy", "indulgent", "sweet"], "Burnt top, soft centre.", "Caramelised top, cloud-soft centre."),
    ("Banana Bread", "Desserts", 150, True, ["gluten", "egg", "nuts"], ["comforting", "sweet", "homely"], "Toasted with salted butter.", "Toasted, buttery and homely."),
    ("Churros & Chocolate", "Desserts", 240, True, ["dairy", "gluten"], ["shareable", "sweet", "indulgent"], "Cinnamon sugar, dark dip.", "Crispy, cinnamon-sugared and made to dip."),
]


def demo_items():
    return [
        dict(name=n, category=c, price=p, veg=v, allergens=a, tags=t, description=d, blurb=b)
        for (n, c, p, v, a, t, d, b) in DEMO_MENU
    ]
