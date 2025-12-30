"""
Configuration for The Shinmonzen Purchasing Evaluation System
Contains vendor patterns, menu items, and analysis settings.
"""

# =============================================================================
# VENDOR NAME MAPPING - Japanese to Clean English Names
# =============================================================================
VENDOR_NAME_MAP = {
    # Meat & Fish
    'ミートショップひら山': 'Meat Shop Hirayama',
    'ひら山': 'Meat Shop Hirayama',
    '株式会社 丸弥太': 'Maruyata',
    '丸弥太': 'Maruyata',
    '有限会社浅見水産': 'Asami Suisan',
    '浅見水産': 'Asami Suisan',
    '洛北ジビエ イマイ': 'Gibier Imai',
    
    # Dairy & Cheese
    '新利根チーズ工房': 'Cheese Kobo',
    'タカナシ販売株式会社': 'Takanashi',
    '有限会社レチェール・ユゲ': 'Yuge Farm',
    
    # Produce & Vegetables
    '株式会社ポモナファーム': 'Pomona Farm',
    '株式会社ミナト　青果事業部': 'Minato Seika',
    '株式会社ミナト': 'Minato',
    '万松青果株式会社': 'Manmatsu',
    
    # Specialty Foods
    'フレンチ・エフ・アンド・ビー': 'French F&B Japan',
    'French F&B': 'French F&B Japan',
    '株式会社 LIBERTE JAPON': 'Liberte Japon',
    'LIBERTE JAPON': 'Liberte Japon',
    '株式会社 有徳島庄蔵卸月浦明堂': 'Nezu Matsumoto',
    'ＡＳＩＡＭＩＸ株式会社': 'Asiamix',
    
    # Rice & Bread
    '株式会社八代目儀兵衛': 'Hachidaime Gihei',
    '株式会社進々堂': 'Shinshindo',
    
    # Meat (Premium)
    '株式会社銀閣寺大西': 'Ginkakuji Onishi',
    
    # Other Suppliers
    '池伝株式会社　大阪支店': 'Ikeden',
    '池伝株式会社': 'Ikeden',
    'ＷＩＳＫジャパン株式会社': 'WISK Japan',
}

def get_clean_vendor_name(vendor_name: str) -> str:
    """Convert Japanese vendor name to clean English name"""
    if not vendor_name:
        return 'Unknown'
    
    # Direct lookup
    if vendor_name in VENDOR_NAME_MAP:
        return VENDOR_NAME_MAP[vendor_name]
    
    # Partial match - check if any key is contained in the vendor name
    for jp_name, en_name in VENDOR_NAME_MAP.items():
        if jp_name in vendor_name or vendor_name in jp_name:
            return en_name
    
    # If already looks like English, return as-is
    if all(ord(c) < 128 or c in ' ・' for c in vendor_name[:10]):
        return vendor_name
    
    return vendor_name  # Return original if no match


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
# NOTE: Costs should be calculated from actual recipes, not hardcoded!
# The Menu Engineering page now uses:
# 1. User-adjustable default percentage (slider)
# 2. Custom costs entered by user for specific items
# NO FAKE HARDCODED VALUES HERE
A_LA_CARTE_ITEMS = {
    # Empty - costs are calculated dynamically or entered by user
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
