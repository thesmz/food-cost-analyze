"""
Dynamic Recipe & Menu Costing Tool
Split-panel UI: Pantry Explorer (left) + Recipe Canvas (right)
With AI translation support for ingredient names.
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
from config import YIELD_RATES, get_total_yield

st.set_page_config(
    page_title="Recipe & Menu Costing | The Shinmonzen",
    page_icon="🍽️",
    layout="wide"
)

# =============================================================================
# HELPER: Get API Key from various secret locations
# =============================================================================
def get_anthropic_api_key():
    """Try to get ANTHROPIC_API_KEY from multiple secret locations"""
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
    
    return None


# =============================================================================
# TRANSLATION FUNCTION (Using Claude API)
# =============================================================================
def translate_pantry_ingredients(pantry_dict):
    """
    Translate pantry ingredient names from Japanese to meaningful English using Claude API.
    Smart translation - understands culinary context.
    """
    import requests
    import json
    
    if not pantry_dict:
        return pantry_dict, "❌ Pantry is empty.", False
    
    # Get API key
    api_key = get_anthropic_api_key()
    if not api_key:
        return pantry_dict, "❌ ANTHROPIC_API_KEY not found. Add to secrets (root level or under [supabase]).", False
    
    # Collect names needing translation
    names_to_translate = [name for name, info in pantry_dict.items() if not info.get('english_name')]
    
    if not names_to_translate:
        return pantry_dict, "ℹ️ All ingredients already translated.", True
    
    # Build prompt
    prompt = f"""You are a culinary expert translator. Translate these Japanese food ingredient names to clear, meaningful English.

RULES:
1. DO NOT just transliterate - understand what the ingredient IS
2. For French/Italian names in katakana, identify the actual product (butter, cheese, etc.)
3. Be concise but clear - a chef should know what this is
4. Include (Salted), (Fresh), size if relevant

Examples:
- "ﾊﾟﾚｯﾄ ﾛﾝﾄﾞ ﾄﾞ ﾌﾞｰﾙ ﾄﾞ ﾊﾞﾗｯﾄ ﾃﾞﾐｾﾙ（有塩）" → "Churned Butter (Lightly Salted)"
- "KAVIARI キャビア クリスタル100g セレクションJG" → "KAVIARI Crystal Caviar 100g"
- "和牛ヒレ" → "Wagyu Beef Tenderloin"

Ingredients:
{json.dumps(names_to_translate, ensure_ascii=False)}

Return ONLY valid JSON: {{"original": "English"}}"""

    try:
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
        
        if response.status_code == 200:
            import re
            content = response.json()['content'][0]['text'].strip()
            
            # Clean markdown if present
            if content.startswith('```'):
                content = re.sub(r'^```(?:json)?\s*', '', content)
                content = re.sub(r'\s*```$', '', content)
            
            try:
                translations = json.loads(content)
            except:
                match = re.search(r'\{[\s\S]*\}', content)
                if match:
                    translations = json.loads(match.group())
                else:
                    return pantry_dict, "❌ Could not parse API response.", False
            
            # Apply translations
            count = 0
            for name in pantry_dict:
                if name in translations:
                    pantry_dict[name]['english_name'] = translations[name]
                    count += 1
            
            return pantry_dict, f"✅ Translated {count} ingredients!", True
        else:
            return pantry_dict, f"❌ API error {response.status_code}", False
            
    except Exception as e:
        return pantry_dict, f"❌ Error: {str(e)[:100]}", False


# =============================================================================
# HELPER: Get Default Yield from Config
# =============================================================================
def get_default_yield_for_ingredient(item_name: str, category: str) -> int:
    """
    Get default TOTAL yield percentage from YIELD_RATES based on ingredient name/category.
    TOTAL yield = butchery × cooking (raw → cooked)
    """
    item_lower = item_name.lower()
    
    # Check by specific ingredient patterns
    if any(x in item_lower for x in ['beef', 'tenderloin', 'wagyu', 'ヒレ', '牛']):
        return int(get_total_yield('beef_tenderloin') * 100)
    elif any(x in item_lower for x in ['caviar', 'キャビア']):
        return int(get_total_yield('caviar') * 100)
    elif any(x in item_lower for x in ['fillet', 'フィレ', '切身']):
        return int(get_total_yield('fish_fillet') * 100)
    elif any(x in item_lower for x in ['whole', '丸', 'うに', '蛤']):
        return int(get_total_yield('fish_whole') * 100)
    elif any(x in item_lower for x in ['shellfish', 'crab', 'lobster', '海老', '蟹']):
        return int(get_total_yield('shellfish') * 100)
    elif any(x in item_lower for x in ['fish', '魚', '鮪', '鯛', 'salmon', 'サーモン']):
        return int(get_total_yield('fish_fillet') * 100)
    
    # Check by category
    if category == 'Meat':
        return int(get_total_yield('beef_tenderloin') * 100)
    elif category == 'Seafood':
        return int(get_total_yield('fish_fillet') * 100)
    elif category == 'Produce':
        return int(get_total_yield('vegetables') * 100)
    elif category == 'Dairy':
        return int(get_total_yield('caviar') * 100)  # Dairy usually 100%
    
    # Default
    return int(get_total_yield('default') * 100)


# =============================================================================
# LOAD PANTRY FROM INVOICES
# =============================================================================
@st.cache_data(ttl=300)
def load_pantry_from_invoices():
    """
    Load ingredient prices from invoice data.
    Keeps only the MOST RECENT price for each unique ingredient.
    """
    # Import vendor name mapper from utils
    try:
        from utils import get_clean_vendor_name
    except ImportError:
        def get_clean_vendor_name(name):
            return name
    
    supabase = init_supabase()
    if not supabase:
        return {}
    
    db_min, db_max = get_date_range(supabase)
    if not db_min or not db_max:
        return {}
    
    invoices_df = load_invoices(supabase, db_min, db_max)
    if invoices_df.empty:
        return {}
    
    # Sort by date descending so most recent comes first
    if 'date' in invoices_df.columns:
        invoices_df = invoices_df.sort_values('date', ascending=False)
    
    pantry = {}
    for _, row in invoices_df.iterrows():
        item_name = row.get('item_name', '')
        if not item_name:
            continue
        
        # Skip if we already have this item (we want the most recent, which comes first)
        if item_name in pantry:
            continue
        
        # Determine category based on patterns
        category = 'Other'
        item_lower = item_name.lower()
        if any(x in item_lower for x in ['牛', 'ヒレ', 'beef', 'wagyu', '肉', 'duck', '鴨', 'pork', '豚']):
            category = 'Meat'
        elif any(x in item_lower for x in ['キャビア', 'caviar', 'kaviari', '魚', 'fish', 'うに', '鮪', '鯛', 'サーモン', 'ホタテ', '蛤', '海老']):
            category = 'Seafood'
        elif any(x in item_lower for x in ['バター', 'butter', 'ブール', 'チーズ', 'cheese', 'cream', 'クリーム', 'milk', '牛乳']):
            category = 'Dairy'
        elif any(x in item_lower for x in ['ヴィネガー', 'vinegar', 'オイル', 'oil', 'sauce', 'ソース']):
            category = 'Condiments'
        elif any(x in item_lower for x in ['ジロール', 'mushroom', 'きのこ', 'truffle', 'トリュフ', '野菜', 'vegetable']):
            category = 'Produce'
        
        # Clean vendor name using mapping
        vendor_raw = row.get('vendor', 'Unknown')
        vendor = get_clean_vendor_name(vendor_raw)
        
        # Calculate cost per unit
        qty = float(row.get('quantity', 1) or 1)
        amount = float(row.get('amount', 0) or 0)
        unit = row.get('unit', 'pc') or 'pc'
        
        cost_per_unit = amount / qty if qty > 0 else amount
        
        # Add to pantry (most recent price)
        pantry[item_name] = {
            'cost_per_unit': cost_per_unit,
            'unit': unit,
            'vendor': vendor,
            'category': category,
            'english_name': None,
            'last_date': str(row.get('date', ''))
        }
    
    return pantry


# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================
if 'pantry' not in st.session_state:
    st.session_state.pantry = load_pantry_from_invoices()
if 'current_dish_name' not in st.session_state:
    st.session_state.current_dish_name = ""
if 'current_ingredients' not in st.session_state:
    st.session_state.current_ingredients = []
if 'saved_dishes' not in st.session_state:
    st.session_state.saved_dishes = []
if 'selected_pantry_item' not in st.session_state:
    st.session_state.selected_pantry_item = None
if 'transfer_qty' not in st.session_state:
    st.session_state.transfer_qty = 100
if 'transfer_yield' not in st.session_state:
    st.session_state.transfer_yield = 100


# =============================================================================
# MAIN LAYOUT: Split Panel
# =============================================================================
st.title("🍽️ Recipe & Menu Costing Tool")

# Top toolbar
toolbar_col1, toolbar_col2, toolbar_col3, toolbar_col4 = st.columns([1, 1, 1, 1])
with toolbar_col1:
    if st.button("🔄 Refresh Pantry", use_container_width=True):
        st.session_state.pantry = load_pantry_from_invoices()
        st.cache_data.clear()
        st.rerun()
with toolbar_col2:
    if st.button("🌐 AI Translate", use_container_width=True):
        with st.spinner("Translating with Claude AI..."):
            updated, msg, success = translate_pantry_ingredients(st.session_state.pantry)
            st.session_state.pantry = updated
            if success:
                st.success(msg)
            else:
                st.error(msg)
with toolbar_col3:
    if st.button("🗑️ Clear Recipe", use_container_width=True):
        st.session_state.current_ingredients = []
        st.session_state.current_dish_name = ""
        st.rerun()
with toolbar_col4:
    pantry_count = len(st.session_state.pantry)
    st.metric("Pantry Items", pantry_count)

st.divider()

# =============================================================================
# SPLIT PANEL: Left (Pantry) | Right (Recipe Canvas)
# =============================================================================
left_panel, right_panel = st.columns([0.65, 0.35])

# =============================================================================
# LEFT PANEL: PANTRY EXPLORER
# =============================================================================
with left_panel:
    st.subheader("📦 Pantry Explorer")
    
    pantry = st.session_state.pantry
    
    if not pantry:
        st.warning("No pantry data. Upload invoices in the main app first.")
    else:
        # Build DataFrame for filtering
        pantry_data = []
        for name, info in pantry.items():
            display_name = info.get('english_name') or name
            pantry_data.append({
                'Name': display_name,
                'Original': name,
                'Vendor': info.get('vendor', 'Unknown'),
                'Category': info.get('category', 'Other'),
                'Price': info.get('cost_per_unit', 0),
                'Unit': info.get('unit', 'pc'),
            })
        
        pantry_df = pd.DataFrame(pantry_data)
        
        # --- FILTERS ---
        st.markdown("**Filters**")
        filter_col1, filter_col2 = st.columns(2)
        
        with filter_col1:
            vendors = ['All'] + sorted(pantry_df['Vendor'].unique().tolist())
            selected_vendor = st.selectbox("Vendor", vendors, key="vendor_filter")
        
        with filter_col2:
            categories = ['All'] + sorted(pantry_df['Category'].unique().tolist())
            selected_category = st.selectbox("Category", categories, key="category_filter")
        
        # Search box
        search_term = st.text_input("🔍 Search ingredients", key="search_input", placeholder="Type to search...")
        
        # Apply filters
        filtered_df = pantry_df.copy()
        if selected_vendor != 'All':
            filtered_df = filtered_df[filtered_df['Vendor'] == selected_vendor]
        if selected_category != 'All':
            filtered_df = filtered_df[filtered_df['Category'] == selected_category]
        if search_term:
            mask = (
                filtered_df['Name'].str.contains(search_term, case=False, na=False) |
                filtered_df['Original'].str.contains(search_term, case=False, na=False)
            )
            filtered_df = filtered_df[mask]
        
        st.caption(f"Showing {len(filtered_df)} of {len(pantry_df)} items")
        
        # --- RESULTS TABLE ---
        if not filtered_df.empty:
            # Format for display
            display_df = filtered_df[['Name', 'Vendor', 'Price', 'Unit']].copy()
            display_df['Price'] = display_df['Price'].apply(lambda x: f"¥{x:,.0f}")
            
            # Show as interactive table
            st.dataframe(
                display_df,
                hide_index=True,
                height=250,
                use_container_width=True
            )
            
            # --- SELECT ITEM ---
            st.markdown("**Select Item to Transfer**")
            item_options = filtered_df['Name'].tolist()
            selected_item_name = st.selectbox(
                "Choose ingredient",
                options=item_options,
                key="pantry_select",
                label_visibility="collapsed"
            )
            
            if selected_item_name:
                # Find the original name
                row = filtered_df[filtered_df['Name'] == selected_item_name].iloc[0]
                original_name = row['Original']
                item_info = pantry[original_name]
                
                st.session_state.selected_pantry_item = {
                    'name': selected_item_name,
                    'original_name': original_name,
                    'info': item_info
                }
                
                # Show preview card
                st.markdown("---")
                st.markdown(f"**Selected:** {selected_item_name}")
                if selected_item_name != original_name:
                    st.caption(f"_{original_name}_")
                
                prev_col1, prev_col2 = st.columns(2)
                with prev_col1:
                    st.metric("Price", f"¥{item_info['cost_per_unit']:,.0f}")
                with prev_col2:
                    st.metric("Unit", item_info['unit'])
                
                # Transfer controls
                st.markdown("**Transfer Settings**")
                
                # Get default yield based on ingredient
                default_yield = get_default_yield_for_ingredient(
                    selected_item_name, 
                    item_info.get('category', 'Other')
                )
                
                trans_col1, trans_col2 = st.columns(2)
                with trans_col1:
                    transfer_qty = st.number_input(
                        "Usable/Cooked Amount (g)",
                        min_value=1,
                        value=st.session_state.transfer_qty,
                        step=10,
                        key="transfer_qty_input",
                        help="Amount that goes on the plate (after trimming & cooking)"
                    )
                with trans_col2:
                    transfer_yield = st.number_input(
                        "Total Yield %",
                        min_value=1,
                        max_value=100,
                        value=default_yield,
                        step=5,
                        key="transfer_yield_input",
                        help=f"Raw → Cooked yield. {default_yield}% means 100g raw → {default_yield}g cooked"
                    )
                
                # Calculate cost preview
                unit = item_info['unit']
                cost_per_unit = item_info['cost_per_unit']
                
                # Convert based on unit to get cost per gram of RAW product
                if unit == 'kg':
                    raw_cost_per_gram = cost_per_unit / 1000
                elif unit == '100g':
                    raw_cost_per_gram = cost_per_unit / 100
                elif unit == 'L':
                    raw_cost_per_gram = cost_per_unit / 1000
                else:
                    raw_cost_per_gram = cost_per_unit  # pc, etc.
                
                # Calculate: usable_qty → raw_needed → cost
                yield_decimal = transfer_yield / 100
                raw_qty_needed = transfer_qty / yield_decimal if yield_decimal > 0 else transfer_qty
                total_cost = raw_qty_needed * raw_cost_per_gram
                
                # Show breakdown
                st.caption(f"📐 {transfer_qty}g cooked ÷ {transfer_yield}% yield = **{raw_qty_needed:.0f}g raw** needed")
                st.info(f"💰 Cost: {raw_qty_needed:.0f}g × ¥{raw_cost_per_gram:.1f}/g = **¥{total_cost:,.0f}**")
                
                # TRANSFER BUTTON
                if st.button("➡️ TRANSFER TO RECIPE", type="primary", use_container_width=True):
                    new_ingredient = {
                        'name': selected_item_name,
                        'original_name': original_name,
                        'quantity': transfer_qty,  # Usable/cooked amount
                        'raw_qty': raw_qty_needed,
                        'unit': 'g',
                        'yield_pct': transfer_yield,
                        'cost': total_cost,
                    }
                    st.session_state.current_ingredients.append(new_ingredient)
                    st.success(f"Added {selected_item_name}!")
                    st.rerun()
        else:
            st.info("No items match your filters.")


# =============================================================================
# RIGHT PANEL: RECIPE CANVAS
# =============================================================================
with right_panel:
    st.subheader("👨‍🍳 Recipe Canvas")
    
    # Dish name input
    dish_name = st.text_input(
        "Dish Name / 料理名",
        value=st.session_state.current_dish_name,
        placeholder="e.g., Autumn Amuse Bouche",
        key="dish_name_input"
    )
    st.session_state.current_dish_name = dish_name
    
    st.markdown("---")
    
    # Current ingredients
    st.markdown("**Current Ingredients**")
    
    ingredients = st.session_state.current_ingredients
    
    if not ingredients:
        st.info("👈 Select ingredients from Pantry Explorer and transfer them here")
    else:
        # Build ingredients table
        ing_data = []
        for i, ing in enumerate(ingredients):
            ing_data.append({
                'Ingredient': ing['name'],
                'Qty': f"{ing['quantity']}g",
                'Yield': f"{ing['yield_pct']}%",
                'Cost': f"¥{ing['cost']:,.0f}",
                'idx': i
            })
        
        ing_df = pd.DataFrame(ing_data)
        
        # Display with remove buttons
        for i, ing in enumerate(ingredients):
            col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 0.5])
            with col1:
                st.write(ing['name'])
            with col2:
                st.write(f"{ing['quantity']}g")
            with col3:
                st.write(f"{ing['yield_pct']}%")
            with col4:
                st.write(f"¥{ing['cost']:,.0f}")
            with col5:
                if st.button("🗑️", key=f"remove_{i}"):
                    st.session_state.current_ingredients.pop(i)
                    st.rerun()
        
        st.markdown("---")
        
        # Totals
        total_cost = sum(ing['cost'] for ing in ingredients)
        
        total_col1, total_col2 = st.columns(2)
        with total_col1:
            st.metric("Total Dish Cost", f"¥{total_cost:,.0f}")
        with total_col2:
            # Show food cost % if selling price set
            if 'selling_price' in st.session_state and st.session_state.selling_price > 0:
                food_cost_pct = (total_cost / st.session_state.selling_price) * 100
                color = "normal" if food_cost_pct <= 35 else "inverse"
                st.metric("Food Cost %", f"{food_cost_pct:.1f}%", delta_color=color)
        
        st.markdown("---")
        
        # Save dish button
        save_col1, save_col2 = st.columns(2)
        with save_col1:
            if st.button("✅ Save Dish to Menu", type="primary", use_container_width=True):
                if dish_name:
                    new_dish = {
                        'name': dish_name,
                        'ingredients': ingredients.copy(),
                        'cost': total_cost,
                        'created': datetime.now().strftime("%Y-%m-%d %H:%M")
                    }
                    st.session_state.saved_dishes.append(new_dish)
                    st.session_state.current_ingredients = []
                    st.session_state.current_dish_name = ""
                    st.success(f"Saved '{dish_name}' to menu!")
                    st.rerun()
                else:
                    st.error("Please enter a dish name")
        
        with save_col2:
            if st.button("🗑️ Clear All", use_container_width=True):
                st.session_state.current_ingredients = []
                st.rerun()


# =============================================================================
# SECTION 2: MENU ASSEMBLER
# =============================================================================
st.divider()
st.header("2️⃣ Menu Assembler / メニュー構成")

if not st.session_state.saved_dishes:
    st.info("No dishes saved yet. Create dishes above and save them to build your menu.")
else:
    # Menu settings
    menu_col1, menu_col2, menu_col3 = st.columns(3)
    
    with menu_col1:
        menu_type = st.selectbox(
            "Menu Type",
            ['Dinner Tasting', 'Lunch Tasting', 'A la Carte'],
            key="menu_type"
        )
    
    with menu_col2:
        default_prices = {'Dinner Tasting': 24000, 'Lunch Tasting': 8500, 'A la Carte': 5000}
        selling_price = st.number_input(
            "Selling Price (¥)",
            min_value=0,
            value=default_prices.get(menu_type, 24000),
            step=500,
            key="selling_price"
        )
    
    with menu_col3:
        target_cost = st.slider("Target Food Cost %", 20, 50, 30)
    
    st.markdown("---")
    
    # Display saved dishes
    total_menu_cost = 0
    
    for i, dish in enumerate(st.session_state.saved_dishes):
        total_menu_cost += dish['cost']
        
        dish_col1, dish_col2, dish_col3 = st.columns([3, 1, 0.5])
        with dish_col1:
            with st.expander(f"**{dish['name']}** - ¥{dish['cost']:,.0f}"):
                for ing in dish['ingredients']:
                    st.write(f"• {ing['name']}: {ing['quantity']}g @ {ing['yield_pct']}% yield = ¥{ing['cost']:,.0f}")
        with dish_col2:
            st.write(f"¥{dish['cost']:,.0f}")
        with dish_col3:
            if st.button("🗑️", key=f"del_dish_{i}"):
                st.session_state.saved_dishes.pop(i)
                st.rerun()
    
    st.markdown("---")
    
    # Menu totals
    result_col1, result_col2, result_col3 = st.columns(3)
    
    with result_col1:
        st.metric("Total Menu Cost", f"¥{total_menu_cost:,.0f}")
    
    with result_col2:
        if selling_price > 0:
            actual_cost_pct = (total_menu_cost / selling_price) * 100
            delta = actual_cost_pct - target_cost
            st.metric(
                "Actual Food Cost %",
                f"{actual_cost_pct:.1f}%",
                delta=f"{delta:+.1f}%",
                delta_color="inverse"
            )
    
    with result_col3:
        gross_profit = selling_price - total_menu_cost
        st.metric("Gross Profit", f"¥{gross_profit:,.0f}")
    
    # Visualization
    if st.session_state.saved_dishes:
        st.subheader("📊 Cost Breakdown")
        
        chart_data = pd.DataFrame([
            {'Dish': d['name'], 'Cost': d['cost']}
            for d in st.session_state.saved_dishes
        ])
        
        fig = px.pie(
            chart_data,
            values='Cost',
            names='Dish',
            title='Cost Distribution by Dish'
        )
        st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# FOOTER
# =============================================================================
st.divider()
st.caption("💡 Tip: Use 🌐 AI Translate to convert Japanese ingredient names to English")
