"""
Configuration for The Shinmonzen Purchasing Evaluation System

This file contains ONLY static configuration that rarely changes:
- Analysis thresholds
- Category definitions
- Seasonality factors
- AI extraction settings

NO PRICES HERE - prices come from database (invoices/sales tables)
NO FUNCTIONS HERE - functions go in utils.py
"""

# =============================================================================
# AI EXTRACTION CONFIGURATION
# =============================================================================
AI_CONFIG = {
    'model': 'claude-sonnet-4-20250514',
    'max_tokens': 8000,
    'temperature': 0,
}

# AI prompt for invoice extraction - edit here instead of in code
AI_INVOICE_PROMPT = """You are an expert at extracting data from Japanese invoices.

Extract ALL line items from this invoice image. Return ONLY valid JSON, no markdown.

Required JSON structure:
{
  "vendor_name": "vendor name from invoice header",
  "invoice_date": "YYYY-MM-DD",
  "items": [
    {
      "date": "YYYY-MM-DD",
      "item_name": "product name in original language",
      "quantity": 1.0,
      "unit": "kg or pc or g or 100g",
      "unit_price": 1000,
      "amount": 1000
    }
  ]
}

Rules:
- Extract EVERY line item, not just the first few
- Keep item names in original Japanese
- Use numeric values (no commas or yen symbols)
- If unit is unclear, use "pc"
- If date is missing on line, use invoice header date
- Return ONLY the JSON object, nothing else"""

# =============================================================================
# ANALYSIS THRESHOLDS
# =============================================================================
THRESHOLDS = {
    'waste_ratio_warning': 15,      # % - Show warning if waste exceeds
    'waste_ratio_critical': 25,     # % - Show critical if waste exceeds
    'cost_ratio_target': 30,        # % - Target food cost ratio
    'cost_ratio_warning': 35,       # % - Warning threshold
    'cost_ratio_critical': 40,      # % - Critical threshold
}

# =============================================================================
# DEFAULT YIELD RATES - For waste analysis
# These are industry standards, not prices
# =============================================================================
YIELD_RATES = {
    'beef_tenderloin': 0.65,  # 65% yield after trimming
    'caviar': 1.0,            # 100% yield (no waste)
    'fish_whole': 0.45,       # 45% yield for whole fish
    'fish_fillet': 0.90,      # 90% yield for fillets
    'vegetables': 0.85,       # 85% yield after prep
    'shellfish': 0.40,        # 40% yield (shells)
    'default': 0.80           # Default 80% yield
}

# =============================================================================
# FOOD CATEGORIES - For filtering and classification
# =============================================================================
FOOD_CATEGORIES = [
    'A la carte',
    'Tasting Menu',
    'Lunch',
    'Dinner',
    'Breakfast',
    'Dessert',
    'Appetizer',
    'Main Course',
    'Side Dish'
]

# Categories to EXCLUDE from food cost analysis
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
# INGREDIENT CATEGORY PATTERNS - For auto-categorization
# Used to classify invoice items into categories
# =============================================================================
INGREDIENT_PATTERNS = {
    'Meat': ['牛', 'ヒレ', 'beef', 'wagyu', '肉', 'duck', '鴨', 'pork', '豚', 'chicken', '鶏'],
    'Seafood': ['キャビア', 'caviar', '魚', 'fish', 'うに', '鮪', '鯛', 'サーモン', 'ホタテ', '蛤', '海老', 'crab', '蟹'],
    'Dairy': ['バター', 'butter', 'チーズ', 'cheese', 'cream', 'クリーム', 'milk', '牛乳', 'yogurt'],
    'Produce': ['ジロール', 'mushroom', 'きのこ', 'truffle', 'トリュフ', '野菜', 'vegetable'],
    'Condiments': ['ヴィネガー', 'vinegar', 'オイル', 'oil', 'sauce', 'ソース', 'salt', '塩'],
}

# =============================================================================
# SEASONALITY FACTORS - For forecasting
# Month: multiplier (1.0 = average)
# Based on Kyoto tourism patterns
# =============================================================================
SEASONALITY_FACTORS = {
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

# =============================================================================
# FORECAST CONFIGURATION
# =============================================================================
FORECAST_CONFIG = {
    'default_growth_rate': 0.05,  # 5% YoY growth assumption
    'min_data_points': 3,         # Minimum months for forecasting
    'confidence_interval': 0.95,  # 95% confidence
}
