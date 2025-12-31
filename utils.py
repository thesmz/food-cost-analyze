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
    
    # Common unit mappings
    unit_map = {
        'キログラム': 'kg',
        'グラム': 'g',
        '個': 'pc',
        '本': 'pc',
        '丁': 'pc',
        '缶': 'can',
        '箱': 'box',
        'パック': 'pack',
        'kg': 'kg',
        'g': 'g',
        'pc': 'pc',
        'pcs': 'pc',
        '100g': '100g',
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

def calculate_revenue(df: pd.DataFrame, fallback_price: float = None) -> pd.DataFrame:
    """
    Calculate revenue for sales data. Uses net_total if available,
    otherwise calculates from qty * price.
    
    Args:
        df: DataFrame with columns: qty, price, net_total
        fallback_price: Optional fallback price if price is 0/null
    
    Returns:
        DataFrame with added 'calculated_revenue' column
    """
    df = df.copy()
    
    def calc_row_revenue(row):
        # Use net_total if it's valid
        if pd.notna(row.get('net_total')) and row.get('net_total', 0) != 0:
            return float(row['net_total'])
        
        # Otherwise calculate from qty * price
        qty = float(row.get('qty', 0) or 0)
        price = float(row.get('price', 0) or 0)
        
        # Use fallback price if price is 0/null
        if price == 0 and fallback_price:
            price = fallback_price
        
        return qty * price
    
    df['calculated_revenue'] = df.apply(calc_row_revenue, axis=1)
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
    
    def convert_row(row):
        qty = float(row.get('quantity', 0) or 0)
        unit = normalize_unit(str(row.get('unit', 'pc')))
        
        if unit == 'kg':
            return qty * 1000
        elif unit == 'g':
            return qty
        elif unit == '100g':
            return qty * 100
        elif unit in ['pc', 'can', 'box', 'pack']:
            # Use the default grams per unit (e.g., 100g per caviar can)
            return qty * default_unit_grams
        else:
            # Unknown unit - assume it's already in the target unit
            return qty
    
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
