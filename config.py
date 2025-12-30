"""
Configuration for The Shinmonzen Purchasing Evaluation System
Contains vendor patterns, menu items, and analysis settings.
"""

# =============================================================================
# VENDOR CONFIGURATION - Item patterns for invoice matching
# =============================================================================
VENDOR_CONFIG = {
    'Meat Shop Hirayama': {
        'vendor_patterns': ['ミートショップひら山', 'ひら山', 'Hirayama', 'hirayama'],
        'items': {
            'wagyu_tenderloin': {
                'name': '和牛ヒレ (Wagyu Tenderloin)',
                'name_en': 'Wagyu Tenderloin',
                'name_jp': '和牛ヒレ',
                'patterns': ['和牛ヒレ', '和牛モレ', '和生ヒレ', '和邊ヒレ', 'wagyu', 'tenderloin'],
                'default_unit': 'kg',
                'default_price_per_kg': 12000
            }
        }
    },
    'French F&B Japan': {
        'vendor_patterns': ['フレンチ・エフ・アンド・ビー', 'French F&B', 'french fnb'],
        'items': {
            # SPLIT: Standard/Selection Caviar (excludes Fresh)
            'kaviari_crystal_selection': {
                'name': 'KAVIARI キャビア クリスタル セレクション',
                'name_en': 'KAVIARI Crystal Caviar Selection',
                'name_jp': 'キャビア クリスタル セレクション',
                'patterns': ['クリスタル100g セレクション', 'セレクションJG', 'クリスタル.*セレクション'],
                'exclude_patterns': ['フレッシュ', 'Fresh'],
                'default_unit': '100g',
                'default_price_per_unit': 19500
            },
            # SPLIT: Fresh Caviar (separate item)
            'kaviari_crystal_fresh': {
                'name': 'KAVIARI キャヴィア クリスタル フレッシュ',
                'name_en': 'KAVIARI Crystal Caviar Fresh',
                'name_jp': 'キャヴィア クリスタル フレッシュ',
                'patterns': ['クリスタル フレッシュ', 'クリスタル.*フレッシュ', 'キャヴィア.*フレッシュ'],
                'default_unit': '100g',
                'default_price_per_unit': 19500
            },
            'butter_palette': {
                'name': 'パレット ロンド バター',
                'name_en': 'Palette Rond Butter',
                'name_jp': 'パレット ロンド',
                'patterns': ['パレット', 'ﾊﾟﾚｯﾄ', 'バラット', 'ブール', 'ﾛﾝﾄﾞ', 'ﾃﾞﾐｾﾙ'],
                'default_unit': 'pc',
                'default_price_per_unit': 290
            },
            'champagne_vinegar': {
                'name': 'シャンパン ヴィネガー',
                'name_en': 'Champagne Vinegar',
                'name_jp': 'シャンパン ヴィネガー',
                'patterns': ['シャンパン', 'ヴィネガー', 'vinegar', 'champagne'],
                'default_unit': 'pc',
                'default_price_per_unit': 830
            },
            'girolles': {
                'name': '生 ジロール',
                'name_en': 'Fresh Girolles (Chanterelles)',
                'name_jp': '生 ジロール',
                'patterns': ['ジロール', 'girolles', 'ｼﾞﾛｰﾙ'],
                'default_unit': 'kg',
                'default_price_per_unit': 8000
            },
            'small_girolles': {
                'name': '生 スモールジロール',
                'name_en': 'Fresh Small Girolles',
                'name_jp': '生 スモールジロール',
                'patterns': ['スモールジロール', 'ｽﾓｰﾙｼﾞﾛｰﾙ'],
                'default_unit': 'kg',
                'default_price_per_unit': 9000
            },
            'morille': {
                'name': '生 モリーユ',
                'name_en': 'Fresh Morels',
                'name_jp': '生 モリーユ',
                'patterns': ['モリーユ', 'morel', 'ﾓﾘｰﾕ'],
                'default_unit': 'kg',
                'default_price_per_unit': 12440
            },
            'winter_truffle': {
                'name': '生 冬のトリュフ',
                'name_en': 'Fresh Winter Truffle',
                'name_jp': '生 冬のトリュフ',
                'patterns': ['冬のトリュフ', 'トリュフ', 'truffle'],
                'default_unit': 'kg',
                'default_price_per_unit': 192
            }
        }
    }
}

# =============================================================================
# MENU ITEM CONFIGURATION - For cost analysis
# =============================================================================
MENU_ITEMS = {
    'beef_tenderloin_dinner': {
        'name': 'Beef Tenderloin',
        'category': 'A la carte',
        'patterns': ['beef tenderloin', 'ビーフ', 'テンダーロイン'],
        'default_price': 5682,
        'ingredient': '和牛ヒレ (Wagyu Tenderloin)',
        'portion_grams': 150
    },
    'egg_toast_caviar': {
        'name': 'Egg Toast Caviar',
        'category': 'A la carte',
        'patterns': ['egg toast caviar', 'キャビア', 'エッグトースト'],
        'default_price': 3247,
        'ingredient': 'KAVIARI キャビア',
        'portion_grams': 10
    }
}

# =============================================================================
# FOOD CATEGORIES - For filtering menu items
# =============================================================================
FOOD_CATEGORIES = [
    'A la carte',
    'Tasting Menu',
    'Lunch',
    'Dessert',
    'Appetizer',
    'Main Course',
    'Side Dish'
]

# Categories to EXCLUDE from food cost analysis (beverages, etc.)
BEVERAGE_CATEGORIES = [
    'Beverage',
    'Wine',
    'Beer',
    'Cocktail',
    'Soft Drink',
    'Coffee',
    'Tea',
    'Spirits',
    'Sake',
    'Non-Alcoholic'
]

# =============================================================================
# A LA CARTE ITEMS - For Menu Engineering analysis
# =============================================================================
# NOTE: Costs are estimates - update with actual invoice data
A_LA_CARTE_ITEMS = {
    'Beef Tenderloin': {'cost': 1800, 'price': 5682},
    'Egg Toast Caviar': {'cost': 1950, 'price': 3247},
    'Snow Crab Dumpling': {'cost': 800, 'price': 2800},
    'Sea Urchin, Black Bread': {'cost': 1200, 'price': 4200},
    'Roasted Amadai': {'cost': 1100, 'price': 4500},
    # Default cost percentage for items not in this list
    'default_cost_pct': 0.30  # 30% food cost assumed
}

# =============================================================================
# YIELD RATES - Default processing yields
# =============================================================================
YIELD_RATES = {
    'beef_tenderloin': 0.65,  # 65% yield after trimming
    'caviar': 1.0,            # 100% yield (no waste)
    'fish': 0.45,             # 45% yield for whole fish
    'vegetables': 0.85,       # 85% yield after prep
    'default': 0.80           # Default 80% yield
}

# =============================================================================
# ANALYSIS THRESHOLDS
# =============================================================================
THRESHOLDS = {
    'waste_ratio_warning': 15,      # % - Show warning if waste exceeds this
    'waste_ratio_critical': 25,     # % - Show critical if waste exceeds this
    'cost_ratio_target': 30,        # % - Target food cost ratio
    'cost_ratio_warning': 35,       # % - Warning threshold
    'cost_ratio_critical': 40,      # % - Critical threshold
    'food_cost_warning': 40,        # % - Warning for tasting menu analysis
}

# =============================================================================
# MENU PRICES - Current selling prices
# =============================================================================
MENU_PRICES = {
    'dinner_tasting': 24000,
    'lunch_tasting': 8500,
    'special_tasting': 32000
}

# =============================================================================
# DISH TO INGREDIENT MAPPING - For forecasting and cost analysis
# =============================================================================
DISH_INGREDIENT_MAP = {
    'Beef Tenderloin': {
        'ingredient': 'Wagyu Tenderloin',
        'portion_grams': 150,
        'selling_price': 5682,
        'estimated_cost_per_serving': 1800
    },
    'Egg Toast Caviar': {
        'ingredient': 'KAVIARI Caviar',
        'portion_grams': 10,
        'selling_price': 3247,
        'estimated_cost_per_serving': 1950
    },
    'Snow Crab Dumpling': {
        'ingredient': 'Snow Crab',
        'portion_grams': 80,
        'selling_price': 2800,
        'estimated_cost_per_serving': 800
    },
    'Sea Urchin, Black Bread': {
        'ingredient': 'Sea Urchin',
        'portion_grams': 30,
        'selling_price': 4200,
        'estimated_cost_per_serving': 1200
    },
    'Roasted Amadai': {
        'ingredient': 'Amadai Fish',
        'portion_grams': 120,
        'selling_price': 4500,
        'estimated_cost_per_serving': 1100
    }
}

# =============================================================================
# FORECAST CONFIGURATION
# =============================================================================
FORECAST_CONFIG = {
    'default_growth_rate': 0.05,  # 5% YoY growth
    'min_data_points': 3,         # Minimum months for forecasting
    'confidence_interval': 0.95,  # 95% confidence
}

# =============================================================================
# SEASONALITY DATA - Historical patterns for forecasting
# =============================================================================
SEASONALITY_FACTORS = {
    # Month: multiplier (1.0 = average)
    1: 0.85,   # January - post-holiday slow
    2: 0.90,   # February
    3: 1.05,   # March - cherry blossom season starts
    4: 1.15,   # April - peak cherry blossom
    5: 1.10,   # May - Golden Week
    6: 0.95,   # June - rainy season
    7: 1.00,   # July
    8: 0.90,   # August - summer heat
    9: 1.00,   # September
    10: 1.10,  # October - autumn tourism
    11: 1.15,  # November - autumn peak
    12: 1.05,  # December - year-end
}
