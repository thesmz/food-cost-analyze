"""
Dynamic Recipe & Menu Costing Tool
Build menus from scratch by calculating dish costs from ingredient breakdowns.
Pantry auto-populated from actual invoice data with translation support.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import init_supabase, load_invoices, get_date_range

st.set_page_config(
    page_title="Recipe & Menu Costing | The Shinmonzen",
    page_icon="🍽️",
    layout="wide"
)

st.title("🍽️ Recipe & Menu Costing Tool")
st.markdown("*Build menus by calculating dish costs from ingredient breakdowns*")


# =============================================================================
# TRANSLATION FUNCTION (Using Claude API for PANTRY INGREDIENTS)
# =============================================================================
def translate_pantry_ingredients(pantry_dict):
    """
    Translate pantry ingredient names from Japanese to meaningful English using Claude API.
    This is SMART translation - understands that ﾊﾟﾚｯﾄ ﾛﾝﾄﾞ ﾄﾞ ﾌﾞｰﾙ is BUTTER, not just transliteration.
    Returns: (updated_pantry_dict, status_message, is_success)
    """
    import requests
    import json
    
    st.info("🚀 Debug: translate_pantry_ingredients() called")
    st.info(f"📦 Debug: pantry_dict has {len(pantry_dict) if pantry_dict else 0} items")
    
    # Check if pantry is empty
    if not pantry_dict:
        return pantry_dict, "❌ Pantry is empty. Upload invoices first.", False
    
    # Get API key from Streamlit secrets
    st.info("🔑 Debug: Attempting to get API key from secrets...")
    try:
        api_key = st.secrets.get("ANTHROPIC_API_KEY")
        if not api_key:
            st.error("❌ Debug: API key is None or empty")
            return pantry_dict, "❌ ANTHROPIC_API_KEY not found in secrets. Add it to enable translation.", False
        st.info(f"✅ Debug: API key retrieved (length: {len(api_key)})")
    except Exception as e:
        st.error(f"❌ Debug: Exception getting secrets: {type(e).__name__}: {str(e)}")
        return pantry_dict, f"❌ Could not access secrets: {str(e)[:100]}", False
    
    # Collect names that need translation
    st.info("📋 Debug: Collecting names that need translation...")
    names_to_translate = []
    for name, info in pantry_dict.items():
        if not info.get('english_name'):
            names_to_translate.append(name)
    
    st.info(f"📝 Debug: Found {len(names_to_translate)} items needing translation")
    
    if not names_to_translate:
        return pantry_dict, "ℹ️ All ingredients already have English names.", True
    
    # Build smart prompt for culinary context
    prompt = f"""You are a culinary expert translator. Translate these Japanese food ingredient names to clear, meaningful English names that a chef would understand.

IMPORTANT RULES:
1. DO NOT just transliterate - understand what the ingredient actually IS
2. For French/Italian product names in katakana, identify the actual product (e.g., butter, cheese, mushroom type)
3. Keep it concise but clear - a chef should immediately know what this ingredient is
4. Include key details like (Salted), (Fresh), size/weight if relevant

Examples of what I want:
- "ﾊﾟﾚｯﾄ ﾛﾝﾄﾞ ﾄﾞ ﾌﾞｰﾙ ﾄﾞ ﾊﾞﾗｯﾄ ﾃﾞﾐｾﾙ（有塩）" → "Churned Butter Round (Lightly Salted)"
- "KAVIARI キャビア クリスタル100g セレクションJG" → "KAVIARI Crystal Caviar 100g Selection"
- "生 スモールジロール 1kg" → "Fresh Small Girolles (Chanterelles) 1kg"
- "和牛ヒレ" → "Wagyu Beef Tenderloin"
- "シャンパン ヴィネガー 500ml" → "Champagne Vinegar 500ml"

Ingredient names to translate:
{json.dumps(names_to_translate, ensure_ascii=False, indent=2)}

Return ONLY a valid JSON object mapping original name to English translation.
Format: {{"original Japanese name": "Clear English Name"}}
JSON only, no explanation or markdown:"""

    try:
        st.info(f"🔑 Debug: API key starts with: {api_key[:10]}..." if len(api_key) > 10 else "API key too short")
        st.info(f"📤 Debug: Sending request with {len(names_to_translate)} items...")
        
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=60
        )
        
        st.info(f"📡 Debug: Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            content = result['content'][0]['text']
            
            st.info(f"📄 Debug: Response content length: {len(content)}")
            
            # Show first part of response
            with st.expander("Raw API Response (first 500 chars)", expanded=False):
                st.code(content[:500])
            
            # Parse JSON from response - handle potential markdown wrapping
            import re
            content_clean = content.strip()
            if content_clean.startswith('```'):
                content_clean = re.sub(r'^```(?:json)?\s*', '', content_clean)
                content_clean = re.sub(r'\s*```$', '', content_clean)
            
            try:
                translations = json.loads(content_clean)
                st.info(f"✅ Debug: Parsed {len(translations)} translations from JSON")
            except json.JSONDecodeError as e:
                st.warning(f"⚠️ Debug: JSON parse error: {e}")
                json_match = re.search(r'\{[\s\S]*\}', content_clean)
                if json_match:
                    translations = json.loads(json_match.group())
                    st.info(f"✅ Debug: Regex found {len(translations)} translations")
                else:
                    return pantry_dict, f"❌ Could not parse JSON from API response: {content[:100]}", False
            
            # Apply translations to pantry
            translated_count = 0
            for name in pantry_dict:
                if name in translations:
                    pantry_dict[name]['english_name'] = translations[name]
                    translated_count += 1
            
            st.info(f"✅ Debug: Applied {translated_count} translations to pantry")
            
            return pantry_dict, f"✅ Translated {translated_count} of {len(names_to_translate)} ingredients!", True
        else:
            error_detail = response.text[:500]
            st.error(f"❌ API error details: {error_detail}")
            return pantry_dict, f"❌ API error {response.status_code}: {response.text[:200]}", False
            
    except requests.exceptions.Timeout:
        st.error("❌ Debug: Request timed out after 60 seconds")
        return pantry_dict, "❌ Request timed out. Try again.", False
    except requests.exceptions.ConnectionError as e:
        st.error(f"❌ Debug: Connection error: {str(e)}")
        return pantry_dict, f"❌ Connection error: {str(e)[:100]}", False
    except Exception as e:
        import traceback
        st.error(f"❌ Debug: Exception type: {type(e).__name__}")
        st.error(f"❌ Debug: Exception message: {str(e)}")
        with st.expander("Full traceback"):
            st.code(traceback.format_exc())
        return pantry_dict, f"❌ Error: {type(e).__name__}: {str(e)[:200]}", False


# =============================================================================
# LOAD INVOICE DATA FOR PANTRY
# =============================================================================
@st.cache_data(ttl=300)
def load_pantry_from_invoices():
    """Load ingredient prices from actual invoice data"""
    supabase = init_supabase()
    if not supabase:
        return {}
    
    db_min, db_max = get_date_range(supabase)
    if not db_min or not db_max:
        return {}
    
    invoices_df = load_invoices(supabase, db_min, db_max)
    if invoices_df.empty:
        return {}
    
    pantry = {}
    
    # Group by item_name and vendor
    for (item_name, vendor), group in invoices_df.groupby(['item_name', 'vendor']):
        # Skip shipping/delivery fees
        if '運賃' in str(item_name) or '送料' in str(item_name) or '宅配' in str(item_name):
            continue
        
        # Get unit price from invoice
        if 'unit_price' in group.columns and group['unit_price'].notna().any():
            unit_price = group['unit_price'].dropna().median()
        else:
            total_amt = group['amount'].sum()
            total_qty = group['quantity'].sum()
            unit_price = total_amt / total_qty if total_qty > 0 else total_amt
        
        # Determine unit type
        unit_raw = group['unit'].iloc[0] if 'unit' in group.columns and pd.notna(group['unit'].iloc[0]) else ''
        unit_str = str(unit_raw).lower()
        
        if unit_str in ['kg', 'ｋｇ']:
            unit_type = 'kg'
        elif unit_str in ['g', 'ｇ']:
            unit_type = 'g'
        elif '100g' in item_name.lower() or '100g' in unit_str:
            unit_type = '100g'
        elif unit_str in ['l', 'ｌ', 'リットル']:
            unit_type = 'L'
        elif unit_str in ['ml', 'ｍｌ']:
            unit_type = 'ml'
        elif unit_str in ['本', '缶', 'pc', 'ｐｃ', '個']:
            unit_type = 'pc'
        else:
            unit_type = 'unit'
        
        pantry[item_name] = {
            'cost_per_unit': round(unit_price),
            'unit': unit_type,
            'vendor': vendor,
            'original_name': item_name,
            'english_name': None
        }
    
    return pantry


# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================
if 'pantry' not in st.session_state:
    st.session_state.pantry = load_pantry_from_invoices()

if 'custom_pantry' not in st.session_state:
    st.session_state.custom_pantry = {}

if 'saved_dishes' not in st.session_state:
    st.session_state.saved_dishes = []

if 'current_dish_ingredients' not in st.session_state:
    st.session_state.current_dish_ingredients = []

if 'menu_type' not in st.session_state:
    st.session_state.menu_type = 'Dinner'

if 'selling_price' not in st.session_state:
    st.session_state.selling_price = 24000

# Input field states for pantry sync
if 'ing_name' not in st.session_state:
    st.session_state.ing_name = ""
if 'ing_cost' not in st.session_state:
    st.session_state.ing_cost = 1000
if 'ing_unit' not in st.session_state:
    st.session_state.ing_unit = 'kg'
if 'ing_qty' not in st.session_state:
    st.session_state.ing_qty = 100.0
if 'ing_yield' not in st.session_state:
    st.session_state.ing_yield = 100

# Translation status message
if 'translate_message' not in st.session_state:
    st.session_state.translate_message = None
if 'translate_success' not in st.session_state:
    st.session_state.translate_success = False


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def calculate_ingredient_cost(unit_cost, unit, quantity, yield_pct):
    """Calculate cost for an ingredient line with unit conversion and yield adjustment."""
    if yield_pct <= 0:
        yield_pct = 100
    
    unit_scales = {
        'kg': 1000,
        'g': 1,
        '100g': 100,
        'L': 1000,
        'ml': 1,
        'pc': 1,
    }
    
    scale = unit_scales.get(unit, 1)
    cost = (unit_cost / scale) * quantity / (yield_pct / 100)
    return cost


def on_pantry_select():
    """Callback when pantry selection changes - sync inputs"""
    selected = st.session_state.pantry_selector
    all_pantry = {**st.session_state.pantry, **st.session_state.custom_pantry}
    
    if selected and selected != "-- Select --" and selected in all_pantry:
        info = all_pantry[selected]
        st.session_state.ing_name = info.get('english_name') or info.get('original_name', selected)
        st.session_state.ing_cost = info['cost_per_unit']
        st.session_state.ing_unit = info['unit']


def add_ingredient_to_dish():
    """Add ingredient to current dish"""
    st.session_state.current_dish_ingredients.append({
        'name': st.session_state.ing_name,
        'unit_cost': st.session_state.ing_cost,
        'unit': st.session_state.ing_unit,
        'quantity': st.session_state.ing_qty,
        'yield_pct': st.session_state.ing_yield,
    })
    # Clear inputs
    st.session_state.ing_name = ""
    st.session_state.ing_qty = 100.0
    st.session_state.ing_yield = 100


def remove_ingredient(idx):
    """Remove ingredient from current dish"""
    if 0 <= idx < len(st.session_state.current_dish_ingredients):
        st.session_state.current_dish_ingredients.pop(idx)


def save_dish_to_menu(dish_name, total_cost, ingredients):
    """Save completed dish to the menu"""
    st.session_state.saved_dishes.append({
        'name': dish_name,
        'cost': total_cost,
        'ingredients': ingredients.copy(),
        'english_name': None
    })
    st.session_state.current_dish_ingredients = []


def remove_dish_from_menu(idx):
    """Remove dish from saved menu"""
    if 0 <= idx < len(st.session_state.saved_dishes):
        st.session_state.saved_dishes.pop(idx)


def reset_all():
    """Clear dishes and custom pantry"""
    st.session_state.saved_dishes = []
    st.session_state.current_dish_ingredients = []
    st.session_state.custom_pantry = {}
    st.session_state.selling_price = 24000


def add_to_pantry(name, cost, unit):
    """Add new ingredient to custom pantry"""
    st.session_state.custom_pantry[name] = {
        'cost_per_unit': cost, 
        'unit': unit, 
        'vendor': 'Custom',
        'original_name': name,
        'english_name': None
    }


# =============================================================================
# SIDEBAR - PANTRY MANAGEMENT
# =============================================================================
with st.sidebar:
    st.header("📦 Ingredient Pantry")
    st.caption("Auto-loaded from invoice data")
    
    all_pantry = {**st.session_state.pantry, **st.session_state.custom_pantry}
    
    if all_pantry:
        vendors = {}
        for name, info in all_pantry.items():
            vendor = info.get('vendor', 'Unknown')
            if vendor not in vendors:
                vendors[vendor] = []
            vendors[vendor].append((name, info))
        
        with st.expander(f"View Pantry ({len(all_pantry)} items)", expanded=False):
            for vendor, items in sorted(vendors.items()):
                st.markdown(f"**🏪 {vendor}**")
                for name, info in items:
                    eng_name = info.get('english_name')
                    orig_name = info.get('original_name', name)
                    
                    if eng_name and eng_name != orig_name:
                        st.markdown(f"• **{eng_name}**: ¥{info['cost_per_unit']:,}/{info['unit']}")
                        st.caption(f"  _{orig_name}_")
                    else:
                        st.markdown(f"• {orig_name}: ¥{info['cost_per_unit']:,}/{info['unit']}")
                st.divider()
    else:
        st.warning("No invoice data. Upload invoices in main app.")
    
    # Show translation status if exists
    if 'translate_message' in st.session_state and st.session_state.translate_message:
        if st.session_state.get('translate_success', False):
            st.success(st.session_state.translate_message)
        else:
            st.error(st.session_state.translate_message)
        # Clear after showing
        st.session_state.translate_message = None
    
    # Refresh and Translate buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Refresh", use_container_width=True):
            st.session_state.pantry = load_pantry_from_invoices()
            st.cache_data.clear()
            st.rerun()
    
    with col2:
        if st.button("🌐 Translate", use_container_width=True, help="AI translate ingredient names to English"):
            if not st.session_state.pantry:
                st.error("❌ Pantry is empty. Upload invoices in main app first.")
            else:
                st.info(f"🔍 Starting translation for {len(st.session_state.pantry)} items...")
                
                # Show items to translate
                items_needing_translation = [n for n, info in st.session_state.pantry.items() if not info.get('english_name')]
                st.info(f"📝 {len(items_needing_translation)} items need translation")
                
                if items_needing_translation:
                    with st.expander("Items to translate", expanded=True):
                        for name in items_needing_translation[:5]:
                            st.write(f"• {name}")
                        if len(items_needing_translation) > 5:
                            st.write(f"... and {len(items_needing_translation) - 5} more")
                
                # Call translation (without spinner to see debug output)
                st.info("🌐 Calling Claude API...")
                updated_pantry, message, success = translate_pantry_ingredients(st.session_state.pantry)
                
                # Show result immediately before rerun
                if success:
                    st.success(message)
                else:
                    st.error(message)
                
                st.session_state.pantry = updated_pantry
                st.session_state.translate_message = message
                st.session_state.translate_success = success
                
                # Add a button to manually rerun after seeing debug
                if st.button("🔄 Apply & Refresh"):
                    st.rerun()
    
    # Add custom ingredient
    with st.expander("➕ Add Custom Ingredient", expanded=False):
        new_pantry_name = st.text_input("Ingredient Name", key="pantry_name")
        new_pantry_cost = st.number_input("Cost per Unit (¥)", min_value=0, value=1000, key="pantry_cost")
        new_pantry_unit = st.selectbox("Unit", ['kg', 'g', '100g', 'L', 'ml', 'pc'], key="pantry_unit")
        if st.button("Add to Pantry"):
            if new_pantry_name:
                add_to_pantry(new_pantry_name, new_pantry_cost, new_pantry_unit)
                st.success(f"Added {new_pantry_name}")
                st.rerun()
    
    st.divider()
    
    # Reset button
    if st.button("🗑️ Reset All", type="secondary", use_container_width=True):
        reset_all()
        st.rerun()


# =============================================================================
# SECTION 1: DISH CALCULATOR
# =============================================================================
st.header("1️⃣ Dish Calculator / 料理原価計算")
st.markdown("Build a dish by adding ingredients and their quantities")

col1, col2 = st.columns([2, 1])

with col1:
    dish_name = st.text_input("Dish Name / 料理名", placeholder="e.g., Seasonal Fish Course")

with col2:
    # Quick-fill from pantry with on_change callback for syncing
    all_pantry = {**st.session_state.pantry, **st.session_state.custom_pantry}
    
    def format_option(key):
        if key == "-- Select --":
            return key
        info = all_pantry.get(key, {})
        eng = info.get('english_name')
        orig = info.get('original_name', key)
        price = info.get('cost_per_unit', 0)
        unit = info.get('unit', '')
        if eng and eng != orig:
            return f"{eng} - ¥{price:,}/{unit}"
        return f"{orig} - ¥{price:,}/{unit}"
    
    st.selectbox(
        "Quick-fill from Pantry",
        options=["-- Select --"] + sorted(all_pantry.keys()),
        format_func=format_option,
        key="pantry_selector",
        on_change=on_pantry_select
    )

# Ingredient input form with SYNCED inputs
st.subheader("Add Ingredients / 材料を追加")

cols = st.columns([3, 2, 1.5, 1.5, 1.5, 1])

with cols[0]:
    st.text_input("Ingredient", key="ing_name")

with cols[1]:
    st.number_input("Cost/Unit (¥)", min_value=0, key="ing_cost")

with cols[2]:
    unit_options = ['kg', 'g', '100g', 'L', 'ml', 'pc']
    current_unit = st.session_state.ing_unit
    default_idx = unit_options.index(current_unit) if current_unit in unit_options else 0
    st.selectbox("Unit", unit_options, index=default_idx, key="ing_unit")

with cols[3]:
    unit = st.session_state.ing_unit
    qty_label = "Qty (g)" if unit in ['kg', 'g', '100g'] else "Qty (ml)" if unit in ['L', 'ml'] else "Qty (pc)"
    st.number_input(qty_label, min_value=0.0, step=10.0, key="ing_qty")

with cols[4]:
    st.number_input("Yield %", min_value=1, max_value=100, key="ing_yield")

with cols[5]:
    st.write("")
    st.write("")
    if st.button("➕ Add", use_container_width=True):
        if st.session_state.ing_name:
            add_ingredient_to_dish()
            st.rerun()

# Display current dish ingredients
if st.session_state.current_dish_ingredients:
    st.subheader("📝 Current Dish Ingredients")
    
    table_data = []
    total_dish_cost = 0
    
    for idx, ing in enumerate(st.session_state.current_dish_ingredients):
        line_cost = calculate_ingredient_cost(
            ing['unit_cost'], ing['unit'], ing['quantity'], ing['yield_pct']
        )
        total_dish_cost += line_cost
        table_data.append({
            '#': idx + 1,
            'Ingredient': ing['name'],
            'Cost/Unit': f"¥{ing['unit_cost']:,}/{ing['unit']}",
            'Quantity': f"{ing['quantity']:.1f}",
            'Yield': f"{ing['yield_pct']}%",
            'Line Cost': f"¥{line_cost:,.0f}"
        })
    
    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Remove buttons
    cols = st.columns(len(st.session_state.current_dish_ingredients) + 1)
    for idx in range(len(st.session_state.current_dish_ingredients)):
        with cols[idx]:
            if st.button(f"🗑️ #{idx+1}", key=f"remove_{idx}"):
                remove_ingredient(idx)
                st.rerun()
    
    st.divider()
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.metric("💰 Total Dish Cost / 料理原価", f"¥{total_dish_cost:,.0f}")
    
    with col3:
        if st.button("✅ Save Dish to Menu", type="primary", use_container_width=True):
            if dish_name:
                save_dish_to_menu(dish_name, total_dish_cost, st.session_state.current_dish_ingredients)
                st.success(f"Saved '{dish_name}' to menu!")
                st.rerun()
            else:
                st.error("Please enter a dish name")
else:
    st.info("👆 Add ingredients above to build your dish")


# =============================================================================
# SECTION 2: MENU ASSEMBLER
# =============================================================================
st.divider()
st.header("2️⃣ Menu Assembler / メニュー構成")

if not st.session_state.saved_dishes:
    st.info("No dishes saved yet. Create dishes above and save them to build your menu.")
else:
    # Menu settings row
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        menu_type = st.selectbox(
            "Menu Type / メニュータイプ",
            ['Dinner', 'Lunch', 'Special'],
            key="menu_type_select"
        )
        st.session_state.menu_type = menu_type
    
    with col2:
        default_prices = {'Dinner': 24000, 'Lunch': 8500, 'Special': 32000}
        selling_price = st.number_input(
            "Selling Price (¥) / 販売価格",
            min_value=0,
            value=default_prices.get(menu_type, 24000),
            step=500,
            key="selling_price_input"
        )
        st.session_state.selling_price = selling_price
    
    with col3:
        target_cost_pct = st.slider("Target Food Cost %", min_value=20, max_value=50, value=30)
    
    st.subheader("📋 Menu Dishes / メニュー料理")
    
    # Display saved dishes
    total_menu_cost = 0
    dish_costs = []
    
    for idx, dish in enumerate(st.session_state.saved_dishes):
        total_menu_cost += dish['cost']
        
        # Use English name if available
        display_name = dish.get('english_name') or dish['name']
        dish_costs.append({'Dish': display_name, 'Cost': dish['cost']})
        
        col1, col2, col3 = st.columns([3, 1, 0.5])
        with col1:
            # Show both names if translated
            if dish.get('english_name') and dish['english_name'] != dish['name']:
                expander_title = f"**{dish['english_name']}** ({dish['name']}) - ¥{dish['cost']:,.0f}"
            else:
                expander_title = f"**{dish['name']}** - ¥{dish['cost']:,.0f}"
            
            with st.expander(expander_title):
                for ing in dish['ingredients']:
                    line_cost = calculate_ingredient_cost(
                        ing['unit_cost'], ing['unit'], ing['quantity'], ing['yield_pct']
                    )
                    st.caption(f"• {ing['name']}: {ing['quantity']:.0f}{ing['unit'][:1]} @ ¥{ing['unit_cost']:,}/{ing['unit']} = ¥{line_cost:,.0f}")
        
        with col2:
            st.metric("Cost", f"¥{dish['cost']:,.0f}", label_visibility="collapsed")
        
        with col3:
            if st.button("🗑️", key=f"del_dish_{idx}"):
                remove_dish_from_menu(idx)
                st.rerun()
    
    st.divider()
    
    # Summary metrics
    food_cost_pct = (total_menu_cost / selling_price * 100) if selling_price > 0 else 0
    gross_profit = selling_price - total_menu_cost
    gross_profit_pct = (gross_profit / selling_price * 100) if selling_price > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Selling Price / 販売価格", f"¥{selling_price:,}")
    
    with col2:
        st.metric("Total Food Cost / 原価合計", f"¥{total_menu_cost:,.0f}")
    
    with col3:
        delta_color = "inverse" if food_cost_pct > target_cost_pct else "normal"
        st.metric(
            "Food Cost %", 
            f"{food_cost_pct:.1f}%",
            delta=f"{food_cost_pct - target_cost_pct:+.1f}% vs target" if abs(food_cost_pct - target_cost_pct) > 0.5 else None,
            delta_color=delta_color
        )
    
    with col4:
        st.metric("Gross Profit / 粗利", f"¥{gross_profit:,.0f}", help=f"{gross_profit_pct:.1f}%")
    
    # Warning/Success
    if food_cost_pct > 40:
        st.error(f"⚠️ Food cost ({food_cost_pct:.1f}%) exceeds 40%! Consider reducing costs or increasing price.")
    elif food_cost_pct > target_cost_pct:
        st.warning(f"⚡ Food cost ({food_cost_pct:.1f}%) is above target ({target_cost_pct}%)")
    else:
        st.success(f"✅ Food cost ({food_cost_pct:.1f}%) is within target ({target_cost_pct}%)")
    
    # Charts
    if len(dish_costs) > 1:
        st.subheader("📊 Cost Breakdown by Dish")
        
        df_costs = pd.DataFrame(dish_costs)
        df_costs['Percentage'] = df_costs['Cost'] / df_costs['Cost'].sum() * 100
        
        fig = px.pie(
            df_costs, 
            values='Cost', 
            names='Dish',
            title='Food Cost Distribution',
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig.update_traces(
            textposition='inside',
            textinfo='percent+label',
            hovertemplate='<b>%{label}</b><br>Cost: ¥%{value:,.0f}<br>Share: %{percent}<extra></extra>'
        )
        fig.update_layout(height=400)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Bar chart
        st.subheader("📈 Cost Analysis")
        
        budget_per_dish = (selling_price * target_cost_pct / 100) / len(dish_costs)
        df_costs['Budget'] = budget_per_dish
        df_costs['Over Budget'] = df_costs['Cost'] > budget_per_dish
        
        fig2 = px.bar(
            df_costs,
            x='Dish',
            y='Cost',
            title='Dish Costs vs Average Budget',
            color='Over Budget',
            color_discrete_map={True: '#e74c3c', False: '#2ecc71'}
        )
        fig2.add_hline(
            y=budget_per_dish, 
            line_dash="dash", 
            line_color="orange",
            annotation_text=f"Avg Budget: ¥{budget_per_dish:,.0f}"
        )
        fig2.update_layout(height=350, showlegend=False)
        fig2.update_yaxes(tickprefix='¥', tickformat=',.0f')
        
        st.plotly_chart(fig2, use_container_width=True)


# =============================================================================
# FOOTER
# =============================================================================
st.divider()
all_pantry_count = len(st.session_state.pantry) + len(st.session_state.custom_pantry)
st.caption(f"Session: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Dishes: {len(st.session_state.saved_dishes)} | Pantry: {all_pantry_count} items")
