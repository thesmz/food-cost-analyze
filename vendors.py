"""
Vendor Name Mapping for The Shinmonzen

This file contains ONLY vendor name data.
Japanese vendor names → Clean English display names

To add a new vendor:
1. Add the Japanese name as key
2. Add the English name as value
3. If vendor has multiple name variations, add all of them

NO FUNCTIONS HERE - functions go in utils.py
NO PRICES HERE - prices come from database
"""

# =============================================================================
# VENDOR NAME MAPPING
# Japanese invoice names → Clean English display names
# =============================================================================
VENDOR_NAME_MAP = {
    # ----- Meat & Fish -----
    'ミートショップひら山': 'Meat Shop Hirayama',
    'ひら山': 'Meat Shop Hirayama',
    '株式会社ミートショップひら山': 'Meat Shop Hirayama',  # Full company name
    '株式会社ミートショップひらい': 'Meat Shop Hirayama',  # OCR misread variant
    'ミートショップひらい': 'Meat Shop Hirayama',  # OCR misread variant
    
    '株式会社 丸弥太': 'Maruyata',
    '丸弥太': 'Maruyata',
    
    '有限会社浅見水産': 'Asami Suisan',
    '浅見水産': 'Asami Suisan',
    
    '洛北ジビエ イマイ': 'Gibier Imai',
    
    '株式会社銀閣寺大西': 'Ginkakuji Onishi',
    
    # ----- Dairy & Cheese -----
    '新利根チーズ工房': 'Cheese Kobo',
    'タカナシ販売株式会社': 'Takanashi',
    '有限会社レチェール・ユゲ': 'Yuge Farm',
    
    # ----- Produce & Vegetables -----
    '株式会社ポモナファーム': 'Pomona Farm',
    '株式会社ミナト　青果事業部': 'Minato Seika',
    '株式会社ミナト': 'Minato',
    '万松青果株式会社': 'Manmatsu',
    '万松青果': 'Manmatsu',
    '万松青果株式会社 (Manmatsu)': 'Manmatsu',  # Legacy parser output
    
    # ----- Specialty Foods -----
    'フレンチ・エフ・アンド・ビー': 'French F&B Japan',
    'フレンチ・エフ・アンド・ビー・ジャパン株式会社': 'French F&B Japan',  # BtoBプラットフォーム
    'French F&B': 'French F&B Japan',
    'フレンチ・エフ・アンド・ビー (French F&B Japan)': 'French F&B Japan',  # Legacy parser output
    
    '株式会社 LIBERTE JAPON': 'Liberte Japon',
    'LIBERTE JAPON': 'Liberte Japon',
    
    '株式会社 有徳島庄蔵卸月浦明堂': 'Nezu Matsumoto',
    
    'ＡＳＩＡＭＩＸ株式会社': 'Asiamix',
    
    # ----- Rice & Bread -----
    '株式会社八代目儀兵衛': 'Hachidaime Gihei',
    '株式会社進々堂': 'Shinshindo',
    
    # ----- Other Suppliers -----
    '池伝株式会社　大阪支店': 'Ikeden',
    '池伝株式会社': 'Ikeden',
    
    'ＷＩＳＫジャパン株式会社': 'WISK Japan',
}

# =============================================================================
# VENDOR DETECTION PATTERNS
# Patterns used to identify vendors from invoice text/filenames
# Add new vendors here instead of in extractors.py
# =============================================================================
VENDOR_PATTERNS = {
    'Meat Shop Hirayama': {
        'patterns': ['ミートショップひら山', 'ひら山', 'hirayama'],
        'extractor': 'hirayama',  # Which regex extractor to use
    },
    'Maruyata': {
        'patterns': ['丸弥太', 'maruyata'],
        'extractor': 'maruyata',
    },
    'French F&B Japan': {
        'patterns': ['フレンチ・エフ・アンド・ビー', 'french f&b', 'french fnb', 'french_fnb'],
        'extractor': 'french_fnb',
    },
    'Asami Suisan': {
        'patterns': ['浅見水産', 'asami'],
        'extractor': 'ai',  # Use AI extraction
    },
    'Gibier Imai': {
        'patterns': ['洛北ジビエ', 'イマイ', 'gibier', 'imai'],
        'extractor': 'ai',
    },
    'Cheese Kobo': {
        'patterns': ['新利根チーズ', 'cheese kobo'],
        'extractor': 'ai',
    },
    'Takanashi': {
        'patterns': ['タカナシ', 'takanashi'],
        'extractor': 'ai',
    },
    'Pomona Farm': {
        'patterns': ['ポモナ', 'pomona'],
        'extractor': 'ai',
    },
    'Minato': {
        'patterns': ['ミナト', 'minato'],
        'extractor': 'ai',
    },
    'Ginkakuji Onishi': {
        'patterns': ['銀閣寺大西', 'ginkakuji', 'onishi'],
        'extractor': 'ai',
    },
}

# =============================================================================
# ITEM NAME PATTERNS - For invoice parsing
# Used to identify specific items in invoice text
# =============================================================================
ITEM_PATTERNS = {
    'wagyu_tenderloin': {
        'display_name': 'Wagyu Tenderloin',
        'patterns': ['和牛ヒレ', '和牛モレ', '和生ヒレ', '和邊ヒレ'],
    },
    'caviar': {
        'display_name': 'KAVIARI Caviar',
        'patterns': ['キャビア', 'クリスタル', 'KAVIARI', 'caviar'],
    },
    'sea_urchin': {
        'display_name': 'Sea Urchin',
        'patterns': ['うに', 'ウニ', '雲丹'],
    },
    'tuna': {
        'display_name': 'Tuna',
        'patterns': ['鮪', 'マグロ', 'まぐろ'],
    },
}
