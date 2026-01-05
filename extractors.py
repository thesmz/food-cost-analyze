"""
Invoice & Sales Data Extractors for The Shinmonzen
Hybrid extraction: Regex for known vendors + AI Vision for unknown/scanned invoices
"""

import re
import os
import tempfile
import base64
import json
from datetime import datetime
from io import StringIO

import pandas as pd
import streamlit as st

# Import vendor name mapping from utils
try:
    from utils import get_clean_vendor_name
except ImportError:
    def get_clean_vendor_name(name):
        return name

# Optional imports with fallbacks
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# =============================================================================
# API KEY HELPER
# =============================================================================
def get_anthropic_api_key():
    """Try to get ANTHROPIC_API_KEY from multiple secret locations"""
    try:
        # Try root level first
        api_key = st.secrets.get("ANTHROPIC_API_KEY")
        if api_key:
            return api_key
        
        # Try under [supabase] section
        if "supabase" in st.secrets:
            api_key = st.secrets["supabase"].get("ANTHROPIC_API_KEY")
            if api_key:
                return api_key
        
        # Try under [anthropic] section
        if "anthropic" in st.secrets:
            api_key = st.secrets["anthropic"].get("api_key")
            if api_key:
                return api_key
    except:
        pass
    
    return None


# =============================================================================
# AI-POWERED INVOICE EXTRACTION (Claude Vision)
# =============================================================================
def extract_invoice_with_ai(pdf_path: str, filename: str = "") -> list:
    """
    Use Claude Vision API to extract invoice data from PDF images.
    Works with any vendor format, including scanned invoices.
    
    Uses AI_CONFIG and AI_INVOICE_PROMPT from config.py
    """
    # Import AI config from config.py
    try:
        from config import AI_CONFIG, AI_INVOICE_PROMPT
    except ImportError:
        AI_CONFIG = {'model': 'claude-sonnet-4-20250514', 'max_tokens': 8000}
        AI_INVOICE_PROMPT = "Extract invoice data as JSON"
    
    debug_log(f"🤖 AI Extraction starting for: {filename}")
    
    api_key = get_anthropic_api_key()
    if not api_key:
        debug_log("   → ❌ No API key available")
        return []
    
    if not PDF2IMAGE_AVAILABLE:
        debug_log("   → ❌ pdf2image not available")
        return []
    
    if not REQUESTS_AVAILABLE:
        debug_log("   → ❌ requests not available")
        return []
    
    try:
        # Convert PDF pages to images
        debug_log(f"   → Converting PDF to images...")
        images = convert_from_path(pdf_path, dpi=150)
        debug_log(f"   → Converted to {len(images)} images")
        
        if not images:
            debug_log("   → ❌ No images extracted from PDF")
            return []
        
        # Encode images as base64
        image_contents = []
        for i, img in enumerate(images[:5]):  # Limit to first 5 pages
            import io
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            img_base64 = base64.b64encode(img_byte_arr.read()).decode('utf-8')
            debug_log(f"   → Image {i+1}: {len(img_base64)} chars encoded")
            
            image_contents.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_base64
                }
            })
        
        # Build message content with prompt from config
        message_content = image_contents + [{"type": "text", "text": AI_INVOICE_PROMPT}]
        
        debug_log(f"   → Calling Claude API (model: {AI_CONFIG['model']})...")
        
        # Call Claude API with settings from config
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": AI_CONFIG['model'],
                "max_tokens": AI_CONFIG['max_tokens'],
                "messages": [{"role": "user", "content": message_content}]
            },
            timeout=120
        )
        
        debug_log(f"   → API response status: {response.status_code}")
        
        if response.status_code != 200:
            debug_log(f"   → ❌ API error: {response.text[:500]}")
            return []
        
        # Parse response and check for truncation
        result = response.json()
        
        # Check if response was truncated
        stop_reason = result.get('stop_reason', 'unknown')
        debug_log(f"   → Stop reason: {stop_reason}")
        if stop_reason == 'max_tokens':
            debug_log(f"   → ⚠️ Response was TRUNCATED (hit max_tokens)")
        
        content = result['content'][0]['text'].strip()
        debug_log(f"   → Response length: {len(content)} chars")
        
        # Clean markdown if present
        if content.startswith('```'):
            content = re.sub(r'^```(?:json)?\s*', '', content)
            content = re.sub(r'\s*```$', '', content)
        
        # Parse JSON with robust error handling for truncated responses
        data = None
        
        # Method 1: Try direct parse
        try:
            data = json.loads(content)
            debug_log(f"   → JSON parsed successfully (direct)")
        except json.JSONDecodeError as e:
            debug_log(f"   → JSON parse error at char {e.pos}: {e.msg}")
        
        # Method 2: Try to repair truncated JSON by extracting complete items
        if data is None:
            debug_log(f"   → Attempting JSON repair for truncated response...")
            try:
                # Extract vendor_name and invoice_date
                vendor_match = re.search(r'"vendor_name"\s*:\s*"([^"]*)"', content)
                date_match = re.search(r'"invoice_date"\s*:\s*"([^"]*)"', content)
                
                vendor_name_extracted = vendor_match.group(1) if vendor_match else 'Unknown Vendor'
                invoice_date_extracted = date_match.group(1) if date_match else datetime.now().strftime('%Y-%m-%d')
                
                debug_log(f"   → Extracted vendor: {vendor_name_extracted}")
                debug_log(f"   → Extracted date: {invoice_date_extracted}")
                
                # Find individual item objects using regex
                # Pattern matches complete JSON objects for items
                item_pattern = r'\{\s*"date"\s*:\s*"[^"]*"\s*,\s*"item_name"\s*:\s*"[^"]*"\s*,\s*"quantity"\s*:\s*[\d.]+\s*,\s*"unit"\s*:\s*"[^"]*"\s*,\s*"unit_price"\s*:\s*[\d.]+\s*,\s*"amount"\s*:\s*[\d.]+\s*\}'
                
                items = []
                for match in re.finditer(item_pattern, content):
                    try:
                        item = json.loads(match.group())
                        items.append(item)
                    except:
                        pass
                
                debug_log(f"   → Found {len(items)} complete items via regex")
                
                if items:
                    data = {
                        'vendor_name': vendor_name_extracted,
                        'invoice_date': invoice_date_extracted,
                        'items': items
                    }
                    debug_log(f"   → JSON repaired successfully!")
                    
            except Exception as repair_error:
                debug_log(f"   → JSON repair failed: {repair_error}")
        
        # Method 3: Try to fix by closing brackets
        if data is None:
            debug_log(f"   → Trying bracket closure fix...")
            try:
                # Find last complete item (ends with },)
                last_complete = content.rfind('},')
                if last_complete > 0:
                    # Close the JSON structure
                    fixed_content = content[:last_complete+1] + ']}'
                    try:
                        data = json.loads(fixed_content)
                        debug_log(f"   → Fixed by closing brackets, got {len(data.get('items', []))} items")
                    except json.JSONDecodeError:
                        pass
            except Exception as fix_error:
                debug_log(f"   → Bracket fix failed: {fix_error}")
        
        if data is None:
            debug_log(f"   → ❌ All JSON parsing methods failed")
            debug_log(f"   → Response start: {content[:300]}")
            debug_log(f"   → Response end: {content[-300:]}")
            return []
        
        # Convert to our record format
        records = []
        vendor_name_raw = data.get('vendor_name', 'Unknown Vendor')
        vendor_name = get_clean_vendor_name(vendor_name_raw)  # Clean the vendor name
        invoice_date = data.get('invoice_date', datetime.now().strftime('%Y-%m-%d'))
        
        debug_log(f"   → Vendor (raw): {vendor_name_raw}")
        debug_log(f"   → Vendor (clean): {vendor_name}")
        debug_log(f"   → Invoice date: {invoice_date}")
        debug_log(f"   → Items found: {len(data.get('items', []))}")
        
        for item in data.get('items', []):
            try:
                item_date = item.get('date', invoice_date)
                
                records.append({
                    'vendor': vendor_name,
                    'date': item_date,
                    'item_name': item.get('item_name', ''),
                    'quantity': float(item.get('quantity', 0)),
                    'unit': item.get('unit', 'pc'),
                    'unit_price': float(item.get('unit_price', 0)),
                    'amount': float(item.get('amount', 0))
                })
            except (ValueError, TypeError) as e:
                debug_log(f"   → Error parsing item: {e}")
                continue
        
        debug_log(f"   → ✅ AI extracted {len(records)} records")
        return records
        
    except Exception as e:
        import traceback
        debug_log(f"   → ❌ AI extraction error: {str(e)}")
        debug_log(f"   → Traceback: {traceback.format_exc()}")
        return []


# =============================================================================
# DEBUG LOGGING (using session_state for thread safety)
# =============================================================================
def _get_debug_log_key():
    """Get the session state key for debug log"""
    return '_extractor_debug_log'

def debug_log(msg):
    """Add message to debug log (thread-safe via session_state)"""
    key = _get_debug_log_key()
    if key not in st.session_state:
        st.session_state[key] = []
    st.session_state[key].append(msg)
    print(msg)  # Also print to console for debugging

def get_debug_log():
    """Get and clear debug log"""
    key = _get_debug_log_key()
    if key not in st.session_state:
        return []
    log = st.session_state[key].copy()
    st.session_state[key] = []
    return log

def clear_debug_log():
    """Clear the debug log"""
    key = _get_debug_log_key()
    st.session_state[key] = []


# =============================================================================
# VENDOR DETECTION (using patterns from vendors.py)
# =============================================================================
def detect_vendor(filename: str, text_content: str) -> str:
    """
    Detect vendor from filename and text content using patterns in vendors.py.
    Returns vendor name or None.
    """
    try:
        from vendors import VENDOR_PATTERNS
    except ImportError:
        return None
    
    combined = (filename + ' ' + text_content).lower()
    
    for vendor_name, config in VENDOR_PATTERNS.items():
        patterns = config.get('patterns', [])
        for pattern in patterns:
            if pattern.lower() in combined:
                return vendor_name
    
    return None


def get_vendor_extractor(vendor_name: str) -> str:
    """
    Get the extractor type for a vendor.
    Returns: 'hirayama', 'french_fnb', 'maruyata', 'ai', etc.
    """
    try:
        from vendors import VENDOR_PATTERNS
    except ImportError:
        return 'ai'
    
    if vendor_name in VENDOR_PATTERNS:
        return VENDOR_PATTERNS[vendor_name].get('extractor', 'ai')
    
    return 'ai'


# =============================================================================
# MAIN INVOICE EXTRACTION (Hybrid: Regex + AI)
# =============================================================================
def extract_invoice_data(uploaded_file) -> list:
    """
    Extract invoice data from PDF or Excel file.
    Hybrid approach:
    1. Try fast regex parsers for known vendors
    2. Fall back to AI Vision for unknown vendors or scanned PDFs
    """
    clear_debug_log()  # Clear log for this extraction (thread-safe)
    
    filename = uploaded_file.name.lower()
    debug_log(f"📄 Starting extraction: {uploaded_file.name}")
    
    # Handle Excel files (French F&B format)
    if filename.endswith('.xlsx') or filename.endswith('.xls'):
        debug_log(f"   → Detected Excel file")
        result = extract_invoice_from_excel(uploaded_file)
        debug_log(f"   → Excel parser returned {len(result)} records")
        return result
    
    # Handle PDF files
    try:
        # Save uploaded file to temp location
        file_content = uploaded_file.read()
        debug_log(f"   → Read {len(file_content)} bytes from file")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        uploaded_file.seek(0)  # Reset for potential re-read
        debug_log(f"   → Saved to temp file: {tmp_path}")
        
        # First try text extraction with pdfplumber
        text_content = ""
        is_scanned = False
        
        debug_log(f"   → pdfplumber available: {PDFPLUMBER_AVAILABLE}")
        
        if PDFPLUMBER_AVAILABLE:
            try:
                with pdfplumber.open(tmp_path) as pdf:
                    num_pages = len(pdf.pages)
                    debug_log(f"   → PDF has {num_pages} pages")
                    for i, page in enumerate(pdf.pages):
                        page_text = page.extract_text()
                        if page_text:
                            text_content += page_text + "\n"
                            debug_log(f"   → Page {i+1}: {len(page_text)} chars")
                        else:
                            debug_log(f"   → Page {i+1}: No text (scanned?)")
                debug_log(f"   → Total text extracted: {len(text_content)} chars")
            except Exception as e:
                debug_log(f"   → pdfplumber error: {str(e)}")
        
        # Check if PDF is mostly scanned (very little text)
        if len(text_content.strip()) < 100:
            is_scanned = True
            debug_log(f"   → PDF is SCANNED (only {len(text_content)} chars)")
        else:
            debug_log(f"   → PDF has text content")
        
        # Detect vendor using patterns from vendors.py
        vendor_detected = detect_vendor(filename, text_content)
        debug_log(f"   → Vendor detected: {vendor_detected}")
        debug_log(f"   → Is scanned: {is_scanned}")
        
        records = []
        
        # Try regex parser for known vendors (if not scanned)
        if vendor_detected and not is_scanned and text_content:
            extractor = get_vendor_extractor(vendor_detected)
            debug_log(f"   → Trying extractor: {extractor}")
            
            if extractor == 'hirayama':
                records = parse_hirayama_invoice(text_content)
            elif extractor == 'french_fnb':
                records = parse_french_fnb_invoice(text_content)
            elif extractor == 'maruyata':
                records = parse_maruyata_invoice(text_content)
            # else: use AI extraction
            
            debug_log(f"   → Regex parser returned {len(records)} records")
        
        # If regex failed or unknown vendor, use AI extraction
        if not records:
            debug_log(f"   → Regex failed/skipped, trying AI extraction...")
            debug_log(f"   → PDF2IMAGE available: {PDF2IMAGE_AVAILABLE}")
            debug_log(f"   → REQUESTS available: {REQUESTS_AVAILABLE}")
            
            api_key = get_anthropic_api_key()
            debug_log(f"   → API key found: {api_key is not None}")
            if api_key:
                debug_log(f"   → API key starts with: {api_key[:15]}...")
            
            if api_key and PDF2IMAGE_AVAILABLE and REQUESTS_AVAILABLE:
                records = extract_invoice_with_ai(tmp_path, filename)
                debug_log(f"   → AI extraction returned {len(records)} records")
            else:
                missing = []
                if not api_key:
                    missing.append("API_KEY")
                if not PDF2IMAGE_AVAILABLE:
                    missing.append("pdf2image")
                if not REQUESTS_AVAILABLE:
                    missing.append("requests")
                debug_log(f"   → ❌ Cannot use AI: missing {', '.join(missing)}")
        
        # Clean up temp file
        try:
            os.unlink(tmp_path)
            debug_log(f"   → Cleaned up temp file")
        except Exception as e:
            debug_log(f"   → Cleanup error: {e}")
        
        debug_log(f"✅ Final result: {len(records)} records")
        
        if records and len(records) > 0:
            debug_log(f"   → Sample record: {records[0]}")
        
        return records
    
    except Exception as e:
        import traceback
        debug_log(f"❌ EXCEPTION: {str(e)}")
        debug_log(f"   → Traceback: {traceback.format_exc()}")
        return []


# =============================================================================
# EXCEL INVOICE EXTRACTION (French F&B)
# =============================================================================
def extract_invoice_from_excel(uploaded_file) -> list:
    """
    Extract invoice data from Excel file.
    Supports multiple vendor formats:
    - French F&B (hardcoded columns)
    - Manmatsu (万松青果) - column headers with brackets
    - Generic format (auto-detect)
    """
    filename = uploaded_file.name.lower()
    debug_log(f"   → Excel extraction starting for: {filename}")
    
    try:
        # First, try to read with headers to inspect structure
        uploaded_file.seek(0)
        xl = pd.ExcelFile(uploaded_file)
        sheet_names = xl.sheet_names
        debug_log(f"   → Excel sheets: {sheet_names}")
        
        # Use first non-empty sheet
        df = None
        used_sheet = None
        for sheet in sheet_names:
            uploaded_file.seek(0)
            temp_df = pd.read_excel(uploaded_file, sheet_name=sheet)
            if not temp_df.empty:
                df = temp_df
                used_sheet = sheet
                debug_log(f"   → Using sheet '{sheet}': {len(df)} rows, {len(df.columns)} columns")
                break
        
        if df is None or df.empty:
            debug_log(f"   → ERROR: All sheets are empty")
            return []
        
        debug_log(f"   → Columns: {list(df.columns)[:10]}...")
        
        records = []
        
        # Detect format by column names
        col_names_str = ' '.join([str(c) for c in df.columns])
        
        # Format 1: Manmatsu (万松青果) - columns with brackets like [商品名]
        if '[商品名]' in col_names_str or '商品名' in col_names_str:
            debug_log(f"   → Detected Manmatsu format")
            records = parse_manmatsu_excel(df, filename)
        
        # Format 2: French F&B (numeric indices)
        elif 'フレンチ' in filename or 'french' in filename or 'fnb' in filename:
            debug_log(f"   → Detected French F&B format (by filename)")
            uploaded_file.seek(0)
            records = parse_french_fnb_excel(uploaded_file)
        
        # Format 3: Generic - try to auto-detect columns
        else:
            debug_log(f"   → Trying generic Excel extraction")
            records = parse_generic_excel(df, filename)
        
        debug_log(f"   → Excel extraction returned {len(records)} records")
        return records
    
    except Exception as e:
        import traceback
        error_msg = f"Error extracting Excel invoice: {type(e).__name__}: {e}"
        debug_log(f"   → ERROR: {error_msg}")
        debug_log(f"   → Traceback: {traceback.format_exc()}")
        return []


def parse_manmatsu_excel(df: pd.DataFrame, filename: str) -> list:
    """Parse Manmatsu (万松青果) Excel format with bracket column names"""
    records = []
    debug_log(f"   → Parsing Manmatsu format: {len(df)} rows")
    
    # Column mapping for Manmatsu format
    # [商品名] = Item name, [数量] = Quantity, [単位] = Unit, [商品金額] = Amount
    # [承認日] or [伝票日付] = Date
    
    col_map = {}
    for col in df.columns:
        col_str = str(col)
        if '商品名' in col_str:
            col_map['item'] = col
        elif '数量' in col_str:
            col_map['qty'] = col
        elif col_str == '[単位]' or col_str == '単位':
            col_map['unit'] = col
        elif '商品金額' in col_str:
            col_map['amount'] = col
        elif '承認日' in col_str or '伝票日付' in col_str:
            col_map['date'] = col
        elif '単価' in col_str:
            col_map['unit_price'] = col
    
    debug_log(f"   → Column mapping: {col_map}")
    
    required = ['item', 'qty', 'amount']
    missing = [r for r in required if r not in col_map]
    if missing:
        debug_log(f"   → ERROR: Missing required columns: {missing}")
        return []
    
    for idx, row in df.iterrows():
        try:
            item_name = str(row[col_map['item']]) if pd.notna(row[col_map['item']]) else ""
            if not item_name or item_name == 'nan' or len(item_name.strip()) < 2:
                continue
            
            qty = float(row[col_map['qty']]) if pd.notna(row[col_map['qty']]) else 0
            amount = float(row[col_map['amount']]) if pd.notna(row[col_map['amount']]) else 0
            
            if qty == 0 or amount == 0:
                continue
            
            # Get optional fields
            unit = str(row[col_map.get('unit', '')]) if col_map.get('unit') and pd.notna(row.get(col_map.get('unit'))) else 'pc'
            if unit == 'nan':
                unit = 'pc'
            
            unit_price = float(row[col_map['unit_price']]) if col_map.get('unit_price') and pd.notna(row.get(col_map.get('unit_price'))) else (amount / qty if qty > 0 else 0)
            
            # Get date
            date_str = None
            if col_map.get('date') and pd.notna(row.get(col_map.get('date'))):
                date_val = row[col_map['date']]
                if isinstance(date_val, datetime):
                    date_str = date_val.strftime('%Y-%m-%d')
                elif hasattr(date_val, 'strftime'):
                    date_str = date_val.strftime('%Y-%m-%d')
                else:
                    date_str = str(date_val)[:10]
            
            if not date_str:
                # Try to extract from filename
                import re
                date_match = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[_\s]*(\d{4})', filename, re.I)
                if date_match:
                    month_map = {'jan':'01','feb':'02','mar':'03','apr':'04','may':'05','jun':'06',
                                'jul':'07','aug':'08','sep':'09','oct':'10','nov':'11','dec':'12'}
                    month = month_map.get(date_match.group(1).lower(), '01')
                    year = date_match.group(2)
                    date_str = f"{year}-{month}-01"
                else:
                    date_str = datetime.now().strftime('%Y-%m-01')
            
            records.append({
                'vendor': '万松青果株式会社 (Manmatsu)',
                'date': date_str,
                'item_name': item_name.strip(),
                'quantity': qty,
                'unit': unit,
                'unit_price': unit_price,
                'amount': amount
            })
            
        except Exception as e:
            debug_log(f"   → Row {idx} error: {e}")
            continue
    
    debug_log(f"   → Manmatsu parser returned {len(records)} records")
    return records


def parse_french_fnb_excel(uploaded_file) -> list:
    """Parse French F&B Excel format (original hardcoded column format)"""
    try:
        # Read Excel with no header to inspect structure
        df = pd.read_excel(uploaded_file, header=None)
        
        if df.empty:
            debug_log(f"   → French F&B Excel is empty")
            return []
        
        records = []
        
        # French F&B Excel structure (hardcoded columns):
        date_col = 15
        product_col = 30
        spec_col = 31
        price_col = 32
        qty_col = 33
        unit_col = 34
        amount_col = 35
        
        for idx in range(1, len(df)):  # Skip header row
            try:
                row = df.iloc[idx]
                
                date_val = row[date_col]
                if pd.isna(date_val):
                    continue
                
                if isinstance(date_val, datetime):
                    date_str = date_val.strftime('%Y-%m-%d')
                else:
                    date_str = str(date_val)[:10]
                
                product_name = str(row[product_col]) if pd.notna(row[product_col]) else ""
                if not product_name or product_name == 'nan':
                    continue
                
                spec = str(row[spec_col]) if pd.notna(row[spec_col]) else ""
                unit_price = row[price_col] if pd.notna(row[price_col]) else 0
                qty = row[qty_col] if pd.notna(row[qty_col]) else 0
                unit = str(row[unit_col]) if pd.notna(row[unit_col]) else "pc"
                amount = row[amount_col] if pd.notna(row[amount_col]) else 0
                
                if qty == 0 or amount == 0:
                    continue
                
                unit_str = unit if unit != 'nan' else 'pc'
                if '100g' in spec:
                    unit_str = '100g'
                elif 'kg' in spec.lower():
                    unit_str = 'kg'
                
                records.append({
                    'vendor': 'フレンチ・エフ・アンド・ビー (French F&B Japan)',
                    'date': date_str,
                    'item_name': product_name.strip(),
                    'quantity': float(qty),
                    'unit': unit_str,
                    'unit_price': float(unit_price) if pd.notna(unit_price) else 0,
                    'amount': float(amount)
                })
                
            except (IndexError, ValueError, TypeError) as e:
                continue
        
        debug_log(f"   → French F&B parser returned {len(records)} records")
        return records
    
    except Exception as e:
        debug_log(f"   → French F&B Excel error: {e}")
        return []


def parse_generic_excel(df: pd.DataFrame, filename: str) -> list:
    """Try to parse Excel with auto-detected columns"""
    records = []
    debug_log(f"   → Generic Excel parsing: {len(df)} rows")
    
    # Try to find columns by common Japanese/English names
    col_map = {}
    
    for col in df.columns:
        col_lower = str(col).lower()
        col_str = str(col)
        
        # Item name
        if any(x in col_str for x in ['商品名', '品名', 'item', 'product', 'name']):
            col_map['item'] = col
        # Quantity
        elif any(x in col_str for x in ['数量', 'qty', 'quantity']):
            col_map['qty'] = col
        # Unit
        elif col_str in ['単位', 'unit'] or col_lower == 'unit':
            col_map['unit'] = col
        # Amount
        elif any(x in col_str for x in ['金額', 'amount', 'total', '合計']):
            col_map['amount'] = col
        # Date
        elif any(x in col_str for x in ['日付', 'date', '伝票日', '納品日']):
            col_map['date'] = col
        # Unit price
        elif any(x in col_str for x in ['単価', 'price', 'unit_price']):
            col_map['unit_price'] = col
    
    debug_log(f"   → Auto-detected columns: {col_map}")
    
    if 'item' not in col_map:
        debug_log(f"   → Could not find item column, trying first text column")
        for col in df.columns:
            if df[col].dtype == 'object':
                col_map['item'] = col
                break
    
    if 'item' not in col_map:
        debug_log(f"   → ERROR: Could not identify item column")
        return []
    
    # Extract vendor from filename
    vendor = filename.replace('.xlsx', '').replace('.xls', '').replace('_', ' ').title()
    
    for idx, row in df.iterrows():
        try:
            item_name = str(row[col_map['item']]) if pd.notna(row[col_map['item']]) else ""
            if not item_name or item_name == 'nan':
                continue
            
            qty = float(row[col_map.get('qty', col_map['item'])]) if col_map.get('qty') and pd.notna(row.get(col_map.get('qty'))) else 1
            amount = float(row[col_map.get('amount', col_map['item'])]) if col_map.get('amount') and pd.notna(row.get(col_map.get('amount'))) else 0
            
            if amount == 0:
                continue
            
            unit = str(row[col_map['unit']]) if col_map.get('unit') and pd.notna(row.get(col_map.get('unit'))) else 'pc'
            unit_price = float(row[col_map['unit_price']]) if col_map.get('unit_price') and pd.notna(row.get(col_map.get('unit_price'))) else (amount / qty if qty > 0 else 0)
            
            date_str = datetime.now().strftime('%Y-%m-01')
            if col_map.get('date') and pd.notna(row.get(col_map.get('date'))):
                date_val = row[col_map['date']]
                if isinstance(date_val, datetime):
                    date_str = date_val.strftime('%Y-%m-%d')
            
            records.append({
                'vendor': vendor,
                'date': date_str,
                'item_name': item_name.strip(),
                'quantity': qty,
                'unit': unit if unit != 'nan' else 'pc',
                'unit_price': unit_price,
                'amount': amount
            })
            
        except Exception as e:
            continue
    
    debug_log(f"   → Generic parser returned {len(records)} records")
    return records


# =============================================================================
# REGEX-BASED PARSERS (for known vendors - fast, no API cost)
# =============================================================================
def parse_hirayama_invoice(text: str) -> list:
    """Parse Meat Shop Hirayama invoice (beef vendor)"""
    records = []
    
    # Extract invoice month/year
    month_match = re.search(r'(\d{4})年(\d{1,2})月', text)
    invoice_year = month_match.group(1) if month_match else "2025"
    invoice_month = month_match.group(2).zfill(2) if month_match else "10"
    
    lines = text.replace('|', ' ').split('\n')
    current_date = f"{invoice_year}-{invoice_month}-01"
    processed = set()
    
    for line in lines:
        # Try to extract date
        date_match = re.search(r'(\d{2})/(\d{2})/(\d{2})', line)
        if date_match:
            current_date = f"20{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        
        # Look for beef quantity patterns
        # Pattern: qty kg price amount
        beef_match = re.search(
            r'(和牛ヒレ|和生ヒレ|牛ヒレ|ヒレ).*?'
            r'(\d+\.\d+)\s*kg.*?'
            r'([\d,]+)\s+'
            r'([\d,]+)',
            line, re.IGNORECASE
        )
        
        if beef_match:
            item_name = beef_match.group(1)
            qty = float(beef_match.group(2))
            unit_price = float(beef_match.group(3).replace(',', ''))
            amount = float(beef_match.group(4).replace(',', ''))
            
            key = f"{current_date}-{qty}-{amount}"
            if key not in processed:
                processed.add(key)
                records.append({
                    'vendor': 'ミートショップひら山 (Meat Shop Hirayama)',
                    'date': current_date,
                    'item_name': '和牛ヒレ',
                    'quantity': qty,
                    'unit': 'kg',
                    'unit_price': unit_price,
                    'amount': amount
                })
    
    return records


def parse_french_fnb_invoice(text: str) -> list:
    """Parse French F&B Japan invoice (caviar, butter, etc.)"""
    records = []
    
    # Extract year/month
    month_match = re.search(r'(\d{4})年(\d{1,2})月', text)
    invoice_year = month_match.group(1) if month_match else "2025"
    invoice_month = month_match.group(2).zfill(2) if month_match else "10"
    
    lines = text.split('\n')
    processed = set()
    
    for line in lines:
        # Caviar pattern
        caviar_match = re.search(
            r'(キャビア|KAVIARI|キャヴィア).*?'
            r'(\d+)\s*(?:缶|個|pc)?\s*'
            r'([\d,]+)\s+'
            r'([\d,]+)',
            line, re.IGNORECASE
        )
        
        if caviar_match:
            qty = float(caviar_match.group(2))
            unit_price = float(caviar_match.group(3).replace(',', ''))
            amount = float(caviar_match.group(4).replace(',', ''))
            
            key = f"caviar-{qty}-{amount}"
            if key not in processed:
                processed.add(key)
                records.append({
                    'vendor': 'フレンチ・エフ・アンド・ビー (French F&B Japan)',
                    'date': f"{invoice_year}-{invoice_month}-01",
                    'item_name': 'KAVIARI キャビア クリスタル',
                    'quantity': qty,
                    'unit': '100g',
                    'unit_price': unit_price,
                    'amount': amount
                })
        
        # Butter pattern
        butter_match = re.search(
            r'(バター|butter|ブール|パレット).*?'
            r'(\d+)\s*(?:個|pc)?\s*'
            r'([\d,]+)\s+'
            r'([\d,]+)',
            line, re.IGNORECASE
        )
        
        if butter_match and 'caviar' not in processed:
            qty = float(butter_match.group(2))
            unit_price = float(butter_match.group(3).replace(',', ''))
            amount = float(butter_match.group(4).replace(',', ''))
            
            key = f"butter-{qty}-{amount}"
            if key not in processed:
                processed.add(key)
                records.append({
                    'vendor': 'フレンチ・エフ・アンド・ビー (French F&B Japan)',
                    'date': f"{invoice_year}-{invoice_month}-01",
                    'item_name': 'パレット ロンド バター',
                    'quantity': qty,
                    'unit': 'pc',
                    'unit_price': unit_price,
                    'amount': amount
                })
    
    return records


def parse_maruyata_invoice(text: str) -> list:
    """Parse Maruyata (丸弥太) seafood invoice"""
    records = []
    
    # Extract year
    year_match = re.search(r'(\d{4})年(\d{1,2})月', text)
    invoice_year = year_match.group(1) if year_match else "2025"
    
    lines = text.split('\n')
    current_date = None
    processed = set()
    
    for line in lines:
        line = line.strip()
        
        # Skip subtotals and headers
        if '伝票合計' in line or '※※' in line or '振込' in line:
            continue
        if '請求書' in line or '伝票日付' in line or '銀行口座' in line:
            continue
        
        # Extract date
        date_match = re.search(r'(\d{2})/(\d{2})/(\d{2})', line)
        if date_match:
            yy, mm, dd = date_match.groups()
            current_date = f"20{yy}-{mm}-{dd}"
        
        # Match product line
        product_match = re.search(
            r'([ぁ-んァ-ン一-龥ー]+(?:サーモン|ホタテ)?)\s+'
            r'(\d+(?:[.,]\d+)?)\s*'
            r'(kg|丁|本|個|g)\s*'
            r'([\d,]+)\s+'
            r'([\d,]+)',
            line
        )
        
        if product_match and current_date:
            product_name = product_match.group(1).strip()
            qty_str = product_match.group(2).replace(',', '.')
            unit = product_match.group(3)
            unit_price = product_match.group(4).replace(',', '')
            amount = product_match.group(5).replace(',', '')
            
            # Skip invalid
            if product_name in ['伝票', '合計', '入金', '消費税']:
                continue
            
            try:
                qty = float(qty_str)
                key = f"{current_date}-{product_name}-{qty}-{amount}"
                if key not in processed:
                    processed.add(key)
                    records.append({
                        'vendor': '丸弥太 (Maruyata Seafood)',
                        'date': current_date,
                        'item_name': product_name,
                        'quantity': qty,
                        'unit': unit,
                        'unit_price': float(unit_price),
                        'amount': float(amount)
                    })
            except (ValueError, TypeError):
                continue
    
    return records


# =============================================================================
# SALES DATA EXTRACTION
# =============================================================================
def extract_sales_data(uploaded_file) -> pd.DataFrame:
    """
    Extract sales data from CSV file (POS export format)
    Returns DataFrame with columns matching database: 
    sale_date, code, item_name, category, qty, price, net_total
    """
    debug_log(f"📊 Sales extraction starting: {uploaded_file.name}")
    
    try:
        content = uploaded_file.read()
        uploaded_file.seek(0)
        
        debug_log(f"   → Read {len(content)} bytes")
        
        # Try different encodings
        text = None
        for encoding in ['utf-8', 'utf-8-sig', 'shift_jis', 'cp932']:
            try:
                if isinstance(content, bytes):
                    text = content.decode(encoding)
                else:
                    text = content
                debug_log(f"   → Decoded with {encoding}")
                break
            except UnicodeDecodeError:
                continue
        
        if text is None:
            debug_log(f"   → ❌ Could not decode file")
            return pd.DataFrame()
        
        lines = text.split('\n')
        debug_log(f"   → Total lines: {len(lines)}")
        
        # Extract date from header (look for date range like "2025-11-01 - 2025-11-30")
        sale_date = None
        date_pattern = r'\((\d{4}-\d{2}-\d{2})\s*-\s*(\d{4}-\d{2}-\d{2})\)'
        for line in lines[:10]:
            match = re.search(date_pattern, line)
            if match:
                # Use the start date of the range
                sale_date = match.group(1)
                debug_log(f"   → Found date range: {match.group(1)} - {match.group(2)}")
                break
        
        if not sale_date:
            # Try to extract from filename (e.g., "Nov_2025" or "202511")
            filename = uploaded_file.name
            month_match = re.search(r'(\d{4})[-_]?(\d{2})', filename)
            if month_match:
                sale_date = f"{month_match.group(1)}-{month_match.group(2)}-01"
                debug_log(f"   → Date from filename: {sale_date}")
            else:
                # Default to first of current month
                sale_date = datetime.now().strftime('%Y-%m-01')
                debug_log(f"   → Using default date: {sale_date}")
        
        # Find the row with column headers
        header_row = 0
        for i, line in enumerate(lines[:20]):
            if 'Code' in line and 'Name' in line and 'Category' in line:
                header_row = i
                debug_log(f"   → Found header at row {i}")
                break
            elif 'Item code' in line or 'Item Code' in line:
                header_row = i
                debug_log(f"   → Found header at row {i}")
                break
        
        # Parse CSV with correct header row
        df = pd.read_csv(StringIO(text), skiprows=header_row)
        debug_log(f"   → Parsed {len(df)} rows, columns: {list(df.columns)}")
        
        # Normalize column names to match DATABASE SCHEMA
        column_mapping = {
            # Code
            'Code': 'code',
            'Item code': 'code',
            'Item Code': 'code',
            '商品コード': 'code',
            
            # Name → item_name (DB column name)
            'Name': 'item_name',
            'Item name': 'item_name',
            'Item Name': 'item_name',
            '商品名': 'item_name',
            
            # Category
            'Category': 'category',
            'カテゴリ': 'category',
            
            # Qty
            'Qty': 'qty',
            'qty': 'qty',
            'Quantity': 'qty',
            '数量': 'qty',
            
            # Price
            'Price': 'price',
            'price': 'price',
            'Unit Price': 'price',
            '単価': 'price',
            
            # Net total
            'Net Item Total': 'net_total',
            'Net Total': 'net_total',
            'Net total': 'net_total',
            '売上合計': 'net_total',
        }
        
        df = df.rename(columns=column_mapping)
        debug_log(f"   → After rename: {list(df.columns)}")
        
        # Ensure required columns exist
        if 'code' not in df.columns:
            df['code'] = ''
        if 'item_name' not in df.columns:
            df['item_name'] = ''
        if 'category' not in df.columns:
            df['category'] = 'Other'
        if 'qty' not in df.columns:
            df['qty'] = 0
        if 'price' not in df.columns:
            df['price'] = 0
        if 'net_total' not in df.columns:
            df['net_total'] = 0
        
        # Add sale_date column (from header)
        df['sale_date'] = sale_date
        
        # Clean data - remove Total rows and empty rows
        initial_count = len(df)
        df = df[df['code'].notna() & (df['code'] != '')]
        df = df[~df['code'].astype(str).str.contains('Total', case=False, na=False)]
        df = df[~df['item_name'].astype(str).str.contains('Total:', case=False, na=False)]
        debug_log(f"   → Removed {initial_count - len(df)} total/empty rows")
        
        # Clean numeric columns
        for col in ['qty', 'price', 'net_total']:
            df[col] = df[col].astype(str).str.replace(',', '').str.replace('%', '')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Remove zero quantity rows
        df = df[df['qty'] != 0]
        
        # Select columns matching DATABASE SCHEMA
        result_df = df[['sale_date', 'code', 'item_name', 'category', 'qty', 'price', 'net_total']].copy()
        
        debug_log(f"   → ✅ Final: {len(result_df)} records for {sale_date}")
        
        return result_df
    
    except Exception as e:
        import traceback
        debug_log(f"   → ❌ Error: {str(e)}")
        debug_log(f"   → {traceback.format_exc()}")
        return pd.DataFrame()


# =============================================================================
# TEST
# =============================================================================
if __name__ == "__main__":
    print("Extractors module loaded successfully")
    print(f"pdfplumber available: {PDFPLUMBER_AVAILABLE}")
    print(f"pdf2image available: {PDF2IMAGE_AVAILABLE}")
    print(f"requests available: {REQUESTS_AVAILABLE}")
