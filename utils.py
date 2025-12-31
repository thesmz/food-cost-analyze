"""
Utility Functions for The Shinmonzen Purchasing Evaluation System

This file contains helper functions used across the application.
Data/configuration goes in config.py and vendors.py
"""

import pandas as pd
from vendors import VENDOR_NAME_MAP, ITEM_PATTERNS
from config import INGREDIENT_PATTERNS


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
# SALES CALCULATION HELPERS (DRY - Don't Repeat Yourself)
# =============================================================================

def get_estimated_dish_price(item_name: str, category: str) -> float:
    """
    Get estimated price for a course item (items with price=0).
    
    Course items belong to prix fixe menus:
    - Dinner Tasting: ¥19,480 / 7 dishes = ¥2,783 per dish
    - Lunch Course: ¥6,900 / 4 dishes = ¥1,725 per dish
    - Dessert: ¥1,725 (for both)
    - Beef Tenderloin: ¥1,725 base + ¥5,682 supplement = ¥7,407
    
    Args:
        item_name: Name of the dish
        category: Category (Dinner, Lunch, Dessert, etc.)
    
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
    
    # Special case: Beef Tenderloin has a supplement
    # Uses 1725 base + 5682 supplement = 7407 for both lunch and dinner
    is_beef = 'beef tenderloin' in item_lower or 'wagyu' in item_lower
    
    if is_beef and ('dinner' in category_lower or 'lunch' in category_lower):
        base_price = 1725  # Fixed base for beef
        beef_supplement = COURSE_PRICING.get('beef_supplement', 5682)
        return base_price + beef_supplement  # 7407
    
    # Determine base price by category for non-beef items
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
    
    For course items (price=0), estimates price based on category:
    - Dinner items: ¥2,783 per dish (¥19,480 / 7)
    - Lunch items: ¥1,725 per dish (¥6,900 / 4)
    - Dessert: ¥1,725
    - Beef Tenderloin: base + ¥5,682 supplement
    
    Args:
        df: DataFrame with columns: qty, price, net_total, name (optional), category (optional)
        fallback_price: Optional fallback price if price is 0/null and no category
    
    Returns:
        DataFrame with added 'calculated_revenue' and 'estimated_price' columns
    """
    df = df.copy()
    
    def calc_row_revenue(row):
        # Use net_total if it's valid and non-zero
        net_total = row.get('net_total', 0)
        if pd.notna(net_total) and float(net_total or 0) != 0:
            return float(net_total)
        
        # Get quantity
        qty = float(row.get('qty', 0) or 0)
        if qty == 0:
            return 0.0
        
        # Check if price is valid
        price = row.get('price', 0)
        if pd.notna(price) and float(price or 0) > 0:
            return qty * float(price)
        
        # Price is 0/null - this is a course item, estimate price
        item_name = row.get('name', '')
        category = row.get('category', '')
        
        estimated_price = get_estimated_dish_price(item_name, category)
        
        # Use fallback if estimation returns 0
        if estimated_price == 0 and fallback_price:
            estimated_price = fallback_price
        
        return qty * estimated_price
    
    def get_price_used(row):
        """Get the price that was used for calculation (for transparency)"""
        price = row.get('price', 0)
        if pd.notna(price) and float(price or 0) > 0:
            return float(price)
        
        item_name = row.get('name', '')
        category = row.get('category', '')
        return get_estimated_dish_price(item_name, category)
    
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
