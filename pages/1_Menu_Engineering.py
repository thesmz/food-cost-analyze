"""
Menu Engineering - BCG Matrix Analysis
A la Carte items only (excludes Tasting Menus)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DISH_INGREDIENT_MAP, A_LA_CARTE_ITEMS
from database import init_supabase, load_sales, get_date_range, get_data_summary

st.set_page_config(page_title="Menu Engineering | The Shinmonzen", page_icon="📈", layout="wide")

st.title("📈 Menu Engineering / メニュー分析")
st.markdown("**BCG Matrix Analysis** - A La Carte Items Only (Excludes Tasting Menus)")


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
    # Filter out category names that slip through
    invalid_names = ['carte', 'a la carte', 'dinner', 'lunch', 'breakfast', 'dessert', 'course', 'open food']
    if name_str.lower() in invalid_names:
        return False
    return True


# Initialize Supabase
supabase = init_supabase()

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
    min_qty = st.number_input("Min Qty Sold / 最小販売数", min_value=1, value=5)
    default_cost_pct = st.slider("Default Cost % (if unknown)", 20, 50, 30) / 100

# Load sales data
sales_df = pd.DataFrame()
if supabase:
    db_min, db_max = get_date_range(supabase)
    if db_min and db_max:
        sales_df = load_sales(supabase, db_min, db_max)

if sales_df.empty:
    st.warning("No sales data available. Please upload data in the main app.")
    st.stop()

# STRICT FILTER: Only 'A la carte' category
if 'category' not in sales_df.columns:
    st.error("Category column not found in sales data")
    st.stop()

alacarte_df = sales_df[sales_df['category'] == 'A la carte'].copy()

if alacarte_df.empty:
    st.warning("No 'A la carte' items found in the data.")
    st.info(f"Categories in data: {', '.join(sales_df['category'].unique())}")
    st.stop()

# Filter valid item names
alacarte_df = alacarte_df[alacarte_df['name'].apply(is_valid_item_name)]

# Aggregate by item
item_sales = alacarte_df.groupby('name').agg({
    'qty': 'sum',
    'net_total': 'sum',
    'price': 'mean'
}).reset_index()

item_sales = item_sales[item_sales['qty'] >= min_qty]

if item_sales.empty:
    st.warning(f"No items with qty >= {min_qty}")
    st.stop()

# Calculate metrics
menu_data = []
for _, row in item_sales.iterrows():
    item_name = row['name']
    qty_sold = row['qty']
    total_revenue = row['net_total']
    avg_price = row['price'] if row['price'] > 0 else (total_revenue / qty_sold if qty_sold > 0 else 0)
    
    # Get cost from config
    if item_name in A_LA_CARTE_ITEMS:
        config = A_LA_CARTE_ITEMS[item_name]
        selling_price = config.get('selling_price', avg_price)
        food_cost = config.get('estimated_food_cost', selling_price * default_cost_pct)
    elif item_name in DISH_INGREDIENT_MAP:
        config = DISH_INGREDIENT_MAP[item_name]
        selling_price = config.get('selling_price', avg_price)
        food_cost = config.get('estimated_cost_per_serving', selling_price * default_cost_pct)
    else:
        selling_price = avg_price if avg_price > 0 else 1000
        food_cost = selling_price * default_cost_pct
    
    unit_margin = selling_price - food_cost
    
    menu_data.append({
        'Item': item_name,
        'Qty Sold': qty_sold,
        'Unit Margin': unit_margin,
        'Total Revenue': total_revenue,
        'Total Contribution': unit_margin * qty_sold,
        'Selling Price': selling_price,
        'Food Cost': food_cost
    })

menu_df = pd.DataFrame(menu_data)

st.info(f"📊 Analyzing **{len(menu_df)}** A la carte items")

# Calculate averages
avg_qty = menu_df['Qty Sold'].mean()
avg_margin = menu_df['Unit Margin'].mean()

# Classify items based on averages
# Star = High Qty AND High Margin (top-right)
# Plowhorse = High Qty AND Low Margin (bottom-right)
# Puzzle = Low Qty AND High Margin (top-left)
# Dog = Low Qty AND Low Margin (bottom-left)
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

# Create scatter plot - CLEAN version without overlapping labels
fig = go.Figure()

# Color and symbol mapping
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
            mode='markers',  # NO text labels - only markers
            name=quadrant,
            marker=dict(
                size=12, 
                color=style['color'], 
                symbol=style['symbol'],
                line=dict(width=1, color='white')
            ),
            text=df_q['Item'],  # For hover only
            hovertemplate='<b>%{text}</b><br>Qty Sold: %{x:,.0f}<br>Unit Margin: ¥%{y:,.0f}<extra></extra>'
        ))

# Add quadrant dividing lines
fig.add_hline(y=avg_margin, line_dash="dash", line_color="rgba(0,0,0,0.3)", line_width=2)
fig.add_vline(x=avg_qty, line_dash="dash", line_color="rgba(0,0,0,0.3)", line_width=2)

# Add quadrant labels
fig.add_annotation(x=avg_qty*0.3, y=menu_df['Unit Margin'].max()*0.95, 
                   text="❓ Puzzle<br>(High Margin, Low Qty)", showarrow=False, 
                   font=dict(size=10, color="gray"))
fig.add_annotation(x=menu_df['Qty Sold'].max()*0.85, y=menu_df['Unit Margin'].max()*0.95, 
                   text="⭐ Star<br>(High Margin, High Qty)", showarrow=False,
                   font=dict(size=10, color="gray"))
fig.add_annotation(x=avg_qty*0.3, y=menu_df['Unit Margin'].min()*1.1, 
                   text="🐕 Dog<br>(Low Margin, Low Qty)", showarrow=False,
                   font=dict(size=10, color="gray"))
fig.add_annotation(x=menu_df['Qty Sold'].max()*0.85, y=menu_df['Unit Margin'].min()*1.1, 
                   text="🐴 Plowhorse<br>(Low Margin, High Qty)", showarrow=False,
                   font=dict(size=10, color="gray"))

fig.update_layout(
    title=f"Menu Engineering Matrix | Avg Qty: {avg_qty:.0f} | Avg Margin: ¥{avg_margin:,.0f}",
    xaxis_title="Popularity (Qty Sold)",
    yaxis_title="Profitability (Unit Margin ¥)",
    height=550,
    showlegend=True,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    plot_bgcolor='white',
    xaxis=dict(gridcolor='rgba(0,0,0,0.1)', zeroline=False),
    yaxis=dict(gridcolor='rgba(0,0,0,0.1)', zeroline=False, tickformat=',.0f', tickprefix='¥')
)

st.plotly_chart(fig, use_container_width=True)

st.caption("💡 **Tip:** Hover over points to see dish names")

# Quadrant guide
st.markdown("""
### 📖 Quadrant Guide / 分類ガイド

| Quadrant | Qty vs Avg | Margin vs Avg | Action |
|----------|------------|---------------|--------|
| ⭐ **Star** | HIGH (≥ avg) | HIGH (≥ avg) | Keep promoting! |
| 🐴 **Plowhorse** | HIGH (≥ avg) | LOW (< avg) | Raise price or reduce cost |
| ❓ **Puzzle** | LOW (< avg) | HIGH (≥ avg) | Market more, feature it |
| 🐕 **Dog** | LOW (< avg) | LOW (< avg) | Consider removing |
""")

# Detail table
st.subheader("📋 Item Details / 品目詳細")

# Add quadrant order for sorting
quadrant_order = {'⭐ Star': 1, '🐴 Plowhorse': 2, '❓ Puzzle': 3, '🐕 Dog': 4}
menu_df['_order'] = menu_df['Quadrant'].map(quadrant_order)

display_df = menu_df[['Item', 'Quadrant', 'Qty Sold', 'Unit Margin', 'Total Contribution']].copy()
display_df = display_df.sort_values(['_order' if '_order' in menu_df.columns else 'Quadrant', 'Qty Sold'], 
                                     ascending=[True, False])
display_df = display_df.drop(columns=['_order'], errors='ignore')
display_df['Qty Sold'] = display_df['Qty Sold'].apply(lambda x: f"{x:,.0f}")
display_df['Unit Margin'] = display_df['Unit Margin'].apply(lambda x: f"¥{x:,.0f}")
display_df['Total Contribution'] = display_df['Total Contribution'].apply(lambda x: f"¥{x:,.0f}")
st.dataframe(display_df, use_container_width=True, hide_index=True)
