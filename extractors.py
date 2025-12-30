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
    """
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
        
        # Build the prompt
        prompt_text = """You are an expert at reading Japanese invoices. Extract ALL line items from this invoice image(s).

Return ONLY valid JSON in this exact format (no markdown, no explanation):
{
  "vendor_name": "Vendor name in Japanese and English if visible",
  "invoice_date": "YYYY-MM-DD",
  "items": [
    {
      "date": "YYYY-MM-DD",
      "item_name": "Product name exactly as written",
      "quantity": 1.0,
      "unit": "kg or 丁 or 本 or pc etc",
      "unit_price": 1000,
      "amount": 1000
    }
  ]
}

IMPORTANT RULES:
1. Extract EVERY line item, not just totals
2. For dates in format YY/MM/DD (like 25/10/01), convert to 2025-10-01
3. Keep Japanese product names as-is (うに, 鮪, 天然鯛, etc.)
4. Skip subtotal rows (伝票合計, ※※, etc.)
5. If quantity has decimals (like 0.200 or 6.30), keep them
6. Unit price × quantity should approximately equal amount
7. Common units: kg, 丁 (for sea urchin), 本, 個, g, 缶

Extract all items now:"""

        # Build message content
        message_content = image_contents + [{"type": "text", "text": prompt_text}]
        
        debug_log(f"   → Calling Claude API...")
        
        # Call Claude API
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 8000,  # Increased to handle large invoices
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
        vendor_name = data.get('vendor_name', 'Unknown Vendor')
        invoice_date = data.get('invoice_date', datetime.now().strftime('%Y-%m-%d'))
        
        debug_log(f"   → Vendor: {vendor_name}")
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
# DEBUG LOGGING (visible in Streamlit)
# =============================================================================
_debug_log = []

def debug_log(msg):
    """Add message to debug log"""
    global _debug_log
    _debug_log.append(msg)
    print(msg)  # Also print to console

def get_debug_log():
    """Get and clear debug log"""
    global _debug_log
    log = _debug_log.copy()
    _debug_log = []
    return log


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
    global _debug_log
    _debug_log = []  # Clear log for this extraction
    
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
        
        # Determine vendor and choose extraction method
        vendor_detected = None
        
        if 'hirayama' in filename or 'ひら山' in text_content.lower():
            vendor_detected = 'hirayama'
        elif 'french' in filename or 'fnb' in filename or 'フレンチ' in text_content:
            vendor_detected = 'french_fnb'
        elif 'maruyata' in filename or '丸弥太' in text_content:
            vendor_detected = 'maruyata'
        elif 'キャビア' in text_content or 'KAVIARI' in text_content:
            vendor_detected = 'french_fnb'
        elif '和牛ヒレ' in text_content:
            vendor_detected = 'hirayama'
        elif any(x in text_content for x in ['うに', '鮪', '天然鯛', '甘鯛', '信州サーモン']):
            vendor_detected = 'maruyata'
        
        debug_log(f"   → Vendor detected: {vendor_detected}")
        debug_log(f"   → Is scanned: {is_scanned}")
        
        records = []
        
        # Try regex parser for known vendors (if not scanned)
        if vendor_detected and not is_scanned and text_content:
            debug_log(f"   → Trying regex parser for {vendor_detected}")
            if vendor_detected == 'hirayama':
                records = parse_hirayama_invoice(text_content)
            elif vendor_detected == 'french_fnb':
                records = parse_french_fnb_invoice(text_content)
            elif vendor_detected == 'maruyata':
                records = parse_maruyata_invoice(text_content)
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
    """Extract invoice data from Excel file (French F&B format)"""
    try:
        # Read Excel with no header to inspect structure
        df = pd.read_excel(uploaded_file, header=None)
        
        if df.empty:
            return []
        
        records = []
        
        # French F&B Excel structure:
        # Column 15: Date (伝票日付)
        # Column 30: Product name (商品名)
        # Column 31: Spec/Unit (規格・入数/単位)
        # Column 32: Unit price (単価)
        # Column 33: Quantity (数量)
        # Column 34: Unit (単位)
        # Column 35: Amount (商品金額)
        
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
                
                # Get date
                date_val = row[date_col]
                if pd.isna(date_val):
                    continue
                
                if isinstance(date_val, datetime):
                    date_str = date_val.strftime('%Y-%m-%d')
                else:
                    date_str = str(date_val)[:10]
                
                # Get product name
                product_name = str(row[product_col]) if pd.notna(row[product_col]) else ""
                if not product_name or product_name == 'nan':
                    continue
                
                # Get other fields
                spec = str(row[spec_col]) if pd.notna(row[spec_col]) else ""
                unit_price = row[price_col] if pd.notna(row[price_col]) else 0
                qty = row[qty_col] if pd.notna(row[qty_col]) else 0
                unit = str(row[unit_col]) if pd.notna(row[unit_col]) else "pc"
                amount = row[amount_col] if pd.notna(row[amount_col]) else 0
                
                # Skip invalid rows
                if qty == 0 or amount == 0:
                    continue
                
                # Determine unit from spec if available
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
        
        return records
    
    except Exception as e:
        print(f"Error extracting Excel invoice: {e}")
        return []


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
    Returns DataFrame with columns: code, name, category, qty, price, net_total
    """
    try:
        content = uploaded_file.read()
        uploaded_file.seek(0)
        
        # Try different encodings
        for encoding in ['utf-8', 'shift_jis', 'cp932', 'utf-8-sig']:
            try:
                if isinstance(content, bytes):
                    text = content.decode(encoding)
                else:
                    text = content
                break
            except UnicodeDecodeError:
                continue
        else:
            return pd.DataFrame()
        
        # Parse CSV
        df = pd.read_csv(StringIO(text))
        
        # Normalize column names
        column_mapping = {
            'Item code': 'code',
            'Item Code': 'code',
            '商品コード': 'code',
            'Item name': 'name',
            'Item Name': 'name',
            '商品名': 'name',
            'Category': 'category',
            'カテゴリ': 'category',
            'Qty': 'qty',
            'qty': 'qty',
            '数量': 'qty',
            'Price': 'price',
            'price': 'price',
            '単価': 'price',
            'Net Total': 'net_total',
            'Net total': 'net_total',
            '売上合計': 'net_total'
        }
        
        df = df.rename(columns=column_mapping)
        
        # Ensure required columns
        required = ['code', 'name', 'qty']
        for col in required:
            if col not in df.columns:
                similar = [c for c in df.columns if col.lower() in c.lower()]
                if similar:
                    df[col] = df[similar[0]]
                else:
                    df[col] = ''
        
        # Add missing columns
        if 'category' not in df.columns:
            df['category'] = 'Other'
        if 'price' not in df.columns:
            df['price'] = 0
        if 'net_total' not in df.columns:
            df['net_total'] = df['qty'] * df['price']
        
        # Clean numeric columns
        df['qty'] = pd.to_numeric(df['qty'], errors='coerce').fillna(0)
        df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0)
        df['net_total'] = pd.to_numeric(df['net_total'], errors='coerce').fillna(0)
        
        # Select and return
        result_df = df[['code', 'name', 'category', 'qty', 'price', 'net_total']].copy()
        result_df = result_df[result_df['qty'] != 0]  # Remove zero quantity
        
        return result_df
    
    except Exception as e:
        print(f"Error extracting sales data: {e}")
        return pd.DataFrame()


# =============================================================================
# TEST
# =============================================================================
if __name__ == "__main__":
    print("Extractors module loaded successfully")
    print(f"pdfplumber available: {PDFPLUMBER_AVAILABLE}")
    print(f"pdf2image available: {PDF2IMAGE_AVAILABLE}")
    print(f"requests available: {REQUESTS_AVAILABLE}")
