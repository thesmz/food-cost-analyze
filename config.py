"""
Configuration for Purchasing Evaluation System - The Shinmonzen
Defines vendor-ingredient-dish mappings, yield percentages, and menu recipes
"""

# =============================================================================
# CATEGORY FILTERING - Strict food-only categories
# =============================================================================
FOOD_CATEGORIES = [
    'A la carte',
    'Dinner', 
    'Lunch',
    'Breakfast',
    'Dessert',
    'Open food',
    'Course'
]

# Categories to explicitly exclude (for reference)
EXCLUDED_CATEGORIES = [
    'Beverage',
    'Open beverage',
    'Wine',
    'Beer',
    'Cocktail',
    'Sake',
    'Spirits',
    'Non-alcoholic',
    'Soft drink'
]

# =============================================================================
# VENDOR CONFIGURATION
# =============================================================================
VENDOR_CONFIG = {
    'hirayama': {
        'names': ['ミートショップひら山', 'Meat Shop Hirayama', 'Hirayama'],
        'products': [
            {
                'name': '和牛ヒレ',
                'name_en': 'Wagyu Tenderloin',
                'unit': 'kg',
                'patterns': ['和牛ヒレ', '和牛モレ', '和生ヒレ', '和邊ヒレ', 'wagyu', 'tenderloin'],
            }
        ]
    },
    'french_fnb': {
        'names': ['フレンチ・エフ・アンド・ビー', 'French F&B Japan', 'French FnB'],
        'products': [
            {
                'name': 'KAVIARI キャビア',
                'name_en': 'Caviar',
                'unit': 'pc (100g)',
                'patterns': ['KAVIARI', 'キャビア', 'キャヴィア', 'caviar', 'クリスタル'],
            },
            {
                'name': 'パレット バター',
                'name_en': 'Butter',
                'unit': 'pc (20g)',
                'patterns': ['パレット', 'ﾊﾟﾚｯﾄ', 'バラット', 'ブール', 'butter'],
            },
            {
                'name': 'シャンパン ヴィネガー',
                'name_en': 'Champagne Vinegar',
                'unit': 'bottle (500ml)',
                'patterns': ['シャンパン', 'ヴィネガー', 'vinegar', 'champagne'],
            },
            {
                'name': 'ジロール',
                'name_en': 'Girolles Mushroom',
                'unit': 'kg',
                'patterns': ['ジロール', 'girolles', 'mushroom'],
            }
        ]
    }
}

# =============================================================================
# DISH TO INGREDIENT MAPPING (with Yield Percentages)
# =============================================================================
DISH_INGREDIENT_MAP = {
    'Beef Tenderloin': {
        'ingredient': '和牛ヒレ',
        'ingredient_en': 'Wagyu Beef Tenderloin',
        'vendor': 'hirayama',
        'usage_per_serving': 150,  # grams (cooked portion)
        'unit': 'g',
        'yield_percent': 0.65,  # 65% yield after trimming (35% loss)
        'selling_price': 5682,  # yen (dinner course allocation)
        'estimated_cost_per_serving': 2769,  # yen (based on avg ¥12,000/kg raw)
        'patterns': ['beef tenderloin', 'ビーフ', 'テンダーロイン'],
    },
    'Egg Toast Caviar': {
        'ingredient': 'KAVIARI キャビア',
        'ingredient_en': 'Caviar',
        'vendor': 'french_fnb',
        'usage_per_serving': 10,  # grams per serving
        'unit': 'g',
        'yield_percent': 1.0,  # 100% yield (no loss)
        'selling_price': 3247,  # yen (course item estimate)
        'estimated_cost_per_serving': 1950,  # yen (based on ¥19,500/100g)
        'patterns': ['egg toast caviar', 'キャビア', 'エッグトースト'],
    },
    'Foie Gras': {
        'ingredient': 'フォアグラ',
        'ingredient_en': 'Foie Gras',
        'vendor': 'french_fnb',
        'usage_per_serving': 80,  # grams
        'unit': 'g',
        'yield_percent': 0.85,  # 85% yield
        'selling_price': 4500,
        'estimated_cost_per_serving': 1600,
        'patterns': ['foie gras', 'フォアグラ'],
    },
    'Wagyu A5 Ribeye': {
        'ingredient': '和牛リブロース',
        'ingredient_en': 'Wagyu A5 Ribeye',
        'vendor': 'hirayama',
        'usage_per_serving': 120,  # grams
        'unit': 'g',
        'yield_percent': 0.75,  # 75% yield
        'selling_price': 8500,
        'estimated_cost_per_serving': 3200,
        'patterns': ['ribeye', 'リブロース', 'a5'],
    }
}

# =============================================================================
# TASTING MENU RECIPES - Components and costs for each course menu
# =============================================================================
TASTING_MENU_RECIPES = {
    'Autumn Tasting Menu': {
        'menu_name_jp': '秋のテイスティングメニュー',
        'selling_price': 28000,  # yen per person
        'courses': [
            {
                'course_number': 1,
                'name': 'Amuse-bouche',
                'name_jp': 'アミューズ',
                'description': 'Seasonal vegetables with dashi gelée',
                'estimated_food_cost': 350,
                'key_ingredients': ['Seasonal vegetables', 'Dashi'],
            },
            {
                'course_number': 2,
                'name': 'Egg Toast Caviar',
                'name_jp': 'エッグトーストキャビア',
                'description': 'Soft scrambled egg with Kaviari caviar on brioche',
                'estimated_food_cost': 1950,
                'key_ingredients': ['Caviar (10g)', 'Eggs', 'Brioche'],
                'linked_dish': 'Egg Toast Caviar',
            },
            {
                'course_number': 3,
                'name': 'Seasonal Soup',
                'name_jp': '季節のスープ',
                'description': 'Pumpkin velouté with truffle oil',
                'estimated_food_cost': 450,
                'key_ingredients': ['Pumpkin', 'Cream', 'Truffle oil'],
            },
            {
                'course_number': 4,
                'name': 'Fish Course',
                'name_jp': '魚料理',
                'description': 'Seared amadai with autumn mushrooms',
                'estimated_food_cost': 1800,
                'key_ingredients': ['Amadai fish', 'Girolles', 'Seasonal mushrooms'],
            },
            {
                'course_number': 5,
                'name': 'Beef Tenderloin',
                'name_jp': '和牛ヒレ',
                'description': 'Grilled Wagyu tenderloin with red wine jus',
                'estimated_food_cost': 2769,
                'key_ingredients': ['Wagyu tenderloin (150g)', 'Red wine', 'Seasonal vegetables'],
                'linked_dish': 'Beef Tenderloin',
            },
            {
                'course_number': 6,
                'name': 'Pre-dessert',
                'name_jp': 'プレデザート',
                'description': 'Yuzu sorbet',
                'estimated_food_cost': 200,
                'key_ingredients': ['Yuzu', 'Sugar'],
            },
            {
                'course_number': 7,
                'name': 'Dessert',
                'name_jp': 'デザート',
                'description': 'Chestnut mont blanc with vanilla ice cream',
                'estimated_food_cost': 650,
                'key_ingredients': ['Chestnuts', 'Cream', 'Vanilla'],
            },
            {
                'course_number': 8,
                'name': 'Petit Fours',
                'name_jp': 'プティフール',
                'description': 'Assorted mignardises',
                'estimated_food_cost': 280,
                'key_ingredients': ['Chocolate', 'Fruits', 'Nuts'],
            },
        ],
        'total_estimated_cost': 8449,  # Sum of all courses
        'target_food_cost_percent': 30,  # Target 30%
    },
    'Winter Tasting Menu': {
        'menu_name_jp': '冬のテイスティングメニュー',
        'selling_price': 32000,
        'courses': [
            {
                'course_number': 1,
                'name': 'Amuse-bouche',
                'name_jp': 'アミューズ',
                'description': 'Oyster with champagne foam',
                'estimated_food_cost': 580,
                'key_ingredients': ['Oyster', 'Champagne'],
            },
            {
                'course_number': 2,
                'name': 'Foie Gras Terrine',
                'name_jp': 'フォアグラテリーヌ',
                'description': 'Foie gras with fig compote',
                'estimated_food_cost': 1600,
                'key_ingredients': ['Foie gras (80g)', 'Figs', 'Brioche'],
                'linked_dish': 'Foie Gras',
            },
            {
                'course_number': 3,
                'name': 'Truffle Soup',
                'name_jp': 'トリュフスープ',
                'description': 'Black truffle consommé',
                'estimated_food_cost': 1200,
                'key_ingredients': ['Black truffle', 'Consommé'],
            },
            {
                'course_number': 4,
                'name': 'Lobster',
                'name_jp': 'オマール海老',
                'description': 'Poached lobster with beurre blanc',
                'estimated_food_cost': 2800,
                'key_ingredients': ['Lobster', 'Butter', 'White wine'],
            },
            {
                'course_number': 5,
                'name': 'Wagyu A5 Ribeye',
                'name_jp': '和牛A5リブロース',
                'description': 'Grilled A5 ribeye with winter vegetables',
                'estimated_food_cost': 3200,
                'key_ingredients': ['Wagyu A5 ribeye (120g)', 'Root vegetables'],
                'linked_dish': 'Wagyu A5 Ribeye',
            },
            {
                'course_number': 6,
                'name': 'Cheese Course',
                'name_jp': 'チーズ',
                'description': 'Selection of aged cheeses',
                'estimated_food_cost': 450,
                'key_ingredients': ['Aged cheeses', 'Honey', 'Nuts'],
            },
            {
                'course_number': 7,
                'name': 'Dessert',
                'name_jp': 'デザート',
                'description': 'Chocolate fondant with gold leaf',
                'estimated_food_cost': 750,
                'key_ingredients': ['Valrhona chocolate', 'Gold leaf'],
            },
            {
                'course_number': 8,
                'name': 'Petit Fours',
                'name_jp': 'プティフール',
                'description': 'Assorted mignardises',
                'estimated_food_cost': 300,
                'key_ingredients': ['Chocolate', 'Macarons'],
            },
        ],
        'total_estimated_cost': 10880,
        'target_food_cost_percent': 34,
    },
    'Lunch Course': {
        'menu_name_jp': 'ランチコース',
        'selling_price': 12000,
        'courses': [
            {
                'course_number': 1,
                'name': 'Appetizer',
                'name_jp': '前菜',
                'description': 'Seasonal appetizer',
                'estimated_food_cost': 400,
                'key_ingredients': ['Seasonal ingredients'],
            },
            {
                'course_number': 2,
                'name': 'Soup',
                'name_jp': 'スープ',
                'description': 'Daily soup',
                'estimated_food_cost': 250,
                'key_ingredients': ['Vegetables', 'Stock'],
            },
            {
                'course_number': 3,
                'name': 'Fish or Meat',
                'name_jp': '魚または肉',
                'description': 'Choice of fish or meat main',
                'estimated_food_cost': 1500,
                'key_ingredients': ['Fish/Meat', 'Vegetables'],
            },
            {
                'course_number': 4,
                'name': 'Dessert',
                'name_jp': 'デザート',
                'description': 'Daily dessert',
                'estimated_food_cost': 350,
                'key_ingredients': ['Seasonal fruits', 'Cream'],
            },
        ],
        'total_estimated_cost': 2500,
        'target_food_cost_percent': 21,
    },
}

# =============================================================================
# A LA CARTE MENU ITEMS - For Menu Engineering Analysis
# =============================================================================
A_LA_CARTE_ITEMS = {
    'Beef Tenderloin': {
        'category': 'A la carte',
        'selling_price': 8500,
        'estimated_food_cost': 2769,
        'is_signature': True,
    },
    'Egg Toast Caviar': {
        'category': 'A la carte',
        'selling_price': 4800,
        'estimated_food_cost': 1950,
        'is_signature': True,
    },
    'Foie Gras Terrine': {
        'category': 'A la carte',
        'selling_price': 3800,
        'estimated_food_cost': 1600,
        'is_signature': False,
    },
    'Wagyu Tartare': {
        'category': 'A la carte',
        'selling_price': 4200,
        'estimated_food_cost': 1400,
        'is_signature': False,
    },
    'Seasonal Salad': {
        'category': 'A la carte',
        'selling_price': 1800,
        'estimated_food_cost': 350,
        'is_signature': False,
    },
    'Truffle Fries': {
        'category': 'A la carte',
        'selling_price': 1500,
        'estimated_food_cost': 280,
        'is_signature': False,
    },
}

# =============================================================================
# DEFAULT TARGETS AND THRESHOLDS
# =============================================================================
DEFAULT_TARGETS = {
    'beef': {
        'waste_ratio_target': 15,  # Maximum acceptable waste %
        'cost_ratio_target': 35,   # Target food cost %
    },
    'caviar': {
        'waste_ratio_target': 10,  # Maximum acceptable waste %
        'cost_ratio_target': 25,   # Target food cost %
    }
}

# Food cost warning threshold
FOOD_COST_WARNING_THRESHOLD = 40  # Warn if food cost % > 40%

# =============================================================================
# SEASONALITY DATA - Historical patterns for forecasting
# =============================================================================
SEASONALITY_FACTORS = {
    # Month: factor relative to average (1.0 = average)
    1: 0.85,   # January - post-holiday slow
    2: 0.80,   # February - slow season
    3: 0.90,   # March - picking up
    4: 1.05,   # April - cherry blossom season
    5: 1.10,   # May - Golden Week
    6: 0.95,   # June - rainy season
    7: 1.00,   # July - summer
    8: 0.90,   # August - Obon holidays
    9: 1.00,   # September - autumn begins
    10: 1.15,  # October - peak autumn
    11: 1.20,  # November - peak season (leaves)
    12: 1.10,  # December - year-end parties
}

# =============================================================================
# FORECAST CONFIGURATION
# =============================================================================
FORECAST_CONFIG = {
    'default_growth_rate': 0.0,  # Default YoY growth assumption
    'safety_stock_percent': 0.10,  # 10% safety buffer
    'min_order_buffer': 0.05,  # 5% minimum buffer
}

# =============================================================================
# OCR SETTINGS
# =============================================================================
OCR_CONFIG = {
    'languages': 'jpn+eng',
    'dpi': 300,
}
