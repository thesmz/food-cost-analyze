"""
Dynamic Recipe & Menu Costing Tool
Build menus from scratch by calculating dish costs from ingredient breakdowns.
No hardcoded menus - fully dynamic session-based tool.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(
    page_title="Recipe & Menu Costing | The Shinmonzen",
    page_icon="🍽️",
    layout="wide"
)

st.title("🍽️ Recipe & Menu Costing Tool")
st.markdown("*Build menus by calculating dish costs from ingredient breakdowns*")

# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================
if 'pantry' not in st.session_state:
    # Start with empty pantry - user adds their own real prices
    # Only include items if we have actual invoice data
    st.session_state.pantry = {
        # Add your ingredients here with real costs from invoices
    }

if 'saved_dishes' not in st.session_state:
    st.session_state.saved_dishes = []  # List of {name, cost, ingredients}

if 'current_dish_ingredients' not in st.session_state:
    st.session_state.current_dish_ingredients = []  # Temp storage for dish being built

if 'menu_type' not in st.session_state:
    st.session_state.menu_type = 'Dinner'

if 'selling_price' not in st.session_state:
    st.session_state.selling_price = 24000


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def calculate_ingredient_cost(unit_cost, unit, quantity, yield_pct):
    """
    Calculate cost for an ingredient line.
    Converts units appropriately and applies yield adjustment.
    """
    if yield_pct <= 0:
        yield_pct = 100
    
    # Unit conversion factors to base unit
    # Cost is given per unit, quantity is in grams/ml/pieces
    unit_scales = {
        'kg': 1000,      # cost per kg, qty in g
        'g': 1,          # cost per g, qty in g
        '100g': 100,     # cost per 100g, qty in g
        'L': 1000,       # cost per L, qty in ml
        'ml': 1,         # cost per ml, qty in ml
        'pc': 1,         # cost per piece, qty in pieces
    }
    
    scale = unit_scales.get(unit, 1)
    
    # Cost = (unit_cost / scale) * quantity / (yield_pct / 100)
    cost = (unit_cost / scale) * quantity / (yield_pct / 100)
    return cost


def add_ingredient_to_dish():
    """Add current ingredient inputs to the dish being built"""
    st.session_state.current_dish_ingredients.append({
        'name': st.session_state.new_ing_name,
        'unit_cost': st.session_state.new_ing_cost,
        'unit': st.session_state.new_ing_unit,
        'quantity': st.session_state.new_ing_qty,
        'yield_pct': st.session_state.new_ing_yield,
    })


def remove_ingredient(idx):
    """Remove ingredient from current dish"""
    if 0 <= idx < len(st.session_state.current_dish_ingredients):
        st.session_state.current_dish_ingredients.pop(idx)


def save_dish_to_menu(dish_name, total_cost, ingredients):
    """Save completed dish to the menu"""
    st.session_state.saved_dishes.append({
        'name': dish_name,
        'cost': total_cost,
        'ingredients': ingredients.copy()
    })
    st.session_state.current_dish_ingredients = []


def remove_dish_from_menu(idx):
    """Remove dish from saved menu"""
    if 0 <= idx < len(st.session_state.saved_dishes):
        st.session_state.saved_dishes.pop(idx)


def reset_all():
    """Clear all session data"""
    st.session_state.saved_dishes = []
    st.session_state.current_dish_ingredients = []
    st.session_state.selling_price = 24000 if st.session_state.menu_type == 'Dinner' else 8500


def add_to_pantry(name, cost, unit):
    """Add new ingredient to pantry"""
    st.session_state.pantry[name] = {'cost_per_unit': cost, 'unit': unit}


# =============================================================================
# SIDEBAR - PANTRY MANAGEMENT
# =============================================================================
with st.sidebar:
    st.header("📦 Ingredient Pantry")
    st.caption("Save frequently used ingredients for quick access")
    
    # Display pantry
    if st.session_state.pantry:
        with st.expander("View Pantry", expanded=False):
            for name, info in st.session_state.pantry.items():
                st.caption(f"**{name}**: ¥{info['cost_per_unit']:,}/{info['unit']}")
    else:
        st.info("Pantry is empty. Add ingredients below using real costs from your invoices.")
    
    # Add to pantry
    with st.expander("➕ Add to Pantry", expanded=False):
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
    # Quick-fill from pantry
    pantry_selection = st.selectbox(
        "Quick-fill from Pantry",
        options=["-- Select --"] + list(st.session_state.pantry.keys())
    )

# Ingredient input form
st.subheader("Add Ingredients / 材料を追加")

cols = st.columns([3, 2, 1.5, 1.5, 1.5, 1])

with cols[0]:
    # Auto-fill if pantry item selected
    if pantry_selection and pantry_selection != "-- Select --":
        default_name = pantry_selection
        default_cost = st.session_state.pantry[pantry_selection]['cost_per_unit']
        default_unit = st.session_state.pantry[pantry_selection]['unit']
    else:
        default_name = ""
        default_cost = 1000
        default_unit = 'kg'
    
    ing_name = st.text_input("Ingredient", value=default_name, key="new_ing_name")

with cols[1]:
    ing_cost = st.number_input("Cost/Unit (¥)", min_value=0, value=default_cost, key="new_ing_cost")

with cols[2]:
    unit_options = ['kg', 'g', '100g', 'L', 'ml', 'pc']
    default_idx = unit_options.index(default_unit) if default_unit in unit_options else 0
    ing_unit = st.selectbox("Unit", unit_options, index=default_idx, key="new_ing_unit")

with cols[3]:
    # Quantity label changes based on unit
    qty_label = "Qty (g)" if ing_unit in ['kg', 'g', '100g'] else "Qty (ml)" if ing_unit in ['L', 'ml'] else "Qty (pc)"
    ing_qty = st.number_input(qty_label, min_value=0.0, value=100.0, step=10.0, key="new_ing_qty")

with cols[4]:
    ing_yield = st.number_input("Yield %", min_value=1, max_value=100, value=100, key="new_ing_yield")

with cols[5]:
    st.write("")  # Spacer
    st.write("")  # Spacer
    if st.button("➕ Add", use_container_width=True):
        if ing_name:
            add_ingredient_to_dish()
            st.rerun()

# Display current dish ingredients
if st.session_state.current_dish_ingredients:
    st.subheader("📝 Current Dish Ingredients")
    
    # Build table
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
    
    # Display table
    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Remove ingredient buttons
    cols = st.columns(len(st.session_state.current_dish_ingredients) + 1)
    for idx in range(len(st.session_state.current_dish_ingredients)):
        with cols[idx]:
            if st.button(f"🗑️ Remove #{idx+1}", key=f"remove_{idx}"):
                remove_ingredient(idx)
                st.rerun()
    
    # Total and Save
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
    # Menu type and selling price
    col1, col2, col3 = st.columns(3)
    
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
        target_cost_pct = st.slider(
            "Target Food Cost %",
            min_value=20, max_value=50, value=30
        )
    
    st.subheader("📋 Menu Dishes / メニュー料理")
    
    # Display saved dishes
    total_menu_cost = 0
    dish_costs = []
    
    for idx, dish in enumerate(st.session_state.saved_dishes):
        total_menu_cost += dish['cost']
        dish_costs.append({'Dish': dish['name'], 'Cost': dish['cost']})
        
        col1, col2, col3 = st.columns([3, 1, 0.5])
        with col1:
            with st.expander(f"**{dish['name']}** - ¥{dish['cost']:,.0f}"):
                for ing in dish['ingredients']:
                    line_cost = calculate_ingredient_cost(
                        ing['unit_cost'], ing['unit'], ing['quantity'], ing['yield_pct']
                    )
                    st.caption(f"• {ing['name']}: {ing['quantity']}{ing['unit'][:1]} @ ¥{ing['unit_cost']:,}/{ing['unit']} = ¥{line_cost:,.0f}")
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
    
    # Pie chart - Cost breakdown by dish
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
        
        # Bar chart showing cost vs budget
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
st.caption(f"Session started: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Dishes: {len(st.session_state.saved_dishes)} | Pantry items: {len(st.session_state.pantry)}")
