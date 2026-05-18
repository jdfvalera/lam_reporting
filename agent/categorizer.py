import json
import logging
from pathlib import Path

from processors.usm import USM_ALLOWED_CATEGORIES

log = logging.getLogger(__name__)

# Grows automatically as new products are seen
LEARNED_FILE = Path(__file__).parent.parent / "usm_category_learned.json"

# Keyword rules: category → lowercase keywords to match anywhere in product name
KEYWORD_RULES: dict[str, list[str]] = {
    "Beverages": [
        "water", "juice", "soda", "cola", "coffee", "tea", "beer", "wine",
        "drink", "beverage", "lemonade", "gatorade", "sparkling", "coconut water",
        "smoothie", "kombucha", "cider", "espresso", "brew", "creamer",
        "energy drink", "sports drink", "punch", "cocoa", "hot chocolate",
    ],
    "Breakfast / Snacks": [
        "cereal", "granola", "oatmeal", "oat", "protein bar", "snack bar",
        "chip", "cracker", "cookie", "pretzel", "popcorn", "snack", "trail mix",
        "waffle", "pancake", "syrup", "muffin", "bagel", "toast", "breakfast",
        "peanut butter", "almond butter", "jam", "jelly", "honey", "spread",
        "rice cake", "nut mix", "dried fruit",
        "bread", "loaf", "bun", "roll",
        "pasta", "spaghetti", "penne", "linguine", "fettuccine", "rigatoni",
        "macaroni", "lasagna noodle", "angel hair", "rotini", "farfalle",
    ],
    "Canned Goods": [
        "canned", "tomato sauce", "tomato paste", "baked beans", "black beans",
        "kidney beans", "chickpea", "garbanzo", "lentil", "canned corn",
        "canned peas", "fruit cup", "mandarin", "canned peach", "canned pineapple",
        "canned tuna", "canned salmon", "canned chicken", "canned tomato",
    ],
    "Dairy / Eggs": [
        "cheese", "yogurt", "butter", "cream cheese", "sour cream",
        "whipped cream", "half and half", "egg", "milk", "dairy",
        "cottage cheese", "ghee", "kefir", "string cheese", "shredded cheese",
    ],
    "Frozen Food": [
        "frozen", "ice cream", "popsicle", "gelato", "sorbet", "nugget",
        "frozen pizza", "frozen meal", "frozen entree", "frozen dinner",
        "frozen waffle", "frozen burrito", "frozen vegetable",
    ],
    "Meat": [
        "beef", "chicken breast", "chicken thigh", "chicken wing", "pork",
        "turkey", "sausage", "bacon", "steak", "ham", "ground beef",
        "ground turkey", "ground meat", "lamb", "veal", "brisket", "rib",
        "roast", "pork chop", "hot dog", "pepperoni", "salami", "deli meat",
        "lunch meat", "chorizo", "bratwurst", "drumstick",
    ],
    "Produce": [
        "apple", "banana", "orange", "strawberr", "blueberr", "raspberr",
        "cherr", "grape", "melon", "watermelon", "cantaloupe", "peach",
        "pear", "plum", "mango", "avocado", "lettuce", "spinach", "kale",
        "arugula", "tomato", "broccoli", "carrot", "onion", "potato",
        "bell pepper", "cucumber", "zucchini", "squash", "mushroom", "celery",
        "asparagus", "sweet corn", "fresh herb", "garlic", "ginger",
        "lemon", "lime",
    ],
    "Soups and Broths": [
        "soup", "broth", "stock", "chowder", "bisque", "stew", "ramen",
        "bouillon", "instant noodle",
    ],
    "Seafood": [
        "shrimp", "salmon", "seafood", "tilapia", "cod", "halibut", "scallop",
        "crab", "lobster", "clam", "oyster", "mahi", "catfish", "trout",
        "sardine", "anchovy", "fish fillet", "fish stick",
    ],
    "Others - Home & Garden": [
        "plant", "garden", "fertilizer", "outdoor", "lawn", "seed",
        "potting soil", "mulch", "insect", "bug spray",
    ],
    "Others - Sauces and Condiments": [
        "sauce", "ketchup", "mustard", "mayonnaise", "mayo", "dressing",
        "salsa", "vinegar", "soy sauce", "hot sauce", "bbq sauce", "marinade",
        "seasoning", "ranch", "hummus", "guacamole", "relish", "pesto",
        "alfredo", "pasta sauce", "taco sauce", "buffalo sauce", "teriyaki",
        "sriracha", "olive oil", "cooking oil", "canola oil",
    ],
    "Others - Cleaning Products": [
        "detergent", "dish soap", "laundry", "bleach", "disinfect", "wipes",
        "tide ", "lysol", "dawn ", "bounty", "paper towel", "trash bag",
        "sponge", "scrub", "fabric softener", "dryer sheet", "all-purpose",
        "bathroom cleaner", "floor cleaner",
    ],
    "Others - Party & Celebration": [
        "party", "celebration", "birthday", "festive", "holiday",
        "decoration", "balloon", "candle", "gift", "seasonal",
    ],
}

_FALLBACK = "Others - Party & Celebration"


def _load_learned() -> dict[str, str]:
    if LEARNED_FILE.exists():
        with open(LEARNED_FILE) as f:
            return json.load(f)
    return {}


def _save_learned(mapping: dict[str, str]) -> None:
    with open(LEARNED_FILE, "w") as f:
        json.dump(mapping, f, indent=2, sort_keys=True)
    log.info(f"Saved {len(mapping)} entries to {LEARNED_FILE.name}")


def _keyword_match(product: str) -> str | None:
    name_lower = product.lower()
    # Try longest keywords first so "pasta sauce" beats "pasta", "dish soap" beats "soap", etc.
    all_kw = sorted(
        ((kw, cat) for cat, kws in KEYWORD_RULES.items() for kw in kws),
        key=lambda x: len(x[0]),
        reverse=True,
    )
    for kw, category in all_kw:
        if kw in name_lower:
            return category
    return None


def auto_categorize(product_names: list[str]) -> dict[str, str]:
    """
    Categorize USM products. Resolution order:
      1. Exact match in usm_category_learned.json  (fastest, user-correctable)
      2. Keyword rules                              (automatic)
      3. Fallback to Others - Party & Celebration   (logged as needing review)

    Every new product+category pair is saved to usm_category_learned.json
    so the file grows over time. Edit it directly to correct any wrong mappings.
    """
    if not product_names:
        return {}

    learned      = _load_learned()
    result       = {}
    newly_added  = {}
    needs_review = []

    for product in product_names:
        if product in learned:
            result[product] = learned[product]
            continue

        category = _keyword_match(product)

        if category:
            log.info(f"  '{product}' → {category} (keyword match)")
        else:
            category = _FALLBACK
            needs_review.append(product)
            log.warning(f"  '{product}' → {category} (no match — review {LEARNED_FILE.name})")

        result[product]      = category
        newly_added[product] = category

    if newly_added:
        learned.update(newly_added)
        _save_learned(learned)

    if needs_review:
        log.warning(
            f"{len(needs_review)} product(s) defaulted to '{_FALLBACK}'. "
            f"Open {LEARNED_FILE.name} and set the correct category — it will be used next time."
        )

    return result
