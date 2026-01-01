"""
Menu Engineering - BCG Matrix Analysis
A la Carte items only (excludes Tasting Menus, Courses, Beverages)

IMPORTANT: Food costs are calculated from:
1. Default percentage (user-adjustable slider)
2. Custom costs (user can input actual costs for specific items)

NO FAKE HARDCODED VALUES - we don't know your actual costs!
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import init_supabase, load_sales, get_date_range, get_data_summary

st.set_page_config(page_title="Menu Engineering | The Shinmonzen", page_icon="📈", layout="wide")

st.title("📈 Menu Engineering / メニュー分析")
st.markdown("**BCG Matrix Analysis** - A La Carte Items Only (No Beverages)")


def is_valid_item_name(name) -> bool:
    """Check if item name is valid"""
    if pd.isna(name):
        return False
    name_str = str(name).strip()
    if not name_str or len(name_str) <= 2:
        return False
    if all(c in '-_. ' for c in name_str):
        return False
    cleaned = name_str.replace(',', '').replace('.', '').replace(' ', '').replace('-', '')
    if cleaned.isdigit():
        return False
    invalid_names = ['carte', 'a la carte', 'dinner', 'lunch', 'breakfast', 'dessert', 'course', 'open food']
    if name_str.lower() in invalid_names:
        return False
    return True


# Initialize Supabase
supabase = init_supabase()

# Initialize session state for custom food costs
if 'custom_food_costs' not in st.session_state:
    st.session_state.custom_food_costs = {}

# Sidebar
with st.sidebar:
    st.header("📈 Menu Engineering")
    
    if supabase:
        summary = get_data_summary(supabase)
        st.success(f"✅ Connected")
        st.caption(f"📊 {summary.get('sales_count', 0)} sales records")
    else:
        st.error("❌ Database not connected")
    
    st.divider()
    
    # Settings
    st.subheader("⚙️ Settings")
    min_qty = st.number_input("Min Qty Sold / 最小販売数", min_value=1, value=5)
    
    st.markdown("---")
    st.subheader("💰 Food Cost %")
    st.caption("Set your estimated food cost percentage:")
    
    default_cost_pct = st.slider(
        "Default Food Cost %", 
        min_value=15, 
        max_value=50, 
        value=30,
        help="Applied to all items without custom cost set"
    )
    
    st.info(f"Using **{default_cost_pct}%** for margin calculation")

# Load sales data
sales_df = pd.DataFrame()
if supabase:
    db_min, db_max = get_date_range(supabase)
    if db_min and db_max:
        sales_df = load_sales(supabase, db_min, db_max)

if sales_df.empty:
    st.warning("No sales data available. Please upload data in the main app.")
    st.stop()

# STRICT FILTER: Only 'A la carte' category, exclude Beverages
if 'category' not in sales_df.columns:
    st.error("Category column not found in sales data")
    st.stop()

# Filter to A la carte only
alacarte_df = sales_df[sales_df['category'] == 'A la carte'].copy()

# Exclude Beverages (check department column if exists)
if 'department' in alacarte_df.columns:
    alacarte_df = alacarte_df[~alacarte_df['department'].str.contains('Beverage', case=False, na=False)]

if alacarte_df.empty:
    st.warning("No 'A la carte' items found in the data (excluding Beverages).")
    available_categories = sorted(sales_df['category'].dropna().unique().tolist())
    st.info(f"Categories in data: {', '.join(available_categories)}")
    st.stop()

# Filter valid item names
filtered_df = alacarte_df[alacarte_df['name'].apply(is_valid_item_name)]

if filtered_df.empty:
    st.warning("No valid A la carte items found after filtering.")
    st.stop()

# Aggregate by item
item_sales = filtered_df.groupby('name').agg({
    'qty': 'sum',
    'net_total': 'sum',
    'price': 'mean'
}).reset_index()

item_sales = item_sales[item_sales['qty'] >= min_qty]

if item_sales.empty:
    st.warning(f"No items with qty >= {min_qty}")
    st.stop()

# Option to set custom food costs
with st.expander("💰 Set Custom Food Costs (Optional)", expanded=False):
    st.caption("If you know the actual food cost for specific items, enter them here:")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        item_options = item_sales['name'].tolist()
        selected_item = st.selectbox("Select Item", item_options)
    
    if selected_item:
        current_row = item_sales[item_sales['name'] == selected_item].iloc[0]
        current_price = current_row['price'] if current_row['price'] > 0 else (current_row['net_total'] / current_row['qty'])
        
        with col2:
            custom_cost = st.number_input(
                "Food Cost (¥)", 
                min_value=0, 
                max_value=int(current_price) + 1000,
                value=st.session_state.custom_food_costs.get(selected_item, int(current_price * default_cost_pct / 100))
            )
        with col3:
            st.metric("Selling Price", f"¥{current_price:,.0f}")
            if st.button("✅ Set Cost"):
                st.session_state.custom_food_costs[selected_item] = custom_cost
                st.success(f"Set!")
                st.rerun()
    
    if st.session_state.custom_food_costs:
        st.markdown("**Custom costs set:**")
        for item, cost in list(st.session_state.custom_food_costs.items()):
            col_a, col_b = st.columns([4, 1])
            with col_a:
                st.write(f"• {item}: ¥{cost:,}")
            with col_b:
                if st.button("🗑️", key=f"rm_{item}"):
                    del st.session_state.custom_food_costs[item]
                    st.rerun()

# Calculate metrics
menu_data = []
for _, row in item_sales.iterrows():
    item_name = row['name']
    qty_sold = row['qty']
    total_revenue = row['net_total']
    avg_price = row['price'] if row['price'] > 0 else (total_revenue / qty_sold if qty_sold > 0 else 0)
    selling_price = avg_price
    
    # Food cost: custom if set, otherwise default percentage
    if item_name in st.session_state.custom_food_costs:
        food_cost = st.session_state.custom_food_costs[item_name]
        cost_source = "Custom"
    else:
        food_cost = selling_price * (default_cost_pct / 100)
        cost_source = f"{default_cost_pct}%"
    
    unit_margin = selling_price - food_cost
    
    menu_data.append({
        'Item': item_name,
        'Qty Sold': qty_sold,
        'Selling Price': selling_price,
        'Food Cost': food_cost,
        'Cost Source': cost_source,
        'Unit Margin': unit_margin,
        'Total Revenue': total_revenue,
        'Total Contribution': unit_margin * qty_sold,
    })

menu_df = pd.DataFrame(menu_data)

st.info(f"📊 Analyzing **{len(menu_df)}** A la carte items | Default Food Cost: **{default_cost_pct}%**")

# Calculate averages
avg_qty = menu_df['Qty Sold'].mean()
avg_margin = menu_df['Unit Margin'].mean()

# Classify items
def classify(row):
    high_qty = row['Qty Sold'] >= avg_qty
    high_margin = row['Unit Margin'] >= avg_margin
    if high_qty and high_margin:
        return '⭐ Star'
    elif high_qty and not high_margin:
        return '🐴 Plowhorse'
    elif not high_qty and high_margin:
        return '❓ Puzzle'
    else:
        return '🐕 Dog'

menu_df['Quadrant'] = menu_df.apply(classify, axis=1)

# Create scatter plot
fig = go.Figure()

quadrant_style = {
    '⭐ Star': {'color': '#FFD700', 'symbol': 'star'},
    '🐴 Plowhorse': {'color': '#4CAF50', 'symbol': 'circle'},
    '❓ Puzzle': {'color': '#2196F3', 'symbol': 'diamond'},
    '🐕 Dog': {'color': '#9E9E9E', 'symbol': 'circle'}
}

for quadrant, style in quadrant_style.items():
    df_q = menu_df[menu_df['Quadrant'] == quadrant]
    if not df_q.empty:
        fig.add_trace(go.Scatter(
            x=df_q['Qty Sold'],
            y=df_q['Unit Margin'],
            mode='markers',
            name=quadrant,
            marker=dict(
                size=12, 
                color=style['color'], 
                symbol=style['symbol'],
                line=dict(width=1, color='white')
            ),
            text=df_q['Item'],
            hovertemplate='<b>%{text}</b><br>Qty: %{x:,.0f}<br>Margin: ¥%{y:,.0f}<extra></extra>'
        ))

# Add quadrant dividing lines
fig.add_hline(y=avg_margin, line_dash="dash", line_color="rgba(0,0,0,0.3)", line_width=2)
fig.add_vline(x=avg_qty, line_dash="dash", line_color="rgba(0,0,0,0.3)", line_width=2)

# Add quadrant labels
max_margin = menu_df['Unit Margin'].max()
min_margin = menu_df['Unit Margin'].min()
max_qty = menu_df['Qty Sold'].max()

fig.add_annotation(x=avg_qty*0.3, y=max_margin*0.95, 
                   text="❓ Puzzle", showarrow=False, font=dict(size=11, color="gray"))
fig.add_annotation(x=max_qty*0.85, y=max_margin*0.95, 
                   text="⭐ Star", showarrow=False, font=dict(size=11, color="gray"))
fig.add_annotation(x=avg_qty*0.3, y=min_margin + (avg_margin - min_margin)*0.1, 
                   text="🐕 Dog", showarrow=False, font=dict(size=11, color="gray"))
fig.add_annotation(x=max_qty*0.85, y=min_margin + (avg_margin - min_margin)*0.1, 
                   text="🐴 Plowhorse", showarrow=False, font=dict(size=11, color="gray"))

fig.update_layout(
    title=f"Menu Engineering Matrix | Avg Qty: {avg_qty:.0f} | Avg Margin: ¥{avg_margin:,.0f}",
    xaxis_title="Popularity (Qty Sold)",
    yaxis_title="Profitability (Unit Margin ¥)",
    height=500,
    showlegend=True,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    plot_bgcolor='white',
    xaxis=dict(gridcolor='rgba(0,0,0,0.1)', zeroline=False),
    yaxis=dict(gridcolor='rgba(0,0,0,0.1)', zeroline=False, tickformat=',.0f', tickprefix='¥')
)

st.plotly_chart(fig, use_container_width=True)

st.caption("💡 Hover over points to see dish names")

# Quadrant guide
st.markdown("""
### 📖 Quadrant Guide

| Quadrant | Meaning | Action |
|----------|---------|--------|
| ⭐ **Star** | High sales + High margin | Keep promoting |
| 🐴 **Plowhorse** | High sales + Low margin | Raise price or cut cost |
| ❓ **Puzzle** | Low sales + High margin | Market more |
| 🐕 **Dog** | Low sales + Low margin | Consider removing |
""")

# Detail table
st.subheader("📋 Item Details")

quadrant_order = {'⭐ Star': 1, '🐴 Plowhorse': 2, '❓ Puzzle': 3, '🐕 Dog': 4}
menu_df['_order'] = menu_df['Quadrant'].map(quadrant_order)
sorted_df = menu_df.sort_values(['_order', 'Qty Sold'], ascending=[True, False])

display_df = sorted_df[['Item', 'Quadrant', 'Qty Sold', 'Selling Price', 'Food Cost', 'Cost Source', 'Unit Margin']].copy()
display_df['Qty Sold'] = display_df['Qty Sold'].apply(lambda x: f"{x:,.0f}")
display_df['Selling Price'] = display_df['Selling Price'].apply(lambda x: f"¥{x:,.0f}")
display_df['Food Cost'] = display_df['Food Cost'].apply(lambda x: f"¥{x:,.0f}")
display_df['Unit Margin'] = display_df['Unit Margin'].apply(lambda x: f"¥{x:,.0f}")

st.dataframe(display_df, hide_index=True, use_container_width=True)

# Important note
st.warning("""
⚠️ **Important:** Food costs shown are **estimates** based on the {0}% default. 
To get accurate margin analysis, either:
1. Adjust the slider in the sidebar
2. Set custom costs for specific items above
3. Use the Recipe & Menu Costing tool to calculate actual costs
""".format(default_cost_pct))
