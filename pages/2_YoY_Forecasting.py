"""
Year-over-Year Forecasting
Reads qty sold from historical database data
Compares to same month in previous years
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import FORECAST_CONFIG, YIELD_RATES, get_total_yield, get_butchery_yield, get_cooking_yield
from database import init_supabase, load_sales, get_date_range, get_data_summary

st.set_page_config(page_title="YoY Forecasting | The Shinmonzen", page_icon="🔮", layout="wide")

st.title("🔮 Year-over-Year Forecasting / 前年比予測")
st.markdown("**Seasonality-Based Forecasting** - Compares to same month in previous years")

# Custom CSS
st.markdown("""
<style>
    .no-data-box {
        background: #f8d7da;
        border: 1px solid #dc3545;
        border-radius: 5px;
        padding: 20px;
        text-align: center;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Supabase
supabase = init_supabase()

# Sidebar settings
with st.sidebar:
    st.header("🔮 Forecast Settings")
    
    if supabase:
        summary = get_data_summary(supabase)
        st.success(f"✅ Connected")
        st.caption(f"📊 {summary.get('sales_count', 0)} sales records")
    else:
        st.error("❌ Database not connected")
        st.stop()
    
    st.divider()
    
    safety_stock_pct = st.slider("Safety Stock (%)", min_value=0, max_value=30, value=10) / 100

# Load all sales data
sales_df = pd.DataFrame()
if supabase:
    db_min, db_max = get_date_range(supabase)
    if db_min and db_max:
        sales_df = load_sales(supabase, db_min, db_max)

if sales_df.empty:
    st.warning("No sales data available. Please upload data in the main app first.")
    st.stop()

# Parse dates
sales_df = sales_df.copy()
sales_df['date'] = pd.to_datetime(sales_df['date'])
sales_df['year'] = sales_df['date'].dt.year
sales_df['month'] = sales_df['date'].dt.month

# =============================================================================
# FILTER OUT UNWANTED ITEMS
# =============================================================================
original_count = len(sales_df)

# 1. Exclude Breakfast category
if 'category' in sales_df.columns:
    sales_df = sales_df[~sales_df['category'].str.lower().str.contains('breakfast', na=False)]

# 2. Exclude items with price = 0 (course items)
if 'price' in sales_df.columns:
    sales_df = sales_df[(sales_df['price'].notna()) & (sales_df['price'] > 0)]

# 3. Exclude Beverage department
if 'department' in sales_df.columns:
    sales_df = sales_df[~sales_df['department'].str.lower().str.contains('beverage', na=False)]

# 4. Exclude "Open food" category
if 'category' in sales_df.columns:
    sales_df = sales_df[~sales_df['category'].str.lower().str.contains('open food', na=False)]

# 5. Exclude categories with "other" in the name (Red other, etc.)
if 'category' in sales_df.columns:
    sales_df = sales_df[~sales_df['category'].str.lower().str.contains('other', na=False)]

filtered_count = len(sales_df)

if sales_df.empty:
    st.warning("No items remaining after filtering. Check your data.")
    st.stop()

# Get available years
available_years = sorted(sales_df['year'].unique())

st.info(f"📊 **Data Available:** {min(available_years)} - {max(available_years)}")

st.divider()

# Target month selection
st.subheader("📅 Forecast Target")

col1, col2, col3 = st.columns(3)
with col1:
    target_year = st.selectbox(
        "Target Year / 対象年",
        options=[max(available_years) + 1, max(available_years)],
        index=0
    )
with col2:
    target_month = st.selectbox(
        "Target Month / 対象月",
        options=list(range(1, 13)),
        format_func=lambda x: datetime(2025, x, 1).strftime('%B'),
        index=0
    )
with col3:
    growth_pct = st.slider(
        "Expected Growth %",
        min_value=-30, max_value=50, value=0,
        help="Adjust based on business outlook"
    ) / 100

target_month_name = datetime(target_year, target_month, 1).strftime('%B %Y')

st.markdown(f"### 🎯 Forecasting for: **{target_month_name}**")

st.divider()

# Get unique items from sales data for selection
unique_items = sales_df['name'].dropna().unique().tolist()
unique_items = sorted([item for item in unique_items if len(str(item)) > 2])

if not unique_items:
    st.warning("No items found in sales data")
    st.stop()

# Ingredient selection - from actual sales data
ingredient = st.selectbox(
    "Select Item / 品目を選択",
    options=unique_items,
    index=0
)

# Determine default TOTAL yield based on item name
def get_default_yield(item_name: str) -> int:
    """
    Get default TOTAL yield percentage from config based on item name.
    TOTAL yield = butchery × cooking (raw → cooked)
    """
    item_lower = item_name.lower()
    if 'beef' in item_lower or 'tenderloin' in item_lower or 'wagyu' in item_lower:
        return int(get_total_yield('beef_tenderloin') * 100)
    elif 'caviar' in item_lower:
        return int(get_total_yield('caviar') * 100)
    elif 'fish' in item_lower or 'amadai' in item_lower:
        return int(get_total_yield('fish_whole') * 100)
    elif 'fillet' in item_lower:
        return int(get_total_yield('fish_fillet') * 100)
    elif 'vegetable' in item_lower or 'salad' in item_lower:
        return int(get_total_yield('vegetables') * 100)
    else:
        return int(get_total_yield('default') * 100)

default_yield = get_default_yield(ingredient)

# Settings - unit is always grams (user inputs COOKED weight)
unit = 'g'

col_a, col_b = st.columns(2)
with col_a:
    usage_per_serving = st.number_input(
        "Cooked portion per serving (g)", 
        min_value=1, max_value=1000, 
        value=100,
        help="Grams of COOKED ingredient per serving (what goes on the plate)"
    )
with col_b:
    yield_pct = st.slider(
        "Total Yield % (raw → cooked)",
        min_value=30, max_value=100,
        value=default_yield,
        help=f"Butchery × Cooking yield. Default {default_yield}%"
    ) / 100

st.caption(f"**{ingredient}** - {usage_per_serving}g cooked/serving @ {yield_pct*100:.0f}% yield → need {usage_per_serving/yield_pct:.0f}g raw/serving")

st.divider()

# Filter sales for this ingredient
ingredient_sales = sales_df[sales_df['name'] == ingredient]

if ingredient_sales.empty:
    st.markdown(f"""
    <div class="no-data-box">
        <h3>❌ No Data Found</h3>
        <p>No sales data found for <b>{ingredient}</b> in the database.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# Get historical data for same month
st.subheader("📊 Historical Data for Same Month")

historical_data = []

for year in sorted(available_years, reverse=True):
    month_data = ingredient_sales[
        (ingredient_sales['year'] == year) & 
        (ingredient_sales['month'] == target_month)
    ]
    
    if not month_data.empty:
        qty_sold = month_data['qty'].sum()
        historical_data.append({
            'Year': year,
            'Month': datetime(year, target_month, 1).strftime('%B %Y'),
            'Qty Sold': qty_sold
        })

if not historical_data:
    available_months = sorted(set(ingredient_sales['date'].dt.strftime('%Y-%m')))
    st.markdown(f"""
    <div class="no-data-box">
        <h3>❌ No Historical Data for {datetime(2025, target_month, 1).strftime('%B')}</h3>
        <p>No sales data found for <b>{ingredient}</b> in <b>{datetime(2025, target_month, 1).strftime('%B')}</b> of any year.</p>
        <p>Available months: {', '.join(available_months[:12])}{'...' if len(available_months) > 12 else ''}</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

historical_df = pd.DataFrame(historical_data)

# Display historical data
st.dataframe(historical_df, use_container_width=True)

# Use most recent year's data as baseline
baseline_year = historical_df.iloc[0]['Year']
baseline_qty = historical_df.iloc[0]['Qty Sold']

st.divider()

# FORECAST CALCULATION
st.subheader("📈 Forecast Calculation")

# Formula: Forecast Qty = Baseline * (1 + Growth%)
forecast_qty = baseline_qty * (1 + growth_pct)

# Raw material needed
raw_needed = (forecast_qty * usage_per_serving) / yield_pct

# Add safety stock
recommended_order = raw_needed * (1 + safety_stock_pct)

# Convert units
if unit == 'g' and recommended_order > 1000:
    display_unit = 'kg'
    display_amount = recommended_order / 1000
    raw_display = raw_needed / 1000
else:
    display_unit = unit
    display_amount = recommended_order
    raw_display = raw_needed

# Display results
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f"""
    <div style="background: #e3f2fd; padding: 20px; border-radius: 10px; text-align: center;">
        <h4>📊 {datetime(baseline_year, target_month, 1).strftime('%b %Y')}</h4>
        <h2>{baseline_qty:,.0f}</h2>
        <p>servings sold</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    growth_color = "#4caf50" if growth_pct >= 0 else "#f44336"
    growth_arrow = "↑" if growth_pct >= 0 else "↓"
    st.markdown(f"""
    <div style="background: #fff3e0; padding: 20px; border-radius: 10px; text-align: center;">
        <h4>📈 Forecast {datetime(target_year, target_month, 1).strftime('%b %Y')}</h4>
        <h2>{forecast_qty:,.0f}</h2>
        <p style="color: {growth_color};">{growth_arrow} {abs(growth_pct)*100:.0f}% vs {baseline_year}</p>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div style="background: #e8f5e9; padding: 20px; border-radius: 10px; text-align: center;">
        <h4>🎯 Recommended Order</h4>
        <h2>{display_amount:,.1f} {display_unit}</h2>
        <p>+{safety_stock_pct*100:.0f}% safety stock</p>
    </div>
    """, unsafe_allow_html=True)

# Calculation breakdown
st.divider()
st.subheader("📋 Calculation Breakdown")

st.markdown(f"""
| Step | Calculation | Result |
|------|-------------|--------|
| 1. Historical Data | {datetime(baseline_year, target_month, 1).strftime('%B %Y')} | **{baseline_qty:,.0f}** servings |
| 2. Apply Growth | {baseline_qty:,.0f} × (1 + {growth_pct*100:.0f}%) | **{forecast_qty:,.0f}** servings |
| 3. Raw Material | {forecast_qty:,.0f} × {usage_per_serving}{unit} ÷ {yield_pct*100:.0f}% | **{raw_display:,.1f} {display_unit}** |
| 4. Safety Stock | {raw_display:,.1f} × (1 + {safety_stock_pct*100:.0f}%) | **{display_amount:,.1f} {display_unit}** |
""")

# Summary
st.success(f"""
**Summary:** In {datetime(baseline_year, target_month, 1).strftime('%B %Y')}, you sold **{baseline_qty:,.0f}** {ingredient} dishes. 
With **{growth_pct*100:+.0f}%** growth, forecast **{forecast_qty:,.0f}** servings for {target_month_name}. 
Recommended order: **{display_amount:,.1f} {display_unit}** (including {safety_stock_pct*100:.0f}% safety stock).
""")

# Historical trend chart
if len(historical_df) > 1:
    st.divider()
    st.subheader("📈 Historical Trend for This Month")
    
    fig = px.bar(historical_df.sort_values('Year'), x='Month', y='Qty Sold',
                title=f"{ingredient} - {datetime(2025, target_month, 1).strftime('%B')} Sales History")
    fig.add_hline(y=forecast_qty, line_dash="dash", line_color="green",
                 annotation_text=f"Forecast: {forecast_qty:,.0f}")
    st.plotly_chart(fig, use_container_width=True)
