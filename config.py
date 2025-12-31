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
# COURSE PRICING - For estimating revenue of course items
# Items with price=0 belong to prix fixe courses
# =============================================================================
COURSE_PRICING = {
    # Dinner Tasting Menu: ¥19,480 for 7 dishes
    'dinner': {
        'course_price': 19480,
        'num_dishes': 7,
        'per_dish': 2783,  # 19480 / 7
    },
    # Lunch Course: ¥6,900 for 4 dishes  
    'lunch': {
        'course_price': 6900,
        'num_dishes': 4,
        'per_dish': 1725,  # 6900 / 4
    },
    # Dessert: same for both lunch and dinner
    'dessert': {
        'per_dish': 1725,
    },
    # Beef Tenderloin supplement (added to base course price)
    'beef_supplement': 5682,
}

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
# YIELD RATES - Processing yields for ingredients
# 
# YIELD CALCULATION FLOW (from PURCHASED RAW to COOKED):
#   1. Purchase RAW (e.g., 100kg whole tenderloin)
#   2. Butchery/Trimming → RAW × Butchery Yield = TRIMMED (ready to cook)
#   3. Cooking → TRIMMED × Cooking Yield = COOKED (ready to serve)
#   4. Total Yield = Butchery × Cooking
#
# Example: 100kg raw beef @ 65% butchery, 80% cooking
#   → 100 × 0.65 = 65kg trimmed (ready to cook)
#   → 65 × 0.80 = 52kg cooked (ready to serve)
#   → Total: 52% of raw becomes servable
#
# WASTE ANALYSIS:
#   - Purchased: from invoices (RAW)
#   - Expected Trimmed: Purchased × Butchery Yield
#   - Expected Cooked: Trimmed × Cooking Yield
#   - Needed for Sales: Sales Qty × Portion Size
#   - Variance: Expected Cooked - Needed
# =============================================================================
YIELD_RATES = {
    # Beef Tenderloin (Wagyu)
    # - Butchery: 65% (remove silverskin, fat cap, chain, head/tail)
    # - Cooking: 80% (moisture/fat loss at medium-rare)
    # - Total: 0.65 × 0.80 = 0.52
    'beef_tenderloin': {
        'butchery': 0.65,
        'cooking': 0.80,
        'total': 0.52,
    },
    
    # Caviar - no processing loss
    'caviar': {
        'butchery': 1.0,
        'cooking': 1.0,
        'total': 1.0,
    },
    
    # Whole Fish (e.g., Sea Bream, Amadai)
    # - Butchery: 45% (head, bones, skin, scales, guts)
    # - Cooking: 85% (moisture loss)
    # - Total: 0.45 × 0.85 = 0.38
    'fish_whole': {
        'butchery': 0.45,
        'cooking': 0.85,
        'total': 0.38,
    },
    
    # Fish Fillet (pre-portioned)
    # - Butchery: 95% (minimal trim)
    # - Cooking: 85% (moisture loss)
    # - Total: 0.95 × 0.85 = 0.81
    'fish_fillet': {
        'butchery': 0.95,
        'cooking': 0.85,
        'total': 0.81,
    },
    
    # Shellfish (lobster, crab)
    # - Butchery: 40% (shells)
    # - Cooking: 90% (minimal loss)
    # - Total: 0.40 × 0.90 = 0.36
    'shellfish': {
        'butchery': 0.40,
        'cooking': 0.90,
        'total': 0.36,
    },
    
    # Vegetables
    # - Butchery: 85% (peel, stems, cores)
    # - Cooking: 90% (some moisture loss)
    # - Total: 0.85 × 0.90 = 0.77
    'vegetables': {
        'butchery': 0.85,
        'cooking': 0.90,
        'total': 0.77,
    },
    
    # Default (conservative estimate)
    'default': {
        'butchery': 0.75,
        'cooking': 0.85,
        'total': 0.64,
    },
}


def get_yield_rates(category: str) -> dict:
    """Get butchery, cooking, and total yield for a category."""
    if category in YIELD_RATES:
        return YIELD_RATES[category]
    return YIELD_RATES['default']


def get_total_yield(category: str) -> float:
    """Get total yield (raw → cooked) for an ingredient category."""
    rates = get_yield_rates(category)
    return rates.get('total', 0.52)


def get_butchery_yield(category: str) -> float:
    """Get butchery/trimming yield (raw → trimmed)."""
    rates = get_yield_rates(category)
    return rates.get('butchery', 0.65)


def get_cooking_yield(category: str) -> float:
    """Get cooking yield (trimmed → cooked)."""
    rates = get_yield_rates(category)
    return rates.get('cooking', 0.80)

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
