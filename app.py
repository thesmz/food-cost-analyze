"""
Purchasing Evaluation System for The Shinmonzen
Analyzes ingredient purchases vs dish sales to evaluate waste and cost efficiency
Features: Yield Management, Menu Engineering, Year-over-Year Forecasting, Tasting Menu Analysis
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import re
from datetime import datetime, date, timedelta
from io import StringIO
from typing import Dict, Any, Optional

# Import our modules
from extractors import extract_sales_data, extract_invoice_data
from config import (
    VENDOR_CONFIG, DISH_INGREDIENT_MAP, FOOD_CATEGORIES, EXCLUDED_CATEGORIES,
    TASTING_MENU_RECIPES, A_LA_CARTE_ITEMS, DEFAULT_TARGETS,
    FOOD_COST_WARNING_THRESHOLD, SEASONALITY_FACTORS, FORECAST_CONFIG
)
from database import (
    init_supabase, save_invoices, save_sales, 
    load_invoices, load_sales, get_date_range, get_data_summary,
    delete_data_by_date_range
)

st.set_page_config(
    page_title="Purchasing Evaluation | The Shinmonzen",
    page_icon="🍽️",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        margin: 10px 0;
    }
    .vendor-header {
        font-size: 1.2em;
        font-weight: bold;
        padding: 10px;
        background: #f0f2f6;
        border-radius: 5px;
        margin: 10px 0;
    }
    .db-status-connected {
        padding: 10px;
        background: #d4edda;
        border-radius: 5px;
        color: #155724;
        text-align: center;
    }
    .db-status-disconnected {
        padding: 10px;
        background: #f8d7da;
        border-radius: 5px;
        color: #721c24;
        text-align: center;
    }
    .warning-box {
        background: #fff3cd;
        border: 1px solid #ffc107;
        border-radius: 5px;
        padding: 15px;
        margin: 10px 0;
    }
    .success-box {
        background: #d4edda;
        border: 1px solid #28a745;
        border-radius: 5px;
        padding: 15px;
        margin: 10px 0;
    }
    .forecast-card {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        margin: 10px 0;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


def clean_and_filter_sales(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and filter sales data - STRICTLY exclude beverages
    Only keeps items in FOOD_CATEGORIES
    """
    if df.empty:
        return df
    
    # Ensure category column exists
    if 'category' not in df.columns:
        return df
    
    # Convert category to string and strip whitespace
    df['category'] = df['category'].astype(str).str.strip()
    
    # STRICT FILTER: Only keep rows where category is in FOOD_CATEGORIES
    filtered_df = df[df['category'].isin(FOOD_CATEGORIES)].copy()
    
    # Double-check: Explicitly remove any beverage-related items that might slip through
    beverage_patterns = '|'.join([
        'beverage', 'wine', 'beer', 'cocktail', 'sake', 'spirits',
        'drink', 'alcohol', 'ビール', 'ワイン', '酒', 'ドリンク', 'カクテル'
    ])
    
    # Filter out any items with beverage-related names
    if 'name' in filtered_df.columns:
        filtered_df = filtered_df[
            ~filtered_df['name'].str.contains(beverage_patterns, case=False, na=False)
        ]
    
    # Filter out any remaining beverage categories
    filtered_df = filtered_df[
        ~filtered_df['category'].str.contains(beverage_patterns, case=False, na=False)
    ]
    
    return filtered_df


def is_valid_item_name(name) -> bool:
    """Check if item name is valid (not numeric, not empty, not special chars only)"""
    if pd.isna(name):
        return False
    name_str = str(name).strip()
    if not name_str:
        return False
    if all(c in '-_. ' for c in name_str):
        return False
    cleaned = name_str.replace(',', '').replace('.', '').replace(' ', '').replace('-', '')
    if cleaned.isdigit():
        return False
    if len(name_str) > 0 and name_str[0].isdigit() and (',' in name_str or len(cleaned) > 6):
        return False
    if len(name_str) <= 2:
        return False
    return True


def main():
    st.title("🍽️ The Shinmonzen - Purchasing Evaluation")
    st.markdown("*Ingredient Cost & Menu Analysis System*")
    
    # Initialize session state
    if 'upload_key' not in st.session_state:
        st.session_state.upload_key = 0
    if 'filter_start' not in st.session_state:
        st.session_state.filter_start = date.today().replace(day=1) - timedelta(days=30)
    if 'filter_end' not in st.session_state:
        st.session_state.filter_end = date.today()
    
    # Initialize Supabase
    supabase = init_supabase()
    
    # Sidebar
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/restaurant.png", width=80)
        st.header("🏪 The Shinmonzen")
        
        # Database status
        st.header("💾 Database / データベース")
        if supabase:
            summary = get_data_summary(supabase)
            st.markdown('<div class="db-status-connected">✅ Connected / 接続中</div>', unsafe_allow_html=True)
            st.caption(f"📊 {summary.get('invoice_count', 0)} invoices, {summary.get('sales_count', 0)} sales records")
            if summary.get('min_date') and summary.get('max_date'):
                st.caption(f"📅 {summary['min_date']} ~ {summary['max_date']}")
        else:
            st.markdown('<div class="db-status-disconnected">❌ Not connected</div>', unsafe_allow_html=True)
        
        st.divider()
        
        # Date filter
        st.header("📅 Date Filter / 期間選択")
        
        db_min_date, db_max_date = None, None
        if supabase:
            db_min_date, db_max_date = get_date_range(supabase)
            if db_min_date and db_max_date:
                st.caption(f"Data available: {db_min_date} ~ {db_max_date}")
        
        start_date = st.date_input(
            "Start Date / 開始日",
            value=st.session_state.filter_start,
            key="start_date_input"
        )
        end_date = st.date_input(
            "End Date / 終了日",
            value=st.session_state.filter_end,
            key="end_date_input"
        )
        
        # Quick date presets
        st.caption("Quick select / クイック選択:")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("This Month", use_container_width=True):
                st.session_state.filter_start = date.today().replace(day=1)
                st.session_state.filter_end = date.today()
                st.rerun()
        with col2:
            if st.button("All Data", use_container_width=True):
                if db_min_date and db_max_date:
                    st.session_state.filter_start = db_min_date
                    st.session_state.filter_end = db_max_date
                    st.rerun()
        
        st.divider()
        
        # Settings
        st.subheader("⚙️ Settings / 設定")
        
        beef_per_serving = st.number_input(
            "Beef per serving (g)",
            min_value=50, max_value=500, value=150,
            help="Grams of cooked beef per serving"
        )
        
        beef_yield_pct = st.slider(
            "Beef Yield (%)",
            min_value=50, max_value=100, value=65,
            help="Usable meat after trimming"
        ) / 100
        
        caviar_per_serving = st.number_input(
            "Caviar per serving (g)",
            min_value=5, max_value=50, value=10,
            help="Grams of caviar per serving"
        )
        
        caviar_yield_pct = st.slider(
            "Caviar Yield (%)",
            min_value=80, max_value=100, value=100,
            help="Usable caviar (usually 100%)"
        ) / 100
        
        st.divider()
        
        # File upload section
        st.header("📁 Upload Data")
        
        sales_files = st.file_uploader(
            "Sales Reports (CSV)",
            type=['csv'],
            accept_multiple_files=True,
            key=f"sales_uploader_{st.session_state.upload_key}"
        )
        
        invoice_files = st.file_uploader(
            "Invoices (PDF/Excel)",
            type=['pdf', 'xlsx', 'xls'],
            accept_multiple_files=True,
            key=f"invoice_uploader_{st.session_state.upload_key}"
        )
        
        # Data management
        with st.expander("🗑️ Data Management"):
            st.warning("⚠️ Danger zone")
            if st.button("Delete data in selected range", type="secondary"):
                if supabase:
                    deleted = delete_data_by_date_range(supabase, start_date, end_date)
                    st.info(f"Deleted {deleted['invoices']} invoices, {deleted['sales']} sales")
                    st.rerun()
    
    # Main content area
    sales_df = pd.DataFrame()
    invoices_df = pd.DataFrame()
    
    # Check database
    db_has_data = False
    if supabase:
        summary = get_data_summary(supabase)
        db_has_data = (summary.get('invoice_count', 0) > 0 or summary.get('sales_count', 0) > 0)
    
    # Load from database
    if supabase and db_has_data:
        invoices_df = load_invoices(supabase, start_date, end_date)
        sales_df = load_sales(supabase, start_date, end_date)
        
        # Apply strict food filter
        if not sales_df.empty:
            original_count = len(sales_df)
            sales_df = clean_and_filter_sales(sales_df)
            filtered_count = len(sales_df)
            if original_count != filtered_count:
                st.sidebar.caption(f"🍽️ Food items: {filtered_count} (excluded {original_count - filtered_count} beverages)")
    
    # Process uploaded files
    if sales_files or invoice_files:
        with st.spinner("Processing files..."):
            # Process sales
            if sales_files:
                sales_list = []
                for file in sales_files:
                    df = extract_sales_data(file)
                    if not df.empty:
                        sales_list.append(df)
                if sales_list:
                    new_sales = pd.concat(sales_list, ignore_index=True)
                    new_sales = clean_and_filter_sales(new_sales)
                    if supabase:
                        save_sales(supabase, new_sales)
                    sales_df = pd.concat([sales_df, new_sales], ignore_index=True) if not sales_df.empty else new_sales
            
            # Process invoices
            if invoice_files:
                invoice_list = []
                for file in invoice_files:
                    df = extract_invoice_data(file)
                    if not df.empty:
                        invoice_list.append(df)
                if invoice_list:
                    new_invoices = pd.concat(invoice_list, ignore_index=True)
                    if supabase:
                        save_invoices(supabase, new_invoices)
                    invoices_df = pd.concat([invoices_df, new_invoices], ignore_index=True) if not invoices_df.empty else new_invoices
            
            st.session_state.upload_key += 1
            st.success("✅ Files processed and saved!")
            st.rerun()
    
    # Show data status
    if sales_df.empty and invoices_df.empty:
        st.info("📤 Upload sales reports and invoices to begin analysis, or adjust the date filter.")
        return
    
    # Display tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊 Overview",
        "🥩 Beef Analysis", 
        "🐟 Caviar Analysis",
        "📈 Menu Engineering",
        "🔮 YoY Forecasting",
        "🍽️ Tasting Menu Analyzer",
        "📋 Vendor Items"
    ])
    
    with tab1:
        display_overview(sales_df, invoices_df, beef_per_serving, caviar_per_serving, beef_yield_pct, caviar_yield_pct)
    
    with tab2:
        display_beef_analysis(sales_df, invoices_df, beef_per_serving, beef_yield_pct)
    
    with tab3:
        display_caviar_analysis(sales_df, invoices_df, caviar_per_serving, caviar_yield_pct)
    
    with tab4:
        display_menu_engineering(sales_df)
    
    with tab5:
        display_yoy_forecasting(sales_df, beef_per_serving, caviar_per_serving, beef_yield_pct, caviar_yield_pct)
    
    with tab6:
        display_tasting_menu_analyzer()
    
    with tab7:
        display_vendor_items(invoices_df)


# =============================================================================
# OVERVIEW TAB
# =============================================================================
def display_overview(sales_df, invoices_df, beef_per_serving, caviar_per_serving, beef_yield_pct, caviar_yield_pct):
    """Display overview dashboard"""
    st.header("📊 Overview / 概要")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if not sales_df.empty:
            total_items = len(sales_df)
            total_qty = sales_df['qty'].sum()
            st.metric("Food Items Sold", f"{total_qty:,.0f}", help="Beverages excluded")
        else:
            st.metric("Food Items Sold", "0")
    
    with col2:
        if not sales_df.empty:
            total_revenue = sales_df['net_total'].sum()
            st.metric("Food Revenue", f"¥{total_revenue:,.0f}")
        else:
            st.metric("Food Revenue", "¥0")
    
    with col3:
        if not invoices_df.empty:
            total_purchases = invoices_df['amount'].sum()
            st.metric("Total Purchases", f"¥{total_purchases:,.0f}")
        else:
            st.metric("Total Purchases", "¥0")
    
    with col4:
        if not sales_df.empty:
            unique_items = sales_df['name'].nunique()
            st.metric("Unique Items", f"{unique_items}")
        else:
            st.metric("Unique Items", "0")
    
    st.divider()
    
    # Key ingredients summary
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🥩 Beef Tenderloin")
        if not sales_df.empty:
            beef_sales = sales_df[sales_df['name'].str.contains('Beef Tenderloin', case=False, na=False)]
            total_beef_qty = beef_sales['qty'].sum()
            expected_raw_kg = (total_beef_qty * beef_per_serving / beef_yield_pct) / 1000
            
            st.metric("Dishes Sold", f"{total_beef_qty:.0f}")
            st.metric("Raw Beef Needed", f"{expected_raw_kg:.2f} kg", 
                     help=f"At {beef_yield_pct*100:.0f}% yield")
        else:
            st.info("No beef sales data")
    
    with col2:
        st.subheader("🐟 Caviar (Egg Toast)")
        if not sales_df.empty:
            caviar_sales = sales_df[sales_df['name'].str.contains('Egg Toast Caviar', case=False, na=False)]
            total_caviar_qty = caviar_sales['qty'].sum()
            expected_g = (total_caviar_qty * caviar_per_serving) / caviar_yield_pct
            
            st.metric("Dishes Sold", f"{total_caviar_qty:.0f}")
            st.metric("Caviar Needed", f"{expected_g:.0f} g ({expected_g/100:.1f} units)",
                     help=f"At {caviar_yield_pct*100:.0f}% yield")
        else:
            st.info("No caviar sales data")
    
    # Category breakdown
    if not sales_df.empty:
        st.divider()
        st.subheader("📊 Sales by Category (Food Only)")
        
        category_summary = sales_df.groupby('category').agg({
            'qty': 'sum',
            'net_total': 'sum'
        }).reset_index()
        category_summary.columns = ['Category', 'Qty Sold', 'Revenue']
        category_summary = category_summary.sort_values('Revenue', ascending=False)
        
        fig = px.bar(category_summary, x='Category', y='Revenue',
                    color='Category', title="Revenue by Category")
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# BEEF ANALYSIS TAB
# =============================================================================
def display_beef_analysis(sales_df, invoices_df, beef_per_serving, beef_yield_pct):
    """Detailed beef analysis with yield-adjusted calculations"""
    st.header("🥩 Beef Tenderloin Analysis")
    
    st.info(f"📐 **Yield Rate:** {beef_yield_pct*100:.0f}% | **Serving Size:** {beef_per_serving}g cooked")
    
    # Filter data
    beef_sales = sales_df[sales_df['name'].str.contains('Beef Tenderloin', case=False, na=False)] if not sales_df.empty else pd.DataFrame()
    beef_invoices = invoices_df[invoices_df['item_name'].str.contains('ヒレ|フィレ|tenderloin|牛', case=False, na=False)] if not invoices_df.empty else pd.DataFrame()
    
    if beef_sales.empty and beef_invoices.empty:
        st.warning("No beef data available")
        return
    
    col1, col2, col3 = st.columns(3)
    
    # Calculate metrics
    total_sold = beef_sales['qty'].sum() if not beef_sales.empty else 0
    total_revenue = beef_sales['net_total'].sum() if not beef_sales.empty else 0
    
    # Yield-adjusted usage
    raw_needed_g = (total_sold * beef_per_serving) / beef_yield_pct
    raw_needed_kg = raw_needed_g / 1000
    cooked_portion_kg = (total_sold * beef_per_serving) / 1000
    
    # Purchases
    total_purchased_kg = beef_invoices['quantity'].sum() if not beef_invoices.empty else 0
    total_cost = beef_invoices['amount'].sum() if not beef_invoices.empty else 0
    
    with col1:
        st.metric("Dishes Sold", f"{total_sold:.0f}")
        st.metric("Revenue", f"¥{total_revenue:,.0f}")
    
    with col2:
        st.metric("Purchased", f"{total_purchased_kg:.2f} kg")
        st.metric("Cost", f"¥{total_cost:,.0f}")
    
    with col3:
        if total_purchased_kg > 0:
            waste_ratio = max(0, (total_purchased_kg - raw_needed_kg) / total_purchased_kg * 100)
            st.metric("Waste Ratio", f"{waste_ratio:.1f}%",
                     delta=f"{waste_ratio - 15:.1f}%" if waste_ratio > 15 else None,
                     delta_color="inverse")
        
        if total_revenue > 0:
            cost_ratio = (total_cost / total_revenue) * 100
            st.metric("Cost Ratio", f"{cost_ratio:.1f}%",
                     delta=f"{cost_ratio - 35:.1f}%" if cost_ratio > 35 else None,
                     delta_color="inverse")
    
    # Usage comparison chart
    st.subheader("📈 Usage Comparison")
    
    comparison_data = pd.DataFrame({
        'Category': ['Purchased (Raw)', 'Needed (Raw)', 'Cooked Portion', 'Variance'],
        'Amount (kg)': [total_purchased_kg, raw_needed_kg, cooked_portion_kg, max(0, total_purchased_kg - raw_needed_kg)]
    })
    
    fig = px.bar(comparison_data, x='Category', y='Amount (kg)',
                color='Category',
                color_discrete_sequence=['#3366cc', '#ff9900', '#109618', '#dc3912'])
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# CAVIAR ANALYSIS TAB
# =============================================================================
def display_caviar_analysis(sales_df, invoices_df, caviar_per_serving, caviar_yield_pct):
    """Detailed caviar analysis"""
    st.header("🐟 Caviar Analysis")
    
    st.info(f"📐 **Yield Rate:** {caviar_yield_pct*100:.0f}% | **Serving Size:** {caviar_per_serving}g")
    
    caviar_sales = sales_df[sales_df['name'].str.contains('Egg Toast Caviar', case=False, na=False)] if not sales_df.empty else pd.DataFrame()
    caviar_invoices = invoices_df[invoices_df['item_name'].str.contains('キャビア|KAVIARI|caviar', case=False, na=False)] if not invoices_df.empty else pd.DataFrame()
    
    if caviar_sales.empty and caviar_invoices.empty:
        st.warning("No caviar data available")
        return
    
    col1, col2, col3 = st.columns(3)
    
    total_sold = caviar_sales['qty'].sum() if not caviar_sales.empty else 0
    total_revenue = caviar_sales['net_total'].sum() if not caviar_sales.empty else 0
    expected_g = (total_sold * caviar_per_serving) / caviar_yield_pct
    
    # Purchases
    if not caviar_invoices.empty:
        total_qty = caviar_invoices['quantity'].sum()
        total_purchased_g = total_qty if total_qty > 100 else total_qty * 100
        total_cost = caviar_invoices['amount'].sum()
    else:
        total_purchased_g = 0
        total_cost = 0
    
    with col1:
        st.metric("Dishes Sold", f"{total_sold:.0f}")
        st.metric("Revenue", f"¥{total_revenue:,.0f}")
    
    with col2:
        st.metric("Purchased", f"{total_purchased_g:.0f} g")
        st.metric("Cost", f"¥{total_cost:,.0f}")
    
    with col3:
        if total_purchased_g > 0:
            waste_ratio = max(0, (total_purchased_g - expected_g) / total_purchased_g * 100)
            st.metric("Waste Ratio", f"{waste_ratio:.1f}%")
        
        if total_revenue > 0:
            cost_ratio = (total_cost / total_revenue) * 100
            st.metric("Cost Ratio", f"{cost_ratio:.1f}%")


# =============================================================================
# MENU ENGINEERING TAB - A LA CARTE ONLY
# =============================================================================
def display_menu_engineering(sales_df):
    """
    Menu Engineering Analysis - BCG Matrix
    ONLY analyzes 'A la carte' items (excludes Tasting Menus)
    """
    st.header("📈 Menu Engineering / メニュー分析")
    st.markdown("**BCG Matrix Analysis** - A La Carte Items Only")
    
    if sales_df.empty:
        st.warning("No sales data available")
        return
    
    # STRICT FILTER: Only 'A la carte' category
    alacarte_df = sales_df[sales_df['category'] == 'A la carte'].copy()
    
    if alacarte_df.empty:
        st.warning("No 'A la carte' items found. This analysis excludes Tasting Menus.")
        st.info("Categories found: " + ", ".join(sales_df['category'].unique()))
        return
    
    # Filter valid item names
    alacarte_df = alacarte_df[alacarte_df['name'].apply(is_valid_item_name)]
    
    # Settings
    col1, col2 = st.columns(2)
    with col1:
        min_qty = st.number_input("Min Qty Sold", min_value=1, value=5)
    with col2:
        default_cost_pct = st.slider("Default Cost % (if unknown)", 20, 50, 30) / 100
    
    # Aggregate by item
    item_sales = alacarte_df.groupby('name').agg({
        'qty': 'sum',
        'net_total': 'sum',
        'price': 'mean'
    }).reset_index()
    
    item_sales = item_sales[item_sales['qty'] >= min_qty]
    
    if item_sales.empty:
        st.warning(f"No items with qty >= {min_qty}")
        return
    
    # Calculate metrics
    menu_data = []
    for _, row in item_sales.iterrows():
        item_name = row['name']
        qty_sold = row['qty']
        total_revenue = row['net_total']
        avg_price = row['price'] if row['price'] > 0 else (total_revenue / qty_sold if qty_sold > 0 else 0)
        
        # Get cost from config or estimate
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
    
    # Calculate averages for quadrants
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
    
    colors = {'⭐ Star': '#FFD700', '🐴 Plowhorse': '#4CAF50', '❓ Puzzle': '#2196F3', '🐕 Dog': '#9E9E9E'}
    
    for quadrant, color in colors.items():
        df_q = menu_df[menu_df['Quadrant'] == quadrant]
        if not df_q.empty:
            fig.add_trace(go.Scatter(
                x=df_q['Qty Sold'],
                y=df_q['Unit Margin'],
                mode='markers+text',
                name=quadrant,
                marker=dict(size=15, color=color, line=dict(width=1, color='white')),
                text=df_q['Item'],
                textposition='top center',
                hovertemplate='<b>%{text}</b><br>Qty: %{x}<br>Margin: ¥%{y:,.0f}<extra></extra>'
            ))
    
    # Add quadrant lines
    fig.add_hline(y=avg_margin, line_dash="dash", line_color="gray",
                  annotation_text=f"Avg Margin: ¥{avg_margin:,.0f}")
    fig.add_vline(x=avg_qty, line_dash="dash", line_color="gray",
                  annotation_text=f"Avg Qty: {avg_qty:.0f}")
    
    fig.update_layout(
        title="Menu Engineering Matrix (A La Carte Only)",
        xaxis_title="Popularity (Qty Sold)",
        yaxis_title="Profitability (Unit Margin ¥)",
        height=500,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Quadrant guide
    st.markdown("""
    | Quadrant | Description | Action |
    |----------|-------------|--------|
    | ⭐ **Star** | High popularity + High profit | Maintain & promote |
    | 🐴 **Plowhorse** | High popularity + Low profit | Consider price increase |
    | ❓ **Puzzle** | Low popularity + High profit | Increase marketing |
    | 🐕 **Dog** | Low popularity + Low profit | Consider removing |
    """)
    
    # Detail table
    st.subheader("📋 Item Details")
    display_df = menu_df[['Item', 'Quadrant', 'Qty Sold', 'Unit Margin', 'Total Contribution']].copy()
    display_df['Unit Margin'] = display_df['Unit Margin'].apply(lambda x: f"¥{x:,.0f}")
    display_df['Total Contribution'] = display_df['Total Contribution'].apply(lambda x: f"¥{x:,.0f}")
    st.dataframe(display_df.sort_values('Qty Sold', ascending=False), use_container_width=True)


# =============================================================================
# YEAR-OVER-YEAR FORECASTING TAB
# =============================================================================
def display_yoy_forecasting(sales_df, beef_per_serving, caviar_per_serving, beef_yield_pct, caviar_yield_pct):
    """
    Year-over-Year Forecasting
    Uses last year's same month data + growth rate (NOT moving averages)
    """
    st.header("🔮 Year-over-Year Forecasting / 前年比予測")
    st.markdown("**Seasonality-Based Forecasting** - Compare to same month last year")
    
    # Determine target month
    st.subheader("📅 Target Month Selection")
    
    col1, col2 = st.columns(2)
    with col1:
        target_month = st.selectbox(
            "Forecast for Month / 予測対象月",
            options=list(range(1, 13)),
            format_func=lambda x: datetime(2025, x, 1).strftime('%B'),
            index=datetime.now().month % 12  # Next month
        )
    with col2:
        target_year = st.number_input(
            "Year / 年",
            min_value=2024, max_value=2030, value=2025
        )
    
    target_month_name = datetime(target_year, target_month, 1).strftime('%B %Y')
    last_year_month_name = datetime(target_year - 1, target_month, 1).strftime('%B %Y')
    
    st.info(f"🎯 **Forecasting for: {target_month_name}** (comparing to {last_year_month_name})")
    
    st.divider()
    
    # Ingredient selection
    ingredient = st.selectbox(
        "Select Ingredient / 食材を選択",
        options=list(DISH_INGREDIENT_MAP.keys()),
        index=0
    )
    
    config = DISH_INGREDIENT_MAP[ingredient]
    usage_per_serving = config['usage_per_serving']
    yield_pct = config['yield_percent']
    unit = config['unit']
    
    # Override with sidebar settings for beef/caviar
    if ingredient == 'Beef Tenderloin':
        usage_per_serving = beef_per_serving
        yield_pct = beef_yield_pct
    elif ingredient == 'Egg Toast Caviar':
        usage_per_serving = caviar_per_serving
        yield_pct = caviar_yield_pct
    
    st.markdown(f"**{ingredient}** - {usage_per_serving}{unit}/serving, {yield_pct*100:.0f}% yield")
    
    st.divider()
    
    # YoY Input Section
    st.subheader("📊 Year-over-Year Comparison")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"**{last_year_month_name} Data**")
        last_year_qty = st.number_input(
            f"Qty Sold in {last_year_month_name}",
            min_value=0, max_value=10000, value=200,
            help="Enter the quantity sold for the same month last year"
        )
    
    with col2:
        st.markdown("**Growth Expectation**")
        growth_pct = st.slider(
            "Expected Growth/Decline %",
            min_value=-50, max_value=100, value=5,
            help="Positive = growth, Negative = decline"
        ) / 100
    
    # Safety stock
    safety_stock_pct = st.slider(
        "Safety Stock Buffer %",
        min_value=0, max_value=30, value=10,
        help="Extra buffer for unexpected demand"
    ) / 100
    
    st.divider()
    
    # CALCULATIONS
    st.subheader("📈 Forecast Results")
    
    # Formula: Forecast Qty = Last_Year_Qty * (1 + Growth_Pct)
    forecast_qty = last_year_qty * (1 + growth_pct)
    
    # Raw material needed: (Forecast_Qty * Usage_Per_Serving) / Yield_Percent
    raw_needed = (forecast_qty * usage_per_serving) / yield_pct
    
    # Add safety stock
    recommended_order = raw_needed * (1 + safety_stock_pct)
    
    # Convert units
    if unit == 'g':
        if recommended_order > 1000:
            display_unit = 'kg'
            display_amount = recommended_order / 1000
            raw_display = raw_needed / 1000
        else:
            display_unit = 'g'
            display_amount = recommended_order
            raw_display = raw_needed
    else:
        display_unit = unit
        display_amount = recommended_order
        raw_display = raw_needed
    
    # Display results in cards
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div style="background: #e3f2fd; padding: 20px; border-radius: 10px; text-align: center;">
            <h4>📊 Last Year ({last_year_month_name[:3]})</h4>
            <h2>{last_year_qty:,.0f}</h2>
            <p>servings sold</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        growth_color = "#4caf50" if growth_pct >= 0 else "#f44336"
        growth_arrow = "↑" if growth_pct >= 0 else "↓"
        st.markdown(f"""
        <div style="background: #fff3e0; padding: 20px; border-radius: 10px; text-align: center;">
            <h4>📈 Forecast ({target_month_name[:3]})</h4>
            <h2>{forecast_qty:,.0f}</h2>
            <p style="color: {growth_color};">{growth_arrow} {abs(growth_pct)*100:.0f}% vs last year</p>
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
    
    # Detailed breakdown
    st.divider()
    st.subheader("📋 Calculation Breakdown")
    
    st.markdown(f"""
    | Step | Calculation | Result |
    |------|-------------|--------|
    | 1. Last Year Sales | {last_year_month_name} | **{last_year_qty:,.0f}** servings |
    | 2. Apply Growth | {last_year_qty:,.0f} × (1 + {growth_pct*100:.0f}%) | **{forecast_qty:,.0f}** servings |
    | 3. Raw Material Needed | {forecast_qty:,.0f} × {usage_per_serving}{unit} ÷ {yield_pct*100:.0f}% | **{raw_display:,.1f} {display_unit}** |
    | 4. Add Safety Stock | {raw_display:,.1f} × (1 + {safety_stock_pct*100:.0f}%) | **{display_amount:,.1f} {display_unit}** |
    """)
    
    # Summary message
    st.success(f"""
    **Summary:** Last {last_year_month_name[:3]} you sold **{last_year_qty:,}** {ingredient} dishes. 
    With **{growth_pct*100:+.0f}%** growth, expect **{forecast_qty:,.0f}** servings. 
    You need to order **{display_amount:,.1f} {display_unit}** (including {safety_stock_pct*100:.0f}% safety stock).
    """)
    
    # Seasonality reference
    with st.expander("📊 Seasonality Reference (Historical Patterns)"):
        st.markdown("Based on typical Kyoto tourism patterns:")
        
        season_data = []
        for month, factor in SEASONALITY_FACTORS.items():
            month_name = datetime(2025, month, 1).strftime('%b')
            season_data.append({
                'Month': month_name,
                'Factor': factor,
                'Index': int(factor * 100)
            })
        
        season_df = pd.DataFrame(season_data)
        
        fig = px.bar(season_df, x='Month', y='Index',
                    title="Monthly Seasonality Index (100 = Average)",
                    color='Index',
                    color_continuous_scale=['#f44336', '#ffeb3b', '#4caf50'])
        fig.add_hline(y=100, line_dash="dash", line_color="gray")
        fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# TASTING MENU ANALYZER TAB
# =============================================================================
def display_tasting_menu_analyzer():
    """
    Tasting Menu Cost Analyzer
    Allows editing costs and shows margin impact
    """
    st.header("🍽️ Tasting Menu Analyzer / コースメニュー分析")
    st.markdown("Analyze and adjust course menu costs")
    
    # Select menu
    menu_names = list(TASTING_MENU_RECIPES.keys())
    selected_menu = st.selectbox(
        "Select Tasting Menu / メニューを選択",
        options=menu_names
    )
    
    menu = TASTING_MENU_RECIPES[selected_menu]
    selling_price = menu['selling_price']
    target_cost_pct = menu['target_food_cost_percent']
    
    st.markdown(f"**{selected_menu}** ({menu['menu_name_jp']})")
    st.markdown(f"Selling Price: **¥{selling_price:,}** | Target Food Cost: **{target_cost_pct}%**")
    
    st.divider()
    
    # Editable course costs
    st.subheader("📝 Course Components (Editable)")
    st.caption("Adjust costs to see impact on margin")
    
    # Create editable dataframe
    course_data = []
    for course in menu['courses']:
        course_data.append({
            'Course #': course['course_number'],
            'Name': course['name'],
            'Name (JP)': course['name_jp'],
            'Est. Cost (¥)': course['estimated_food_cost'],
            'Key Ingredients': ', '.join(course['key_ingredients'][:2])
        })
    
    course_df = pd.DataFrame(course_data)
    
    # Use session state for edited costs
    if f'costs_{selected_menu}' not in st.session_state:
        st.session_state[f'costs_{selected_menu}'] = {
            c['name']: c['estimated_food_cost'] for c in menu['courses']
        }
    
    edited_costs = st.session_state[f'costs_{selected_menu}']
    
    # Display editable table
    cols = st.columns([1, 3, 2, 2])
    cols[0].markdown("**#**")
    cols[1].markdown("**Course**")
    cols[2].markdown("**Cost (¥)**")
    cols[3].markdown("**Ingredients**")
    
    new_costs = {}
    for course in menu['courses']:
        cols = st.columns([1, 3, 2, 2])
        cols[0].write(course['course_number'])
        cols[1].write(f"{course['name']}")
        
        new_cost = cols[2].number_input(
            f"cost_{course['course_number']}",
            min_value=0, max_value=10000,
            value=edited_costs.get(course['name'], course['estimated_food_cost']),
            label_visibility="collapsed",
            key=f"cost_input_{selected_menu}_{course['course_number']}"
        )
        new_costs[course['name']] = new_cost
        
        cols[3].caption(', '.join(course['key_ingredients'][:2]))
    
    st.session_state[f'costs_{selected_menu}'] = new_costs
    
    st.divider()
    
    # Calculate totals
    total_cost = sum(new_costs.values())
    food_cost_pct = (total_cost / selling_price) * 100
    gross_margin = selling_price - total_cost
    gross_margin_pct = (gross_margin / selling_price) * 100
    
    # Display results
    st.subheader("📊 Margin Analysis")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Selling Price", f"¥{selling_price:,}")
    
    with col2:
        st.metric("Total Food Cost", f"¥{total_cost:,}")
    
    with col3:
        delta_cost = food_cost_pct - target_cost_pct
        st.metric("Food Cost %", f"{food_cost_pct:.1f}%",
                 delta=f"{delta_cost:+.1f}%" if abs(delta_cost) > 0.5 else None,
                 delta_color="inverse")
    
    with col4:
        st.metric("Gross Margin", f"¥{gross_margin:,}", 
                 help=f"{gross_margin_pct:.1f}%")
    
    # Warning if cost too high
    if food_cost_pct > FOOD_COST_WARNING_THRESHOLD:
        st.markdown(f"""
        <div class="warning-box">
            ⚠️ <strong>Warning:</strong> Food cost ({food_cost_pct:.1f}%) exceeds {FOOD_COST_WARNING_THRESHOLD}% threshold!
            Consider reducing ingredient costs or adjusting menu price.
        </div>
        """, unsafe_allow_html=True)
    elif food_cost_pct <= target_cost_pct:
        st.markdown(f"""
        <div class="success-box">
            ✅ <strong>On Target:</strong> Food cost ({food_cost_pct:.1f}%) is within target ({target_cost_pct}%)
        </div>
        """, unsafe_allow_html=True)
    
    # Cost breakdown chart
    st.subheader("📈 Cost Breakdown")
    
    breakdown_data = pd.DataFrame([
        {'Component': name, 'Cost': cost}
        for name, cost in new_costs.items()
    ])
    breakdown_data = breakdown_data.sort_values('Cost', ascending=True)
    
    fig = px.bar(breakdown_data, y='Component', x='Cost', orientation='h',
                title="Cost by Course",
                color='Cost',
                color_continuous_scale=['#4caf50', '#ffeb3b', '#f44336'])
    fig.update_layout(coloraxis_showscale=False, height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    # Reset button
    if st.button("Reset to Original Costs"):
        st.session_state[f'costs_{selected_menu}'] = {
            c['name']: c['estimated_food_cost'] for c in menu['courses']
        }
        st.rerun()


# =============================================================================
# VENDOR ITEMS TAB
# =============================================================================
def display_vendor_items(invoices_df):
    """Display vendor items summary"""
    st.header("📋 Vendor Items")
    
    if invoices_df.empty:
        st.info("No invoice data available")
        return
    
    vendors = invoices_df['vendor'].unique()
    
    for vendor in vendors:
        st.subheader(f"🏪 {vendor}")
        vendor_items = invoices_df[invoices_df['vendor'] == vendor]
        
        summary = vendor_items.groupby('item_name').agg({
            'quantity': 'sum',
            'amount': 'sum',
            'date': ['min', 'max', 'count']
        }).reset_index()
        summary.columns = ['Item', 'Total Qty', 'Total Amount', 'First', 'Last', 'Orders']
        summary['Total Amount'] = summary['Total Amount'].apply(lambda x: f"¥{x:,.0f}")
        
        st.dataframe(summary, use_container_width=True)
        st.divider()


if __name__ == "__main__":
    main()
