from sqlalchemy.orm import Session
from app.models import Item, ItemAlias, Household

SEED_ITEMS = [
    # Dairy & Refrigerated
    {
        "name": "Whole Milk",
        "category": "Dairy",
        "standard_unit": "gallon",
        "shelf_life": 10,
        "is_bulk": False,
        "aliases": ["milk", "whole milk", "kirkland whole milk", "organic whole milk", "horizon whole milk", "milk gal"]
    },
    {
        "name": "2% Reduced Fat Milk",
        "category": "Dairy",
        "standard_unit": "gallon",
        "shelf_life": 10,
        "is_bulk": False,
        "aliases": ["2% milk", "reduced fat milk", "kirkland 2% milk", "organic 2% milk"]
    },
    {
        "name": "Large Grade A Eggs",
        "category": "Dairy",
        "standard_unit": "count",
        "shelf_life": 28,
        "is_bulk": False,
        "aliases": ["eggs", "large eggs", "cage free eggs", "kirkland eggs", "brown eggs", "pasture raised eggs", "large grade a eggs"]
    },
    {
        "name": "Greek Yogurt",
        "category": "Dairy",
        "standard_unit": "oz",
        "shelf_life": 14,
        "is_bulk": False,
        "aliases": ["chobani greek yogurt", "fage yogurt", "plain greek yogurt", "vanilla greek yogurt", "kirkland greek yogurt"]
    },
    {
        "name": "Cheddar Cheese",
        "category": "Dairy",
        "standard_unit": "oz",
        "shelf_life": 30,
        "is_bulk": False,
        "aliases": ["sharp cheddar", "mild cheddar", "shredded cheddar", "cheddar block", "tillamook cheddar"]
    },
    {
        "name": "Unsalted Butter",
        "category": "Dairy",
        "standard_unit": "lb",
        "shelf_life": 60,
        "is_bulk": False,
        "aliases": ["butter", "sweet cream butter", "kerrygold butter", "kirkland butter", "amul pasteurized unsalted butter", "amul butter"]
    },
    {
        "name": "Amul Cheese",
        "category": "Dairy",
        "standard_unit": "g",
        "shelf_life": 60,
        "is_bulk": False,
        "aliases": ["amul cheese", "cheese chiplets", "amul cheese chiplets", "amul cheese chiplets 200gm"]
    },

    # Fresh Produce
    {
        "name": "Bananas",
        "category": "Produce",
        "standard_unit": "lb",
        "shelf_life": 6,
        "is_bulk": False,
        "aliases": ["banana", "organic bananas", "org bnnas", "cavendish bananas", "chiquita bananas"]
    },
    {
        "name": "Baby Spinach",
        "category": "Produce",
        "standard_unit": "oz",
        "shelf_life": 7,
        "is_bulk": False,
        "aliases": ["spinach", "organic baby spinach", "org spinach", "spinach tub", "365 baby spinach", "spinach bag small", "spinach bag"]
    },
    {
        "name": "Hass Avocados",
        "category": "Produce",
        "standard_unit": "count",
        "shelf_life": 5,
        "is_bulk": False,
        "aliases": ["avocado", "avocados", "organic avocados", "tj avocado bag", "hass avocado"]
    },
    {
        "name": "Gala Apples",
        "category": "Produce",
        "standard_unit": "lb",
        "shelf_life": 21,
        "is_bulk": False,
        "aliases": ["apple", "apples", "gala apple", "organic gala apples", "fuji apples", "honeycrisp apples"]
    },
    {
        "name": "Roma Tomatoes",
        "category": "Produce",
        "standard_unit": "lb",
        "shelf_life": 7,
        "is_bulk": False,
        "aliases": ["tomato", "tomatoes", "roma tomato", "organic roma tomatoes", "vine tomatoes", "tomato round", "round tomato"]
    },
    {
        "name": "Yellow Onions",
        "category": "Produce",
        "standard_unit": "lb",
        "shelf_life": 30,
        "is_bulk": False,
        "aliases": ["onion", "onions", "yellow onion bag", "sweet onions"]
    },
    {
        "name": "Red Onion",
        "category": "Produce",
        "standard_unit": "lb",
        "shelf_life": 30,
        "is_bulk": False,
        "aliases": ["red onion", "onion red", "onions red", "red onions"]
    },
    {
        "name": "Russet Potatoes",
        "category": "Produce",
        "standard_unit": "lb",
        "shelf_life": 30,
        "is_bulk": True,
        "aliases": ["potatoes", "potato", "baking potatoes", "russet potato bag 5lb", "potato white small", "white potato"]
    },
    {
        "name": "Fresh Garlic",
        "category": "Produce",
        "standard_unit": "count",
        "shelf_life": 60,
        "is_bulk": False,
        "aliases": ["garlic", "garlic bulb", "organic garlic"]
    },
    {
        "name": "Green Bell Pepper",
        "category": "Produce",
        "standard_unit": "lb",
        "shelf_life": 10,
        "is_bulk": False,
        "aliases": ["bell pepper", "bellpepper green", "green bell pepper", "green pepper", "capsicum"]
    },
    {
        "name": "Red Bell Pepper",
        "category": "Produce",
        "standard_unit": "lb",
        "shelf_life": 10,
        "is_bulk": False,
        "aliases": ["bell pepper red", "bellpepper red", "red bell pepper", "red pepper"]
    },
    {
        "name": "Fresh Cilantro",
        "category": "Produce",
        "standard_unit": "bunch",
        "shelf_life": 7,
        "is_bulk": False,
        "aliases": ["cilantro", "coriander", "coriander leaves", "fresh cilantro bunch"]
    },
    {
        "name": "Fresh Cucumber",
        "category": "Produce",
        "standard_unit": "count",
        "shelf_life": 7,
        "is_bulk": False,
        "aliases": ["cucumber", "cucumbers", "persian cucumber"]
    },
    {
        "name": "Fresh Ginger",
        "category": "Produce",
        "standard_unit": "lb",
        "shelf_life": 28,
        "is_bulk": False,
        "aliases": ["ginger", "fresh ginger", "ginger root", "adrak"]
    },
    {
        "name": "Green Beans",
        "category": "Produce",
        "standard_unit": "lb",
        "shelf_life": 10,
        "is_bulk": False,
        "aliases": ["bean green", "green bean", "green beans", "french beans"]
    },
    {
        "name": "Thai Green Chili",
        "category": "Produce",
        "standard_unit": "lb",
        "shelf_life": 14,
        "is_bulk": False,
        "aliases": ["chilli thai", "green chili", "thai chili", "green chillies", "hari mirch"]
    },
    {
        "name": "Pomegranate",
        "category": "Produce",
        "standard_unit": "count",
        "shelf_life": 14,
        "is_bulk": False,
        "aliases": ["pomegranate", "pomegranates", "anar"]
    },
    {
        "name": "Frozen Green Peas",
        "category": "Produce",
        "standard_unit": "lb",
        "shelf_life": 180,
        "is_bulk": True,
        "aliases": ["green peas", "frozen green peas", "veer frozen green peas", "peas", "matar"]
    },

    # Meat & Seafood
    {
        "name": "Boneless Skinless Chicken Breast",
        "category": "Meat & Seafood",
        "standard_unit": "lb",
        "shelf_life": 3,
        "is_bulk": False,
        "aliases": ["chicken breast", "organic chicken breast", "kirkland chicken", "chk breast", "bonus chk breast"]
    },
    {
        "name": "Ground Beef 80/20",
        "category": "Meat & Seafood",
        "standard_unit": "lb",
        "shelf_life": 3,
        "is_bulk": False,
        "aliases": ["ground beef", "beef 80/20", "angus ground beef", "organic ground beef"]
    },
    {
        "name": "Atlantic Salmon Fillet",
        "category": "Meat & Seafood",
        "standard_unit": "lb",
        "shelf_life": 2,
        "is_bulk": False,
        "aliases": ["salmon", "fresh salmon", "wild salmon", "salmon fillet"]
    },
    {
        "name": "Thick Cut Bacon",
        "category": "Meat & Seafood",
        "standard_unit": "lb",
        "shelf_life": 14,
        "is_bulk": False,
        "aliases": ["bacon", "applewood bacon", "smoked bacon", "kirkland bacon"]
    },

    # Bakery
    {
        "name": "Sourdough Bread",
        "category": "Bakery",
        "standard_unit": "count",
        "shelf_life": 6,
        "is_bulk": False,
        "aliases": ["sourdough", "artisan sourdough", "san francisco sourdough loaf"]
    },
    {
        "name": "Whole Wheat Bread",
        "category": "Bakery",
        "standard_unit": "count",
        "shelf_life": 7,
        "is_bulk": False,
        "aliases": ["wheat bread", "100% whole wheat", "daves killer bread", "sandwich bread"]
    },
    {
        "name": "Pizza Base",
        "category": "Bakery",
        "standard_unit": "count",
        "shelf_life": 10,
        "is_bulk": False,
        "aliases": ["pizza base", "nib pizza base", "pizza crust"]
    },

    # Pantry & Staples
    {
        "name": "Idli Dosa Batter",
        "category": "Refrigerated",
        "standard_unit": "ml",
        "shelf_life": 10,
        "is_bulk": False,
        "aliases": ["dosa batter", "idli batter", "idli dosa batter", "chennai caters idli dosa batter"]
    },
    {
        "name": "Masala Noodles",
        "category": "Pantry",
        "standard_unit": "g",
        "shelf_life": 180,
        "is_bulk": False,
        "aliases": ["ramen masala noodles", "maggi noodles", "masala noodles", "ramen noodles", "ramen masala one sachet"]
    },
    {
        "name": "Jasmine Rice",
        "category": "Pantry",
        "standard_unit": "lb",
        "shelf_life": 365,
        "is_bulk": True,
        "aliases": ["rice", "white rice", "thai jasmine rice", "kirkland jasmine rice"]
    },
    {
        "name": "Extra Virgin Olive Oil",
        "category": "Pantry",
        "standard_unit": "liter",
        "shelf_life": 180,
        "is_bulk": True,
        "aliases": ["olive oil", "evoo", "kirkland signature evoo", "organic olive oil"]
    },
    {
        "name": "Rolled Oats",
        "category": "Pantry",
        "standard_unit": "lb",
        "shelf_life": 180,
        "is_bulk": True,
        "aliases": ["oats", "oatmeal", "old fashioned oats", "quaker oats"]
    },
    {
        "name": "Black Beans",
        "category": "Pantry",
        "standard_unit": "can",
        "shelf_life": 730,
        "is_bulk": False,
        "aliases": ["canned black beans", "organic black beans", "black beans 15oz"]
    },
    {
        "name": "Marinara Pasta Sauce",
        "category": "Pantry",
        "standard_unit": "jar",
        "shelf_life": 180,
        "is_bulk": False,
        "aliases": ["pasta sauce", "tomato sauce", "raos marinara", "marinara sauce"]
    },
    {
        "name": "Penne Pasta",
        "category": "Pantry",
        "standard_unit": "lb",
        "shelf_life": 365,
        "is_bulk": False,
        "aliases": ["pasta", "penne", "barilla penne", "organic pasta"]
    },

    # Beverages
    {
        "name": "100% Pure Orange Juice",
        "category": "Beverages",
        "standard_unit": "fl_oz",
        "shelf_life": 14,
        "is_bulk": False,
        "aliases": ["oj", "orange juice", "tropicana oj", "simply orange"]
    },
    {
        "name": "Sparkling Water",
        "category": "Beverages",
        "standard_unit": "pack",
        "shelf_life": 180,
        "is_bulk": True,
        "aliases": ["la croix", "spindrift", "bubly", "seltzer", "mineral water"]
    },
    {
        "name": "Medium Roast Ground Coffee",
        "category": "Beverages",
        "standard_unit": "lb",
        "shelf_life": 90,
        "is_bulk": False,
        "aliases": ["coffee", "ground coffee", "peets coffee", "kirkland coffee", "starbucks coffee"]
    },

    # Condiments & Snacks
    {
        "name": "Creamy Peanut Butter",
        "category": "Pantry",
        "standard_unit": "oz",
        "shelf_life": 180,
        "is_bulk": False,
        "aliases": ["peanut butter", "jif peanut butter", "skippy peanut butter", "organic peanut butter"]
    },
    {
        "name": "Tomato Ketchup",
        "category": "Pantry",
        "standard_unit": "oz",
        "shelf_life": 180,
        "is_bulk": False,
        "aliases": ["ketchup", "heinz ketchup", "organic ketchup"]
    },
    {
        "name": "Krackjack Biscuits",
        "category": "Snacks",
        "standard_unit": "g",
        "shelf_life": 180,
        "is_bulk": False,
        "aliases": ["parle krackjack", "krackjack", "parle biscuits", "parle krackjack value pack"]
    }
]


def seed_database(db: Session):
    """Seed canonical items, aliases, and initial household profile if empty."""
    household = db.query(Household).first()
    if not household:
        household = Household(id=1, name="Primary Household", member_count=2, postal_code="94107")
        db.add(household)
        db.commit()

    # Seed or update items
    for item_data in SEED_ITEMS:
        existing = db.query(Item).filter(Item.canonical_name == item_data["name"]).first()
        if not existing:
            item = Item(
                canonical_name=item_data["name"],
                category=item_data["category"],
                standard_unit=item_data["standard_unit"],
                default_shelf_life_days=item_data["shelf_life"],
                is_bulk=item_data["is_bulk"]
            )
            db.add(item)
            db.flush()
            canonical_id = item.id
        else:
            canonical_id = existing.id

        # Add canonical name as alias
        name_alias = item_data["name"].lower()
        if not db.query(ItemAlias).filter(ItemAlias.raw_alias == name_alias).first():
            db.add(ItemAlias(
                canonical_item_id=canonical_id,
                raw_alias=name_alias,
                match_confidence=1.0,
                source="system_seed"
            ))

        # Add secondary aliases
        for alias_str in item_data.get("aliases", []):
            clean_alias = alias_str.lower().strip()
            if clean_alias != name_alias and not db.query(ItemAlias).filter(ItemAlias.raw_alias == clean_alias).first():
                db.add(ItemAlias(
                    canonical_item_id=canonical_id,
                    raw_alias=clean_alias,
                    match_confidence=0.95,
                    source="system_seed"
                ))

    db.commit()
