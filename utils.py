"""
Utility Functions for The Shinmonzen Purchasing Evaluation System

This file contains helper functions used across the application.
Data/configuration goes in config.py and vendors.py
"""

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
