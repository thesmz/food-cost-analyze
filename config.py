"""
Configuration for Purchasing Evaluation System
Defines vendor-ingredient-dish mappings, yield percentages, and menu engineering data
"""

# Vendor configuration
# Maps vendor names to their products and related dishes
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

# Dish to ingredient mapping
# Maps menu items to their primary ingredients, expected usage per serving, and yield
DISH_INGREDIENT_MAP = {
    'Beef Tenderloin': {
        'ingredient': '和牛ヒレ',
        'vendor': 'hirayama',
        'usage_per_serving': 150,  # grams (cooked portion) - updated default
        'unit': 'g',
        'yield_percent': 0.65,  # 65% yield after trimming (35% loss from fat, sinew, etc.)
        'selling_price': 5682,  # yen (dinner course allocation)
        'patterns': ['beef tenderloin', 'ビーフ', 'テンダーロイン'],
    },
    'Egg Toast Caviar': {
        'ingredient': 'KAVIARI キャビア',
        'vendor': 'french_fnb',
        'usage_per_serving': 10,  # grams per serving - updated default
        'unit': 'g',
        'yield_percent': 1.0,  # 100% yield (no loss)
        'selling_price': 3247,  # yen (course item estimate)
        'patterns': ['egg toast caviar', 'キャビア', 'エッグトースト'],
    }
}

# Menu item configuration for Menu Engineering analysis
# Includes all tracked menu items with their costs and prices
MENU_ITEMS = {
    'Beef Tenderloin': {
        'category': 'Main / メイン',
        'selling_price': 5682,
        'estimated_food_cost': 2200,  # Based on avg ¥12,000/kg, 180g portion
        'is_signature': True,
    },
    'Egg Toast Caviar': {
        'category': 'Appetizer / 前菜',
        'selling_price': 3247,
        'estimated_food_cost': 2925,  # Based on ¥19,500/100g, 15g portion
        'is_signature': True,
    },
    # Add more menu items as needed for Menu Engineering
}

# Default target ratios for analysis
DEFAULT_TARGETS = {
    'beef': {
        'waste_ratio_target': 15,  # Maximum acceptable waste % (after accounting for yield)
        'cost_ratio_target': 35,   # Target food cost %
    },
    'caviar': {
        'waste_ratio_target': 10,  # Maximum acceptable waste %
        'cost_ratio_target': 25,   # Target food cost %
    }
}

# Forecasting configuration
FORECAST_CONFIG = {
    'safety_stock_percent': 0.10,  # 10% safety buffer
    'min_history_months': 1,       # Minimum months of data needed
    'default_growth_rate': 0.0,    # Assumed growth rate (0% = flat)
}

# OCR settings
OCR_CONFIG = {
    'languages': 'jpn+eng',
    'dpi': 300,
}
