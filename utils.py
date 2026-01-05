"""
Utility Functions for The Shinmonzen Purchasing Evaluation System

This file contains helper functions used across the application.
Data/configuration goes in config.py and vendors.py
"""

import pandas as pd
from vendors import VENDOR_NAME_MAP, ITEM_PATTERNS
from config import INGREDIENT_PATTERNS


# =============================================================================
# SHIPPING FEE / NON-FOOD ITEM DETECTION
# =============================================================================
SHIPPING_FEE_PATTERNS = [
    # Shipping/Delivery
    '送料', '運賃', '配送料', '運送料', '宅配料', '発送料',
    'shipping', 'delivery', 'freight', 'postage',
    'クール便', 'チルド便', '冷凍便', '冷蔵便',
    'クール代', 'クール料金',
    '宅配運賃',
    # Payment/Banking terms (not food!)
    '入金', '振込', '振り込み', '支払', '決済',
    '請求', '調整', '値引', '割引', '返金',
    'payment', 'transfer', 'credit', 'refund',
    # Administrative
    '手数料', '事務', '管理費',
]

def is_shipping_fee(item_name: str) -> bool:
    """
    Check if an item is a shipping/delivery fee (not actual food).
    
    Args:
        item_name: Name of the item from invoice
    
    Returns:
        True if item is a shipping fee, False otherwise
    """
    if not item_name:
        return False
    
    item_lower = str(item_name).lower().strip()
    
    for pattern in SHIPPING_FEE_PATTERNS:
        if pattern.lower() in item_lower:
            return True
    
    return False


def filter_shipping_fees(df: pd.DataFrame, item_column: str = 'item_name') -> pd.DataFrame:
    """
    Remove shipping fee items from a DataFrame.
    
    Args:
        df: DataFrame containing invoice/item data
        item_column: Name of the column containing item names
    
    Returns:
        DataFrame with shipping fees removed
    """
    if df.empty or item_column not in df.columns:
        return df
    
    mask = ~df[item_column].apply(is_shipping_fee)
    return df[mask].copy()


def get_clean_vendor_name(vendor_name: str) -> str:
    """
    Convert Japanese vendor name to clean English display name.
    
    Args:
        vendor_name: Raw vendor name from invoice (may be Japanese)
    
    Returns:
        Clean English vendor name for display
    """
    if not vendor_name:
        return 'Unknown'
    
    vendor_name = str(vendor_name).strip()
    
    # Direct lookup
    if vendor_name in VENDOR_NAME_MAP:
        return VENDOR_NAME_MAP[vendor_name]
    
    # Partial match - check if any key is contained in the vendor name
    for jp_name, en_name in VENDOR_NAME_MAP.items():
        if jp_name in vendor_name or vendor_name in jp_name:
            return en_name
    
    # If already looks like English (ASCII), return as-is
    if all(ord(c) < 128 or c in ' ・-_' for c in vendor_name[:10]):
        return vendor_name
    
    # Return original if no match found
    return vendor_name


def get_ingredient_category(item_name: str) -> str:
    """
    Determine ingredient category based on item name patterns.
    
    Args:
        item_name: Name of the ingredient from invoice
    
    Returns:
        Category name (Meat, Seafood, Dairy, Produce, Condiments, or Other)
    """
    if not item_name:
        return 'Other'
    
    item_lower = str(item_name).lower()
    
    for category, patterns in INGREDIENT_PATTERNS.items():
        if any(pattern.lower() in item_lower for pattern in patterns):
            return category
    
    return 'Other'


def normalize_unit(unit: str) -> str:
    """
    Normalize unit strings for consistent display.
    
    Args:
        unit: Raw unit from invoice (may be Japanese)
    
    Returns:
        Normalized unit string
    """
    if not unit:
        return 'pc'
    
    unit = str(unit).strip().lower()
    
    # Common unit mappings (Japanese and English variations)
    unit_map = {
        # Weight units
        'キログラム': 'kg',
        'kilo': 'kg',
        'kilogram': 'kg',
        'kg': 'kg',
        'グラム': 'g',
        'gram': 'g',
        'grams': 'g',
        'g': 'g',
        '100g': '100g',
        '100グラム': '100g',
        
        # Piece/count units
        '個': 'pc',
        '本': 'pc',
        '丁': 'pc',
        '枚': 'pc',
        '尾': 'pc',
        '匹': 'pc',
        'pc': 'pc',
        'pcs': 'pc',
        'piece': 'pc',
        'pieces': 'pc',
        'unit': 'pc',
        'units': 'pc',
        'ea': 'pc',
        'each': 'pc',
        
        # Container units
        '缶': 'can',
        'can': 'can',
        'cans': 'can',
        'tin': 'can',
        'tins': 'can',
        '箱': 'box',
        'box': 'box',
        'boxes': 'box',
        'パック': 'pack',
        'pack': 'pack',
        'packs': 'pack',
        'pkg': 'pack',
        'package': 'pack',
        'bottle': 'bottle',
        'bottles': 'bottle',
        'jar': 'jar',
        'jars': 'jar',
        'bag': 'bag',
        'bags': 'bag',
    }
    
    return unit_map.get(unit, unit)


def format_currency(amount: float, currency: str = '¥') -> str:
    """
    Format amount as currency string.
    
    Args:
        amount: Numeric amount
        currency: Currency symbol (default ¥)
    
    Returns:
        Formatted string like "¥12,000"
    """
    if amount is None:
        return f"{currency}0"
    
    return f"{currency}{amount:,.0f}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """
    Format value as percentage string.
    
    Args:
        value: Numeric value (0.30 for 30%)
        decimals: Number of decimal places
    
    Returns:
        Formatted string like "30.0%"
    """
    if value is None:
        return "0%"
    
    return f"{value * 100:.{decimals}f}%"


def detect_vendor_from_text(text: str, filename: str = '') -> str:
    """
    Detect vendor name from invoice text or filename.
    
    Args:
        text: Extracted text from invoice
        filename: Invoice filename
    
    Returns:
        Detected vendor name or None
    """
    from vendors import VENDOR_PATTERNS
    
    combined = (text + ' ' + filename).lower()
    
    for vendor_name, patterns in VENDOR_PATTERNS.items():
        for pattern in patterns:
            if pattern.lower() in combined:
                return vendor_name
    
    return None


# =============================================================================
# YIELD CALCULATION HELPERS
# 
# YIELD FLOW (from PURCHASED to SERVED):
#   PURCHASED (raw) → BUTCHERY → TRIMMED → COOKING → COOKED (served)
#   
#   Example: 100kg raw @ 65% butchery, 80% cooking
#     → 100 × 0.65 = 65kg trimmed
#     → 65 × 0.80 = 52kg cooked
# =============================================================================

def get_yield_rate(item_name: str, category: str = None, yield_type: str = 'total') -> float:
    """
    Get yield rate for an ingredient.
    
    YIELD has TWO stages:
    1. BUTCHERY: raw → trimmed (removing fat, bones, skin)
    2. COOKING: trimmed → cooked (moisture loss, fat rendering)
    
    TOTAL yield = butchery × cooking
    
    Args:
        item_name: Name of ingredient
        category: Category (Meat, Seafood, etc.)
        yield_type: 'total', 'butchery', or 'cooking'
    
    Returns:
        Yield rate as decimal (e.g., 0.65 for 65%)
    """
    try:
        from config import YIELD_RATES
    except ImportError:
        return 0.65  # Fallback
    
    item_lower = str(item_name).lower() if item_name else ''
    
    # Determine yield category from item name
    yield_category = 'default'
    
    if any(x in item_lower for x in ['beef', 'tenderloin', 'wagyu', 'ヒレ', '牛']):
        yield_category = 'beef_tenderloin'
    elif any(x in item_lower for x in ['caviar', 'キャビア']):
        yield_category = 'caviar'
    elif any(x in item_lower for x in ['whole fish', '丸', '尾']):
        yield_category = 'fish_whole'
    elif any(x in item_lower for x in ['fillet', 'フィレ', '切身']):
        yield_category = 'fish_fillet'
    elif any(x in item_lower for x in ['lobster', 'crab', 'shrimp', '海老', '蟹', 'ロブスター']):
        yield_category = 'shellfish'
    elif any(x in item_lower for x in ['vegetable', 'salad', '野菜']):
        yield_category = 'vegetables'
    elif category == 'Seafood':
        yield_category = 'fish_fillet'  # Default for seafood
    elif category == 'Meat':
        yield_category = 'beef_tenderloin'  # Default for meat
    
    # Get yield rate
    rate_data = YIELD_RATES.get(yield_category, YIELD_RATES['default'])
    
    if isinstance(rate_data, dict):
        return rate_data.get(yield_type, rate_data.get('total', 0.52))
    else:
        return rate_data  # Old format - just a number


def calculate_yield_from_raw(raw_kg: float, butchery_yield: float, cooking_yield: float) -> dict:
    """
    Calculate cooked output from raw purchase.
    
    Flow: RAW → (butchery) → TRIMMED → (cooking) → COOKED
    
    Args:
        raw_kg: Raw purchased amount in kg
        butchery_yield: Butchery yield as decimal (e.g., 0.65)
        cooking_yield: Cooking yield as decimal (e.g., 0.80)
    
    Returns:
        Dict with: raw_kg, trimmed_kg, cooked_kg, total_yield
    """
    trimmed_kg = raw_kg * butchery_yield
    cooked_kg = trimmed_kg * cooking_yield
    total_yield = butchery_yield * cooking_yield
    
    return {
        'raw_kg': raw_kg,
        'trimmed_kg': trimmed_kg,
        'cooked_kg': cooked_kg,
        'butchery_yield': butchery_yield,
        'cooking_yield': cooking_yield,
        'total_yield': total_yield,
        'butchery_loss_kg': raw_kg - trimmed_kg,
        'cooking_loss_kg': trimmed_kg - cooked_kg,
        'total_loss_kg': raw_kg - cooked_kg,
    }


def calculate_raw_needed(cooked_portion: float, item_name: str = '', category: str = '') -> dict:
    """
    Calculate how much RAW ingredient is needed for a given COOKED portion.
    
    Shows the full breakdown: cooked → trimmed → raw
    
    Args:
        cooked_portion: Grams of cooked/plated product needed
        item_name: Name of ingredient
        category: Category (Meat, Seafood, etc.)
    
    Returns:
        Dict with breakdown
    """
    butchery_yield = get_yield_rate(item_name, category, 'butchery')
    cooking_yield = get_yield_rate(item_name, category, 'cooking')
    total_yield = butchery_yield * cooking_yield
    
    # Work backwards: cooked → trimmed → raw
    trimmed_g = cooked_portion / cooking_yield if cooking_yield > 0 else cooked_portion
    raw_g = trimmed_g / butchery_yield if butchery_yield > 0 else trimmed_g
    
    return {
        'cooked_g': cooked_portion,
        'trimmed_g': trimmed_g,
        'raw_g': raw_g,
        'butchery_yield': butchery_yield,
        'cooking_yield': cooking_yield,
        'total_yield': total_yield
    }


def calculate_cost_for_portion(
    cooked_portion: float,
    cost_per_raw_unit: float,
    raw_unit: str,
    item_name: str = '',
    category: str = ''
) -> dict:
    """
    Calculate the TRUE cost for a cooked portion, accounting for all yield losses.
    
    Args:
        cooked_portion: Grams of cooked/plated product
        cost_per_raw_unit: Cost per unit of raw ingredient (e.g., ¥12,000/kg)
        raw_unit: Unit of the raw cost ('kg', 'g', '100g', 'pc')
        item_name: Ingredient name
        category: Category
    
    Returns:
        Dict with cost breakdown
    """
    # Convert cost to per-gram
    if raw_unit == 'kg':
        cost_per_gram = cost_per_raw_unit / 1000
    elif raw_unit == '100g':
        cost_per_gram = cost_per_raw_unit / 100
    elif raw_unit == 'g':
        cost_per_gram = cost_per_raw_unit
    else:
        # For 'pc' and other units, assume cost is per piece
        cost_per_gram = cost_per_raw_unit
    
    # Calculate raw needed
    breakdown = calculate_raw_needed(cooked_portion, item_name, category)
    raw_g = breakdown['raw_g']
    
    # Calculate costs
    raw_cost = raw_g * cost_per_gram
    
    return {
        **breakdown,
        'cost_per_raw_gram': cost_per_gram,
        'raw_cost': round(raw_cost, 0),
        'cost_per_cooked_gram': round(raw_cost / cooked_portion, 2) if cooked_portion > 0 else 0,
    }


# =============================================================================
# YIELD RATE HELPERS - Centralized for consistency
# =============================================================================

def get_default_yield_for_item(item_name: str, category: str = '') -> int:
    """
    Get default yield percentage based on item name and category.
    Used across all pages for consistency.
    
    Yield = Usable output / Raw input
    - 65% yield means 1kg raw → 650g usable
    
    Args:
        item_name: Name of ingredient
        category: Optional category hint
    
    Returns:
        Yield percentage as integer (e.g., 65 for 65%)
    """
    try:
        from config import YIELD_RATES
    except ImportError:
        YIELD_RATES = {'default': 0.80}
    
    item_lower = str(item_name).lower() if item_name else ''
    category_lower = str(category).lower() if category else ''
    
    # Check by specific ingredient patterns (most specific first)
    if any(x in item_lower for x in ['beef tenderloin', 'wagyu', 'ヒレ', '和牛']):
        return int(YIELD_RATES.get('beef_tenderloin', 0.65) * 100)
    
    if any(x in item_lower for x in ['caviar', 'キャビア']):
        return int(YIELD_RATES.get('caviar', 1.0) * 100)
    
    # Fish - check if fillet or whole
    if any(x in item_lower for x in ['fillet', 'サク', '切り身']):
        return int(YIELD_RATES.get('fish_fillet', 0.90) * 100)
    if any(x in item_lower for x in ['whole', '丸', '姿']):
        return int(YIELD_RATES.get('fish_whole', 0.45) * 100)
    if any(x in item_lower for x in ['fish', '魚', '鮪', '鯛', 'サーモン', 'amadai', '甘鯛']):
        # Default fish to fillet (more common in fine dining)
        return int(YIELD_RATES.get('fish_fillet', 0.90) * 100)
    
    # Shellfish
    if any(x in item_lower for x in ['うに', 'uni', 'sea urchin', '蛤', 'clam', '海老', 'shrimp', 'lobster', 'crab']):
        return int(YIELD_RATES.get('shellfish', 0.40) * 100)
    
    # Other meats
    if any(x in item_lower for x in ['duck', '鴨', 'pork', '豚', 'lamb', 'chicken']):
        return int(YIELD_RATES.get('beef_tenderloin', 0.65) * 100)
    
    # Produce
    if any(x in item_lower for x in ['vegetable', '野菜', 'mushroom', 'きのこ', 'truffle']):
        return int(YIELD_RATES.get('vegetables', 0.85) * 100)
    
    # Check by category
    if category_lower:
        if 'meat' in category_lower:
            return int(YIELD_RATES.get('beef_tenderloin', 0.65) * 100)
        if 'seafood' in category_lower:
            return int(YIELD_RATES.get('fish_fillet', 0.90) * 100)
        if 'produce' in category_lower:
            return int(YIELD_RATES.get('vegetables', 0.85) * 100)
        if 'dairy' in category_lower or 'condiment' in category_lower:
            return 100  # No waste
    
    return int(YIELD_RATES.get('default', 0.80) * 100)


def calculate_raw_from_usable(usable_qty: float, yield_pct: float) -> float:
    """
    Calculate raw quantity needed to get desired usable quantity.
    
    Formula: raw = usable / yield
    
    Example: Need 100g cooked, yield 65% → raw = 100/0.65 = 153.8g
    
    Args:
        usable_qty: Amount you WANT (cooked/final)
        yield_pct: Yield as decimal (0.65 for 65%)
    
    Returns:
        Raw quantity needed
    """
    if yield_pct <= 0:
        yield_pct = 1.0
    return usable_qty / yield_pct


def calculate_usable_from_raw(raw_qty: float, yield_pct: float) -> float:
    """
    Calculate usable quantity from raw quantity.
    
    Formula: usable = raw * yield
    
    Example: Have 100g raw, yield 65% → usable = 100*0.65 = 65g
    
    Args:
        raw_qty: Amount you HAVE (raw/purchased)
        yield_pct: Yield as decimal (0.65 for 65%)
    
    Returns:
        Usable quantity
    """
    return raw_qty * yield_pct


def calculate_cost_for_usable(usable_qty: float, raw_cost_per_unit: float, yield_pct: float) -> dict:
    """
    Calculate cost to get a desired usable quantity.
    
    Args:
        usable_qty: Amount you WANT (cooked/final)
        raw_cost_per_unit: Cost per unit of RAW product
        yield_pct: Yield as decimal (0.65 for 65%)
    
    Returns:
        Dict with raw_qty_needed, raw_cost, cost_per_usable_unit
    """
    if yield_pct <= 0:
        yield_pct = 1.0
    
    raw_qty_needed = usable_qty / yield_pct
    total_cost = raw_qty_needed * raw_cost_per_unit
    cost_per_usable = raw_cost_per_unit / yield_pct
    
    return {
        'raw_qty_needed': raw_qty_needed,
        'total_cost': total_cost,
        'cost_per_usable_unit': cost_per_usable
    }


# =============================================================================
# SALES CALCULATION HELPERS (DRY - Don't Repeat Yourself)
# =============================================================================

def get_estimated_dish_price(item_name: str, category: str, recorded_price: float = 0) -> float:
    """
    Get estimated price for a course item.
    
    Course items belong to prix fixe menus:
    - Dinner Tasting: ¥19,480 / 7 dishes = ¥2,783 per dish
    - Lunch Course: ¥6,900 / 4 dishes = ¥1,725 per dish
    - Dessert: ¥1,725 (for both)
    - Beef Tenderloin: ¥1,725 base + ¥5,682 supplement = ¥7,407
    
    SPECIAL CASE: Beef Tenderloin in Lunch/Dinner
    - POS records only the supplement (¥5,682), not the full price
    - We need to add the base course price (¥1,725)
    
    Args:
        item_name: Name of the dish
        category: Category (Dinner, Lunch, Dessert, etc.)
        recorded_price: The price recorded in POS (for special case handling)
    
    Returns:
        Estimated price per dish
    """
    try:
        from config import COURSE_PRICING
    except ImportError:
        # Fallback values if config not available
        COURSE_PRICING = {
            'dinner': {'per_dish': 2783},
            'lunch': {'per_dish': 1725},
            'dessert': {'per_dish': 1725},
            'beef_supplement': 5682,
        }
    
    item_lower = str(item_name).lower() if item_name else ''
    category_lower = str(category).lower() if category else ''
    
    beef_supplement = COURSE_PRICING.get('beef_supplement', 5682)
    base_course_price = 1725  # Base price for course items
    
    # Check if it's Beef Tenderloin
    is_beef = 'beef tenderloin' in item_lower or 'wagyu' in item_lower
    is_course_category = 'dinner' in category_lower or 'lunch' in category_lower
    
    if is_beef and is_course_category:
        # SPECIAL CASE: Beef Tenderloin in Lunch/Dinner
        # POS may record only supplement (¥5,682), we need to add base (¥1,725)
        if recorded_price > 0:
            # Check if recorded price is approximately the supplement amount
            # (allow some variance for tax/rounding)
            if abs(recorded_price - beef_supplement) < 100:
                # POS recorded only the supplement, add base course price
                return recorded_price + base_course_price
            else:
                # POS recorded full price (e.g., A la carte), use as-is
                return recorded_price
        else:
            # No price recorded, use full course price
            return base_course_price + beef_supplement  # 7407
    
    # For non-beef items or A la carte, use recorded price if available
    if recorded_price > 0:
        return recorded_price
    
    # Estimate price based on category (for items with price=0/N/A)
    if 'dessert' in category_lower:
        return COURSE_PRICING.get('dessert', {}).get('per_dish', 1725)
    elif 'dinner' in category_lower:
        return COURSE_PRICING.get('dinner', {}).get('per_dish', 2783)
    elif 'lunch' in category_lower:
        return COURSE_PRICING.get('lunch', {}).get('per_dish', 1725)
    else:
        # Default to dinner pricing for unknown categories
        return COURSE_PRICING.get('dinner', {}).get('per_dish', 2783)


def calculate_revenue(df: pd.DataFrame, fallback_price: float = None) -> pd.DataFrame:
    """
    Calculate revenue for sales data. Uses net_total if available,
    otherwise calculates from qty * price.
    
    Special handling:
    - Beef Tenderloin in Lunch/Dinner: POS records ¥5,682 (supplement only)
      We add ¥1,725 (base course price) to get true revenue of ¥7,407
    - Course items (price=0): estimates price based on category
    
    Args:
        df: DataFrame with columns: qty, price, net_total, name (optional), category (optional)
        fallback_price: Optional fallback price if price is 0/null and no category
    
    Returns:
        DataFrame with added 'calculated_revenue' and 'estimated_price' columns
    """
    df = df.copy()
    
    def calc_row_revenue(row):
        # Get basic info
        qty = float(row.get('qty', 0) or 0)
        if qty == 0:
            return 0.0
        
        item_name = row.get('name', '')
        category = row.get('category', '')
        price = row.get('price', 0)
        price = float(price) if pd.notna(price) else 0
        
        # Use net_total if valid (but check for special cases first)
        net_total = row.get('net_total', 0)
        
        # Check if this is a special case that needs adjustment
        item_lower = str(item_name).lower()
        category_lower = str(category).lower()
        is_beef = 'beef tenderloin' in item_lower or 'wagyu' in item_lower
        is_course = 'dinner' in category_lower or 'lunch' in category_lower
        beef_supplement = 5682
        
        # Special case: Beef Tenderloin in Lunch/Dinner with supplement-only price
        if is_beef and is_course and price > 0 and abs(price - beef_supplement) < 100:
            # POS recorded only the supplement, add base course price
            adjusted_price = price + 1725  # Add base course price
            return qty * adjusted_price
        
        # Normal case: use net_total if valid
        if pd.notna(net_total) and float(net_total or 0) != 0:
            return float(net_total)
        
        # Use recorded price if valid
        if price > 0:
            return qty * price
        
        # Price is 0/null - this is a course item, estimate price
        estimated_price = get_estimated_dish_price(item_name, category, price)
        
        # Use fallback if estimation returns 0
        if estimated_price == 0 and fallback_price:
            estimated_price = fallback_price
        
        return qty * estimated_price
    
    def get_price_used(row):
        """Get the price that was used for calculation (for transparency)"""
        item_name = row.get('name', '')
        category = row.get('category', '')
        price = row.get('price', 0)
        price = float(price) if pd.notna(price) else 0
        
        return get_estimated_dish_price(item_name, category, price)
    
    df['calculated_revenue'] = df.apply(calc_row_revenue, axis=1)
    df['estimated_price'] = df.apply(get_price_used, axis=1)
    
    return df


def convert_quantity_to_grams(df: pd.DataFrame, default_unit_grams: float = 100) -> pd.DataFrame:
    """
    Convert invoice quantities to grams based on the ACTUAL unit column.
    
    IMPORTANT: This uses the 'unit' column from invoice data, NOT inference from quantity.
    
    Args:
        df: DataFrame with columns: quantity, unit
        default_unit_grams: Grams per unit for 'pc'/'can' types (default 100g for caviar cans)
    
    Returns:
        DataFrame with added 'quantity_grams' column
    """
    df = df.copy()
    
    # Known weight units
    weight_units = {'kg', 'g', '100g'}
    # Known container/piece units - treat as default_unit_grams each
    container_units = {'pc', 'can', 'box', 'pack', 'tin', 'bottle', 'jar', 'bag', 'unit'}
    
    def convert_row(row):
        qty = float(row.get('quantity', 0) or 0)
        unit = normalize_unit(str(row.get('unit', 'pc')))
        
        if unit == 'kg':
            return qty * 1000
        elif unit == 'g':
            return qty
        elif unit == '100g':
            return qty * 100
        elif unit in container_units:
            # Known container type - use default grams per unit
            return qty * default_unit_grams
        else:
            # SAFETY NET: Unknown unit (e.g., "tin", "bottle", "portion")
            # Assume it's a container/piece rather than 1 gram
            # This is safer for expensive items like caviar/wine
            return qty * default_unit_grams
    
    df['quantity_grams'] = df.apply(convert_row, axis=1)
    return df


def convert_quantity_to_kg(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert invoice quantities to kg based on the ACTUAL unit column.
    
    Args:
        df: DataFrame with columns: quantity, unit
    
    Returns:
        DataFrame with added 'quantity_kg' column
    """
    df = df.copy()
    
    def convert_row(row):
        qty = float(row.get('quantity', 0) or 0)
        unit = normalize_unit(str(row.get('unit', 'kg')))
        
        if unit == 'kg':
            return qty
        elif unit == 'g':
            return qty / 1000
        elif unit == '100g':
            return qty / 10
        else:
            # Assume kg for unknown units
            return qty
    
    df['quantity_kg'] = df.apply(convert_row, axis=1)
    return df
