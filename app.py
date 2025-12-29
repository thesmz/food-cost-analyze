"""
Purchasing Evaluation System for The Shinmonzen
Analyzes ingredient purchases vs dish sales to evaluate waste and cost efficiency
With Supabase database integration for persistent storage
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import re
from datetime import datetime, date, timedelta
from io import StringIO

# Import our modules
from extractors import extract_sales_data, extract_invoice_data
from config import VENDOR_CONFIG, DISH_INGREDIENT_MAP, MENU_ITEMS, DEFAULT_TARGETS, FORECAST_CONFIG
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

# Custom CSS for bilingual support
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
        margin: 5px 0;
    }
    .db-status-disconnected {
        padding: 10px;
        background: #f8d7da;
        border-radius: 5px;
        color: #721c24;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)


def main():
    st.title("🍽️ Purchasing Evaluation System")
    st.markdown("**購買評価システム** | The Shinmonzen")
    
    # Initialize session state for file uploader reset
    if 'upload_key' not in st.session_state:
        st.session_state.upload_key = 0
    
    # Initialize Supabase
    supabase = init_supabase()
    
    # Sidebar
    with st.sidebar:
        # Database status
        st.header("💾 Database / データベース")
        if supabase:
            summary = get_data_summary(supabase)
            st.markdown('<div class="db-status-connected">✅ Connected / 接続中</div>', unsafe_allow_html=True)
            st.caption(f"📊 {summary.get('invoice_count', 0)} invoices, {summary.get('sales_count', 0)} sales records")
            if summary.get('min_date') and summary.get('max_date'):
                st.caption(f"📅 {summary['min_date']} ~ {summary['max_date']}")
            # Show total beef in entire database (no filter)
            if summary.get('beef_total_in_db'):
                st.caption(f"🥩 Total Beef in DB: **{summary['beef_total_in_db']:.0f}** dishes")
        else:
            st.markdown('<div class="db-status-disconnected">❌ Not connected / 未接続</div>', unsafe_allow_html=True)
            st.caption("Using file upload only")
        
        st.divider()
        
        # Date range filter
        st.header("📅 Date Filter / 期間フィルター")
        
        # Get available date range from database
        if supabase:
            db_min_date, db_max_date = get_date_range(supabase)
        else:
            db_min_date, db_max_date = None, None
        
        # Show available data range
        if db_min_date and db_max_date:
            st.caption(f"📊 Data available: {db_min_date} ~ {db_max_date}")
        
        # Initialize session state for dates if not set
        if 'filter_start' not in st.session_state:
            if db_min_date:
                st.session_state.filter_start = db_min_date.replace(day=1)
            else:
                st.session_state.filter_start = date.today().replace(day=1)
        
        if 'filter_end' not in st.session_state:
            if db_max_date:
                # Get last day of max date's month
                if db_max_date.month == 12:
                    st.session_state.filter_end = date(db_max_date.year, 12, 31)
                else:
                    next_month = db_max_date.replace(day=1, month=db_max_date.month + 1)
                    st.session_state.filter_end = next_month - timedelta(days=1)
            else:
                st.session_state.filter_end = date.today()
        
        # Update session state if database range expanded
        if db_min_date and st.session_state.filter_start > db_min_date:
            st.session_state.filter_start = db_min_date.replace(day=1)
        if db_max_date:
            month_end = date(db_max_date.year, 12, 31) if db_max_date.month == 12 else (db_max_date.replace(day=1, month=db_max_date.month + 1) - timedelta(days=1))
            if st.session_state.filter_end < month_end:
                st.session_state.filter_end = month_end
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "From / 開始日",
                value=st.session_state.filter_start,
                min_value=date(2020, 1, 1),
                max_value=date.today(),
                key="date_start_input"
            )
            st.session_state.filter_start = start_date
        with col2:
            end_date = st.date_input(
                "To / 終了日",
                value=st.session_state.filter_end,
                min_value=date(2020, 1, 1),
                max_value=date(2030, 12, 31),
                key="date_end_input"
            )
            st.session_state.filter_end = end_date
        
        # Quick date presets
        st.caption("Quick select / クイック選択:")
        preset_col1, preset_col2, preset_col3 = st.columns(3)
        with preset_col1:
            if st.button("This Month", use_container_width=True):
                st.session_state.filter_start = date.today().replace(day=1)
                st.session_state.filter_end = date.today()
                st.rerun()
        with preset_col2:
            if st.button("Last Month", use_container_width=True):
                last_month = date.today().replace(day=1) - timedelta(days=1)
                st.session_state.filter_start = last_month.replace(day=1)
                st.session_state.filter_end = last_month
                st.rerun()
        with preset_col3:
            if st.button("All Data", use_container_width=True):
                if db_min_date and db_max_date:
                    st.session_state.filter_start = db_min_date.replace(day=1)
                    if db_max_date.month == 12:
                        st.session_state.filter_end = date(db_max_date.year, 12, 31)
                    else:
                        st.session_state.filter_end = db_max_date.replace(day=1, month=db_max_date.month + 1) - timedelta(days=1)
                    st.rerun()
        
        st.divider()
        
        # File upload section
        st.header("📁 Upload Data / データアップロード")
        
        sales_files = st.file_uploader(
            "Sales Reports (CSV) / 売上レポート",
            type=['csv'],
            accept_multiple_files=True,
            help="Upload Item Sales CSV files from POS system",
            key=f"sales_uploader_{st.session_state.upload_key}"
        )
        
        invoice_files = st.file_uploader(
            "Invoices (PDF/Excel) / 請求書",
            type=['pdf', 'xlsx', 'xls'],
            accept_multiple_files=True,
            help="Upload vendor invoices (PDF or Excel)",
            key=f"invoice_uploader_{st.session_state.upload_key}"
        )
        
        # Process and save uploaded files
        if sales_files or invoice_files:
            if st.button("💾 Save to Database / データベースに保存", type="primary", use_container_width=True):
                if not supabase:
                    st.error("Database not connected. Configure Supabase in Streamlit secrets.")
                else:
                    saved_invoices = 0
                    saved_sales = 0
                    
                    # Progress bar
                    progress_text = st.empty()
                    progress_bar = st.progress(0)
                    
                    total_files = len(invoice_files) + len(sales_files)
                    processed = 0
                    
                    # Process invoices
                    for inv in invoice_files:
                        progress_text.text(f"Processing invoice: {inv.name}...")
                        try:
                            invoice_data = extract_invoice_data(inv)
                            if invoice_data:
                                saved_invoices += save_invoices(supabase, invoice_data)
                        except Exception as e:
                            st.warning(f"Error processing {inv.name}: {e}")
                        processed += 1
                        progress_bar.progress(processed / total_files)
                    
                    # Process sales
                    for sf in sales_files:
                        progress_text.text(f"Processing sales: {sf.name}...")
                        try:
                            sales_df = extract_sales_data(sf)
                            if sales_df is not None and not sales_df.empty:
                                saved_sales += save_sales(supabase, sales_df)
                        except Exception as e:
                            st.warning(f"Error processing {sf.name}: {e}")
                        processed += 1
                        progress_bar.progress(processed / total_files)
                    
                    progress_bar.progress(100)
                    progress_text.empty()
                    st.success(f"✅ Saved {saved_invoices} invoices, {saved_sales} sales records")
                    
                    # Clear file uploaders by incrementing the key
                    st.session_state.upload_key += 1
                    st.rerun()
        
        st.divider()
        
        # Settings
        st.subheader("⚙️ Settings / 設定")
        
        beef_per_serving = st.number_input(
            "Beef per serving (g) / 1人前の牛肉量",
            min_value=50, max_value=500, value=180,
            help="Grams of beef tenderloin per Beef Tenderloin dish"
        )
        
        caviar_per_serving = st.number_input(
            "Caviar per serving (g) / 1人前のキャビア量",
            min_value=5, max_value=50, value=15,
            help="Grams of caviar per Egg Toast Caviar dish"
        )
        
        # Data management (expandable)
        with st.expander("🗑️ Data Management / データ管理"):
            st.warning("⚠️ Danger zone / 危険ゾーン")
            if st.button("Delete data in selected date range", type="secondary"):
                if supabase:
                    deleted = delete_data_by_date_range(supabase, start_date, end_date)
                    st.info(f"Deleted {deleted['invoices']} invoices, {deleted['sales']} sales")
                    st.rerun()
    
    # Main content area - Load data from database or files
    sales_df = pd.DataFrame()
    invoices_df = pd.DataFrame()
    
    # Check if database has ANY data (regardless of date filter)
    db_has_data = False
    if supabase:
        summary = get_data_summary(supabase)
        db_has_data = (summary.get('invoice_count', 0) > 0 or summary.get('sales_count', 0) > 0)
    
    if supabase and db_has_data:
        # Load from database with date filter
        invoices_df = load_invoices(supabase, start_date, end_date)
        sales_df = load_sales(supabase, start_date, end_date)
        
        # Show message if no data in selected period (but DB has data)
        if sales_df.empty and invoices_df.empty:
            st.warning(f"⚠️ No data found for period {start_date} to {end_date}. Try adjusting the date filter.")
            st.info("💡 Your database has data from other periods. Use the date filter in the sidebar to view it.")
            return
    
    # Only show preview mode if database is empty or not connected
    elif sales_files or invoice_files:
        st.info("📤 Preview mode: Showing uploaded file data. Click 'Save to Database' to persist.")
        
        # Process files for preview
        all_sales = []
        for sf in sales_files:
            try:
                sf.seek(0)  # Reset file pointer
                temp_sales = extract_sales_data(sf)
                if temp_sales is not None:
                    all_sales.append(temp_sales)
            except Exception as e:
                st.warning(f"Error processing {sf.name}: {e}")
        
        all_invoices = []
        for inv in invoice_files:
            try:
                inv.seek(0)  # Reset file pointer
                invoice_data = extract_invoice_data(inv)
                if invoice_data:
                    all_invoices.extend(invoice_data)
            except Exception as e:
                st.warning(f"Error processing {inv.name}: {e}")
        
        sales_df = pd.concat(all_sales, ignore_index=True) if all_sales else pd.DataFrame()
        invoices_df = pd.DataFrame(all_invoices) if all_invoices else pd.DataFrame()
    
    else:
        # Show welcome message
        st.info("👆 Please upload sales reports and invoices in the sidebar, or view existing data from the database.")
        st.info("👆 サイドバーから売上レポートと請求書をアップロードするか、データベースの既存データを表示してください。")
        
        with st.expander("📖 How this system works / システムの使い方"):
            st.markdown("""
            ### Analysis Flow / 分析フロー
            
            1. **Upload Data / データアップロード**
               - Sales CSV from POS system / POSシステムからの売上CSV
               - Vendor invoices (PDF) / 仕入先請求書 (PDF)
            
            2. **Save to Database / データベースに保存**
               - Data is stored persistently / データは永続的に保存されます
               - No need to re-upload each time / 毎回アップロードする必要はありません
            
            3. **Filter by Date / 期間でフィルター**
               - View specific time periods / 特定の期間を表示
               - Compare months / 月別比較
            
            4. **Analysis / 分析**
               - **Waste Ratio**: (Purchased - Expected Usage) / Purchased
               - **Cost Efficiency**: Ingredient Cost / Dish Revenue
            
            ### Vendor Mapping / 仕入先マッピング
            | Vendor / 仕入先 | Ingredient / 食材 | Dish / 料理 |
            |----------------|-------------------|-------------|
            | Meat Shop Hirayama / ミートショップひら山 | 和牛ヒレ (Wagyu Tenderloin) | Beef Tenderloin |
            | French F&B Japan / フレンチ・エフ・アンド・ビー | KAVIARI キャビア | Egg Toast Caviar |
            """)
        return
    
    # Show current data period
    st.caption(f"📅 Filtering: **{start_date}** to **{end_date}**")
    
    # Show database summary for debugging
    if supabase:
        with st.expander("📊 Data Summary / データ概要", expanded=False):
            col_a, col_b = st.columns(2)
            with col_a:
                st.write(f"**Sales records loaded:** {len(sales_df)}")
                st.write(f"**Invoice records loaded:** {len(invoices_df)}")
            with col_b:
                if not sales_df.empty and 'date' in sales_df.columns:
                    unique_dates = sales_df['date'].unique()
                    st.write(f"**Unique dates in data:** {sorted(unique_dates)}")
            
            # Show Beef Tenderloin count specifically
            if not sales_df.empty:
                beef = sales_df[sales_df['name'].str.contains('Beef Tenderloin', case=False, na=False)]
                st.write(f"**Beef Tenderloin:** {len(beef)} rows, **{beef['qty'].sum():.0f} dishes total**")
                
                # Show by date
                if 'date' in beef.columns:
                    beef_by_date = beef.groupby('date')['qty'].sum().reset_index()
                    st.write("**Beef by date:**")
                    st.dataframe(beef_by_date, use_container_width=True)
    
    # Display tabs for different analyses
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Overview / 概要",
        "🥩 Beef Analysis / 牛肉分析", 
        "🐟 Caviar Analysis / キャビア分析",
        "📈 Menu Engineering / メニュー分析",
        "🔮 Forecasting / 発注予測",
        "📋 Vendor Items / 仕入先品目"
    ])
    
    with tab1:
        display_overview(sales_df, invoices_df, beef_per_serving, caviar_per_serving)
    
    with tab2:
        display_beef_analysis(sales_df, invoices_df, beef_per_serving)
    
    with tab3:
        display_caviar_analysis(sales_df, invoices_df, caviar_per_serving)
    
    with tab4:
        display_menu_engineering(sales_df)
    
    with tab5:
        display_forecasting(sales_df, invoices_df, beef_per_serving, caviar_per_serving)
    
    with tab6:
        display_vendor_items(invoices_df)


def display_overview(sales_df, invoices_df, beef_per_serving, caviar_per_serving):
    """Display overview dashboard"""
    st.header("📊 Overview / 概要")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🥩 Beef Tenderloin")
        if not sales_df.empty:
            beef_sales = sales_df[sales_df['name'].str.contains('Beef Tenderloin', case=False, na=False)]
            total_beef_qty = beef_sales['qty'].sum()
            
            # Calculate revenue with fixed dinner price ¥5,682
            beef_dinner_price = 5682
            beef_sales_calc = beef_sales.copy()
            beef_sales_calc['calc_price'] = beef_sales_calc.apply(
                lambda row: beef_dinner_price if row['price'] == 0 or pd.isna(row['price']) else row['price'],
                axis=1
            )
            beef_sales_calc['calc_revenue'] = beef_sales_calc.apply(
                lambda row: row['net_total'] if row['net_total'] != 0 else row['qty'] * row['calc_price'],
                axis=1
            )
            total_beef_revenue = beef_sales_calc['calc_revenue'].sum()
            
            expected_beef_kg = (total_beef_qty * beef_per_serving) / 1000
            
            st.metric("Dishes Sold / 販売数", f"{total_beef_qty:.0f}")
            st.metric("Revenue / 売上", f"¥{total_beef_revenue:,.0f}")
            st.metric("Expected Usage / 予想使用量", f"{expected_beef_kg:.2f} kg")
    
    with col2:
        st.subheader("🐟 Egg Toast Caviar")
        if not sales_df.empty:
            caviar_sales = sales_df[sales_df['name'].str.contains('Egg Toast Caviar', case=False, na=False)]
            total_caviar_qty = caviar_sales['qty'].sum()
            
            # Calculate revenue with fixed dinner price (same as lunch price)
            caviar_dinner_price = 3247  # Course item estimate
            caviar_sales_calc = caviar_sales.copy()
            caviar_sales_calc['calc_price'] = caviar_sales_calc.apply(
                lambda row: caviar_dinner_price if row['price'] == 0 or pd.isna(row['price']) else row['price'],
                axis=1
            )
            caviar_sales_calc['calc_revenue'] = caviar_sales_calc.apply(
                lambda row: row['net_total'] if row['net_total'] != 0 else row['qty'] * row['calc_price'],
                axis=1
            )
            total_caviar_revenue = caviar_sales_calc['calc_revenue'].sum()
            
            expected_caviar_g = total_caviar_qty * caviar_per_serving
            
            st.metric("Dishes Sold / 販売数", f"{total_caviar_qty:.0f}")
            st.metric("Revenue / 売上", f"¥{total_caviar_revenue:,.0f}")
            st.metric("Expected Usage / 予想使用量", f"{expected_caviar_g:.0f} g")
    
    # Purchase summary
    st.subheader("💰 Purchase Summary / 仕入概要")
    if not invoices_df.empty:
        # Group by vendor
        vendor_summary = invoices_df.groupby('vendor').agg({
            'amount': 'sum'
        }).reset_index()
        vendor_summary.columns = ['Vendor / 仕入先', 'Total / 合計']
        vendor_summary['Total / 合計'] = vendor_summary['Total / 合計'].apply(lambda x: f"¥{x:,.0f}")
        st.dataframe(vendor_summary, use_container_width=True)
        
        # Total purchases
        total_purchases = invoices_df['amount'].sum()
        st.metric("Total Purchases / 仕入合計", f"¥{total_purchases:,.0f}")
    else:
        st.info("No invoice data in selected period")


def display_beef_analysis(sales_df, invoices_df, beef_per_serving):
    """Detailed beef tenderloin analysis with yield-adjusted calculations"""
    st.header("🥩 Beef Tenderloin Analysis / 牛肉分析")
    
    # Get yield percentage from config (default to 1.0 if not found)
    yield_percent = DISH_INGREDIENT_MAP.get('Beef Tenderloin', {}).get('yield_percent', 1.0)
    if yield_percent <= 0:
        yield_percent = 1.0  # Prevent division by zero
    
    # Filter beef data
    beef_sales = sales_df[sales_df['name'].str.contains('Beef Tenderloin', case=False, na=False)] if not sales_df.empty else pd.DataFrame()
    beef_invoices = invoices_df[invoices_df['item_name'].str.contains('ヒレ|フィレ|tenderloin|牛', case=False, na=False)] if not invoices_df.empty else pd.DataFrame()
    
    if beef_sales.empty and beef_invoices.empty:
        st.warning("No beef data available for analysis in selected period")
        return
    
    # Show yield info
    st.info(f"📐 **Yield Rate / 歩留まり率:** {yield_percent*100:.0f}% (cooked portion from raw purchase)")
    
    col1, col2, col3 = st.columns(3)
    
    # Fixed price for Beef Tenderloin Dinner course items
    beef_dinner_price = DISH_INGREDIENT_MAP.get('Beef Tenderloin', {}).get('selling_price', 5682)
    
    # Calculate metrics
    total_sold = beef_sales['qty'].sum() if not beef_sales.empty else 0
    
    # Calculate revenue including estimated revenue for course items
    if not beef_sales.empty:
        beef_sales_calc = beef_sales.copy()
        beef_sales_calc['calc_price'] = beef_sales_calc.apply(
            lambda row: beef_dinner_price if row['price'] == 0 or pd.isna(row['price']) else row['price'],
            axis=1
        )
        beef_sales_calc['calc_revenue'] = beef_sales_calc.apply(
            lambda row: row['net_total'] if row['net_total'] != 0 else row['qty'] * row['calc_price'],
            axis=1
        )
        total_revenue = beef_sales_calc['calc_revenue'].sum()
    else:
        total_revenue = 0
    
    # YIELD-ADJUSTED Expected Usage: How much RAW meat needed for the cooked portions
    # Formula: (Qty Sold * Serving Size) / Yield Percent
    expected_usage_g = (total_sold * beef_per_serving) / yield_percent
    expected_usage_kg = expected_usage_g / 1000
    
    # Also show the cooked portion for reference
    cooked_portion_kg = (total_sold * beef_per_serving) / 1000
    
    # Calculate purchases
    if not beef_invoices.empty:
        total_purchased_kg = beef_invoices['quantity'].sum()
        total_cost = beef_invoices['amount'].sum()
    else:
        total_purchased_kg = 0
        total_cost = 0
    
    with col1:
        st.metric("Total Sold / 販売総数", f"{total_sold:.0f} servings")
        st.metric("Total Revenue / 売上合計", f"¥{total_revenue:,.0f}")
    
    with col2:
        st.metric("Total Purchased / 仕入総量", f"{total_purchased_kg:.2f} kg")
        st.metric("Total Cost / 仕入原価", f"¥{total_cost:,.0f}")
    
    with col3:
        # Yield-adjusted waste ratio
        if total_purchased_kg > 0:
            waste_ratio = max(0, (total_purchased_kg - expected_usage_kg) / total_purchased_kg * 100)
            target_waste = DEFAULT_TARGETS['beef']['waste_ratio_target']
            st.metric("Waste Ratio / ロス率", f"{waste_ratio:.1f}%",
                     delta=f"{waste_ratio - target_waste:.1f}%" if waste_ratio > target_waste else None,
                     delta_color="inverse")
        
        if total_revenue > 0:
            cost_ratio = (total_cost / total_revenue) * 100
            target_cost = DEFAULT_TARGETS['beef']['cost_ratio_target']
            st.metric("Cost Ratio / 原価率", f"{cost_ratio:.1f}%",
                     delta=f"{cost_ratio - target_cost:.1f}%" if cost_ratio > target_cost else None,
                     delta_color="inverse")
    
    # Usage comparison chart with yield breakdown
    st.subheader("📈 Usage Comparison / 使用量比較")
    
    st.caption(f"※ Cooked portion: {cooked_portion_kg:.2f} kg → Raw needed (at {yield_percent*100:.0f}% yield): {expected_usage_kg:.2f} kg")
    
    comparison_data = pd.DataFrame({
        'Category': ['Purchased\n仕入量', 'Expected Raw\n必要量(生)', 'Cooked Portion\n調理済(参考)', 'Variance\n差異'],
        'Amount (kg)': [total_purchased_kg, expected_usage_kg, cooked_portion_kg, max(0, total_purchased_kg - expected_usage_kg)]
    })
    
    fig = px.bar(comparison_data, x='Category', y='Amount (kg)', 
                 color='Category',
                 color_discrete_sequence=['#3366cc', '#ff9900', '#109618', '#dc3912'])
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    
    # Detailed invoice breakdown
    if not beef_invoices.empty:
        st.subheader("📋 Purchase Details / 仕入明細")
        display_df = beef_invoices[['date', 'item_name', 'quantity', 'unit', 'amount']].copy()
        display_df.columns = ['Date/日付', 'Item/品目', 'Qty/数量', 'Unit/単位', 'Amount/金額']
        display_df['Amount/金額'] = display_df['Amount/金額'].apply(lambda x: f"¥{x:,.0f}")
        st.dataframe(display_df, use_container_width=True)
    
    # Detailed sales breakdown
    if not beef_sales.empty:
        st.subheader("🍽️ Sales Details / 売上明細")
        sales_display = beef_sales[['code', 'name', 'category', 'qty', 'price', 'net_total']].copy()
        
        # Apply fixed price for Dinner items, keep original for others
        sales_display['price'] = sales_display.apply(
            lambda row: beef_dinner_price if (row['price'] == 0 or pd.isna(row['price'])) else row['price'], 
            axis=1
        )
        
        # Calculate revenue: use net_total if exists, otherwise qty * price
        sales_display['net_total'] = sales_display.apply(
            lambda row: row['net_total'] if row['net_total'] != 0 else row['qty'] * row['price'],
            axis=1
        )
        
        sales_display.columns = ['Code/コード', 'Item/品目', 'Category/カテゴリ', 'Qty/数量', 'Price/単価', 'Revenue/売上']
        sales_display['Price/単価'] = sales_display['Price/単価'].apply(lambda x: f"¥{x:,.0f}")
        sales_display['Revenue/売上'] = sales_display['Revenue/売上'].apply(lambda x: f"¥{x:,.0f}")
        
        # Add note about estimated prices
        st.caption("※ Dinner course items: estimated at ¥5,682/dish")
        st.dataframe(sales_display, use_container_width=True)
        
        # Summary by category
        st.subheader("📊 Sales by Category / カテゴリ別売上")
        beef_sales_summary = beef_sales.copy()
        # Use fixed dinner price where price is 0
        beef_sales_summary['calc_price'] = beef_sales_summary.apply(
            lambda row: beef_dinner_price if row['price'] == 0 or pd.isna(row['price']) else row['price'],
            axis=1
        )
        # Then calculate revenue: use net_total if exists, otherwise qty * price
        beef_sales_summary['calc_revenue'] = beef_sales_summary.apply(
            lambda row: row['net_total'] if row['net_total'] != 0 else row['qty'] * row['calc_price'],
            axis=1
        )
        category_summary = beef_sales_summary.groupby('category').agg({
            'qty': 'sum',
            'calc_revenue': 'sum'
        }).reset_index()
        category_summary.columns = ['Category/カテゴリ', 'Qty/数量', 'Revenue/売上']
        category_summary['Revenue/売上'] = category_summary['Revenue/売上'].apply(lambda x: f"¥{x:,.0f}")
        st.dataframe(category_summary, use_container_width=True)


def display_caviar_analysis(sales_df, invoices_df, caviar_per_serving):
    """Detailed caviar analysis with yield-adjusted calculations"""
    st.header("🐟 Caviar Analysis / キャビア分析")
    
    # Get yield percentage from config (default to 1.0 if not found)
    yield_percent = DISH_INGREDIENT_MAP.get('Egg Toast Caviar', {}).get('yield_percent', 1.0)
    if yield_percent <= 0:
        yield_percent = 1.0  # Prevent division by zero
    
    # Filter caviar data
    caviar_sales = sales_df[sales_df['name'].str.contains('Egg Toast Caviar', case=False, na=False)] if not sales_df.empty else pd.DataFrame()
    caviar_invoices = invoices_df[invoices_df['item_name'].str.contains('キャビア|KAVIARI|caviar', case=False, na=False)] if not invoices_df.empty else pd.DataFrame()
    
    if caviar_sales.empty and caviar_invoices.empty:
        st.warning("No caviar data available for analysis in selected period")
        return
    
    # Show yield info
    st.info(f"📐 **Yield Rate / 歩留まり率:** {yield_percent*100:.0f}% (no trimming loss)")
    
    col1, col2, col3 = st.columns(3)
    
    # Course price estimation
    estimated_course_item_price = DISH_INGREDIENT_MAP.get('Egg Toast Caviar', {}).get('selling_price', 3247)
    
    # Calculate metrics
    total_sold = caviar_sales['qty'].sum() if not caviar_sales.empty else 0
    
    # Calculate revenue including estimated revenue for course items
    if not caviar_sales.empty:
        caviar_sales_calc = caviar_sales.copy()
        caviar_sales_calc['calc_price'] = caviar_sales_calc.apply(
            lambda row: estimated_course_item_price if row['price'] == 0 or pd.isna(row['price']) else row['price'],
            axis=1
        )
        caviar_sales_calc['calc_revenue'] = caviar_sales_calc.apply(
            lambda row: row['net_total'] if row['net_total'] != 0 else row['qty'] * row['calc_price'],
            axis=1
        )
        total_revenue = caviar_sales_calc['calc_revenue'].sum()
    else:
        total_revenue = 0
    
    # YIELD-ADJUSTED Expected Usage
    expected_usage_g = (total_sold * caviar_per_serving) / yield_percent
    
    # Caviar is typically sold in 100g units, but quantity may be in grams or units
    if not caviar_invoices.empty:
        total_qty = caviar_invoices['quantity'].sum()
        if total_qty > 100:
            total_purchased_g = total_qty
        else:
            total_purchased_g = total_qty * 100
        total_purchased_units = total_purchased_g / 100
        total_cost = caviar_invoices['amount'].sum()
    else:
        total_purchased_g = 0
        total_purchased_units = 0
        total_cost = 0
    
    with col1:
        st.metric("Total Sold / 販売総数", f"{total_sold:.0f} servings")
        st.metric("Total Revenue / 売上合計", f"¥{total_revenue:,.0f}")
    
    with col2:
        st.metric("Total Purchased / 仕入総量", f"{total_purchased_g:.0f} g ({total_purchased_units:.0f} units)")
        st.metric("Total Cost / 仕入原価", f"¥{total_cost:,.0f}")
    
    with col3:
        if total_purchased_g > 0:
            waste_ratio = max(0, (total_purchased_g - expected_usage_g) / total_purchased_g * 100)
            target_waste = DEFAULT_TARGETS['caviar']['waste_ratio_target']
            st.metric("Waste Ratio / ロス率", f"{waste_ratio:.1f}%",
                     delta=f"{waste_ratio - target_waste:.1f}%" if waste_ratio > target_waste else None,
                     delta_color="inverse")
        
        if total_revenue > 0:
            cost_ratio = (total_cost / total_revenue) * 100
            target_cost = DEFAULT_TARGETS['caviar']['cost_ratio_target']
            st.metric("Cost Ratio / 原価率", f"{cost_ratio:.1f}%",
                     delta=f"{cost_ratio - target_cost:.1f}%" if cost_ratio > target_cost else None,
                     delta_color="inverse")
    
    # Usage comparison chart
    st.subheader("📈 Usage Comparison / 使用量比較")
    
    comparison_data = pd.DataFrame({
        'Category': ['Purchased\n仕入量', 'Expected Usage\n予想使用量', 'Potential Waste\n予想ロス'],
        'Amount (g)': [total_purchased_g, expected_usage_g, max(0, total_purchased_g - expected_usage_g)]
    })
    
    fig = px.bar(comparison_data, x='Category', y='Amount (g)', 
                 color='Category',
                 color_discrete_sequence=['#3366cc', '#109618', '#dc3912'])
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    
    # Detailed invoice breakdown
    if not caviar_invoices.empty:
        st.subheader("📋 Purchase Details / 仕入明細")
        display_df = caviar_invoices[['date', 'item_name', 'amount']].copy()
        display_df.columns = ['Date/日付', 'Item/品目', 'Amount/金額']
        display_df['Amount/金額'] = display_df['Amount/金額'].apply(lambda x: f"¥{x:,.0f}")
        st.dataframe(display_df, use_container_width=True)
    
    # Detailed sales breakdown
    if not caviar_sales.empty:
        st.subheader("🍽️ Sales Details / 売上明細")
        sales_display = caviar_sales[['code', 'name', 'category', 'qty', 'price', 'net_total']].copy()
        
        # Calculate estimated price for course items (Dinner category with 0 price)
        # Assume 6-course menu at ¥19,480.44
        course_price = 19480.44
        num_courses = 6
        estimated_course_item_price = course_price / num_courses
        
        # Apply estimated price only where price is 0 or missing
        sales_display['price'] = sales_display.apply(
            lambda row: estimated_course_item_price if row['price'] == 0 or pd.isna(row['price']) else row['price'], 
            axis=1
        )
        
        # Calculate revenue: use net_total if exists, otherwise qty * price
        sales_display['net_total'] = sales_display.apply(
            lambda row: row['net_total'] if row['net_total'] != 0 else row['qty'] * row['price'],
            axis=1
        )
        
        sales_display.columns = ['Code/コード', 'Item/品目', 'Category/カテゴリ', 'Qty/数量', 'Price/単価', 'Revenue/売上']
        sales_display['Price/単価'] = sales_display['Price/単価'].apply(lambda x: f"¥{x:,.0f}")
        sales_display['Revenue/売上'] = sales_display['Revenue/売上'].apply(lambda x: f"¥{x:,.0f}")
        
        # Add note about estimated prices
        st.caption("※ Dinner course items: estimated at ¥19,480 ÷ 6 courses = ¥3,247/dish")
        st.dataframe(sales_display, use_container_width=True)
        
        # Summary by category
        st.subheader("📊 Sales by Category / カテゴリ別売上")
        caviar_sales_summary = caviar_sales.copy()
        # First fill in price where missing
        caviar_sales_summary['calc_price'] = caviar_sales_summary.apply(
            lambda row: estimated_course_item_price if row['price'] == 0 or pd.isna(row['price']) else row['price'],
            axis=1
        )
        # Then calculate revenue: use net_total if exists, otherwise qty * price
        caviar_sales_summary['calc_revenue'] = caviar_sales_summary.apply(
            lambda row: row['net_total'] if row['net_total'] != 0 else row['qty'] * row['calc_price'],
            axis=1
        )
        category_summary = caviar_sales_summary.groupby('category').agg({
            'qty': 'sum',
            'calc_revenue': 'sum'
        }).reset_index()
        category_summary.columns = ['Category/カテゴリ', 'Qty/数量', 'Revenue/売上']
        category_summary['Revenue/売上'] = category_summary['Revenue/売上'].apply(lambda x: f"¥{x:,.0f}")
        st.dataframe(category_summary, use_container_width=True)


def display_menu_engineering(sales_df):
    """
    Menu Engineering Analysis - BCG Matrix style scatter plot
    Analyzes item popularity (qty sold) vs profitability (margin)
    """
    st.header("📈 Menu Engineering / メニュー分析")
    st.markdown("**BCG Matrix Analysis** - Identify Stars, Plowhorses, Puzzles, and Dogs")
    
    if sales_df.empty:
        st.warning("No sales data available for Menu Engineering analysis")
        return
    
    # Aggregate sales by item
    item_sales = sales_df.groupby('name').agg({
        'qty': 'sum',
        'net_total': 'sum',
        'price': 'mean'
    }).reset_index()
    
    # Calculate metrics for each item
    menu_data = []
    
    for _, row in item_sales.iterrows():
        item_name = row['name']
        qty_sold = row['qty']
        total_revenue = row['net_total']
        avg_price = row['price'] if row['price'] > 0 else (total_revenue / qty_sold if qty_sold > 0 else 0)
        
        # Get cost data from config if available, otherwise estimate
        if item_name in MENU_ITEMS:
            item_config = MENU_ITEMS[item_name]
            selling_price = item_config.get('selling_price', avg_price)
            food_cost = item_config.get('estimated_food_cost', selling_price * 0.30)
        elif item_name in DISH_INGREDIENT_MAP:
            dish_config = DISH_INGREDIENT_MAP[item_name]
            selling_price = dish_config.get('selling_price', avg_price)
            # Estimate food cost at 30% if not specified
            food_cost = selling_price * 0.30
        else:
            selling_price = avg_price if avg_price > 0 else 1000
            food_cost = selling_price * 0.30  # Assume 30% food cost
        
        # Calculate unit margin (profit per item)
        unit_margin = selling_price - food_cost
        
        # Total contribution
        total_contribution = unit_margin * qty_sold
        
        menu_data.append({
            'Item / 品目': item_name,
            'Qty Sold / 販売数': qty_sold,
            'Unit Margin / 単品利益': unit_margin,
            'Total Revenue / 総売上': total_revenue,
            'Total Contribution / 総貢献利益': total_contribution,
            'Selling Price / 販売価格': selling_price,
            'Food Cost / 原価': food_cost
        })
    
    menu_df = pd.DataFrame(menu_data)
    
    if menu_df.empty:
        st.warning("No menu items found for analysis")
        return
    
    # Calculate averages for quadrant lines
    avg_qty = menu_df['Qty Sold / 販売数'].mean()
    avg_margin = menu_df['Unit Margin / 単品利益'].mean()
    
    # Classify items into quadrants
    def classify_item(row):
        high_qty = row['Qty Sold / 販売数'] >= avg_qty
        high_margin = row['Unit Margin / 単品利益'] >= avg_margin
        
        if high_qty and high_margin:
            return '⭐ Star / スター'
        elif high_qty and not high_margin:
            return '🐴 Plowhorse / 稼ぎ頭'
        elif not high_qty and high_margin:
            return '❓ Puzzle / パズル'
        else:
            return '🐕 Dog / ドッグ'
    
    menu_df['Quadrant / 分類'] = menu_df.apply(classify_item, axis=1)
    
    # Create scatter plot
    fig = px.scatter(
        menu_df,
        x='Qty Sold / 販売数',
        y='Unit Margin / 単品利益',
        color='Quadrant / 分類',
        size='Total Revenue / 総売上',
        hover_name='Item / 品目',
        hover_data={
            'Total Revenue / 総売上': ':,.0f',
            'Selling Price / 販売価格': ':,.0f',
            'Food Cost / 原価': ':,.0f'
        },
        color_discrete_map={
            '⭐ Star / スター': '#FFD700',
            '🐴 Plowhorse / 稼ぎ頭': '#4CAF50',
            '❓ Puzzle / パズル': '#2196F3',
            '🐕 Dog / ドッグ': '#9E9E9E'
        }
    )
    
    # Add reference lines for quadrants
    fig.add_hline(y=avg_margin, line_dash="dash", line_color="gray", 
                  annotation_text=f"Avg Margin: ¥{avg_margin:,.0f}")
    fig.add_vline(x=avg_qty, line_dash="dash", line_color="gray",
                  annotation_text=f"Avg Qty: {avg_qty:.0f}")
    
    # Add quadrant labels
    max_qty = menu_df['Qty Sold / 販売数'].max()
    max_margin = menu_df['Unit Margin / 単品利益'].max()
    min_margin = menu_df['Unit Margin / 単品利益'].min()
    
    fig.add_annotation(x=max_qty * 0.75, y=max_margin * 0.9, text="⭐ STARS", showarrow=False, font=dict(size=14, color="gold"))
    fig.add_annotation(x=max_qty * 0.75, y=min_margin + (avg_margin - min_margin) * 0.3, text="🐴 PLOWHORSES", showarrow=False, font=dict(size=14, color="green"))
    fig.add_annotation(x=avg_qty * 0.3, y=max_margin * 0.9, text="❓ PUZZLES", showarrow=False, font=dict(size=14, color="blue"))
    fig.add_annotation(x=avg_qty * 0.3, y=min_margin + (avg_margin - min_margin) * 0.3, text="🐕 DOGS", showarrow=False, font=dict(size=14, color="gray"))
    
    fig.update_layout(
        title="Menu Engineering Matrix / メニューエンジニアリングマトリクス",
        xaxis_title="Popularity (Qty Sold) / 人気度（販売数）",
        yaxis_title="Profitability (Unit Margin ¥) / 収益性（単品利益）",
        height=600
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Quadrant explanation
    st.markdown("""
    ### Quadrant Guide / 分類ガイド
    | Quadrant | Description | Action |
    |----------|-------------|--------|
    | ⭐ **Stars / スター** | High popularity + High profit | Maintain & promote |
    | 🐴 **Plowhorses / 稼ぎ頭** | High popularity + Low profit | Consider price increase |
    | ❓ **Puzzles / パズル** | Low popularity + High profit | Increase marketing |
    | 🐕 **Dogs / ドッグ** | Low popularity + Low profit | Consider removing |
    """)
    
    # Summary table
    st.subheader("📋 Item Details / 品目詳細")
    
    display_df = menu_df[['Item / 品目', 'Quadrant / 分類', 'Qty Sold / 販売数', 
                          'Unit Margin / 単品利益', 'Total Contribution / 総貢献利益']].copy()
    display_df['Unit Margin / 単品利益'] = display_df['Unit Margin / 単品利益'].apply(lambda x: f"¥{x:,.0f}")
    display_df['Total Contribution / 総貢献利益'] = display_df['Total Contribution / 総貢献利益'].apply(lambda x: f"¥{x:,.0f}")
    display_df = display_df.sort_values('Qty Sold / 販売数', ascending=False)
    
    st.dataframe(display_df, use_container_width=True)


def display_forecasting(sales_df, invoices_df, beef_per_serving, caviar_per_serving):
    """
    Predictive Purchasing - Forecast next month's ingredient needs
    """
    st.header("🔮 Predictive Purchasing / 発注予測")
    st.markdown("**Next Month Order Recommendation** based on historical sales data")
    
    if sales_df.empty:
        st.warning("No sales data available for forecasting. Upload at least one month of data.")
        return
    
    # Get safety stock percentage from config
    safety_stock = FORECAST_CONFIG.get('safety_stock_percent', 0.10)
    
    # Calculate historical data by month
    if 'date' not in sales_df.columns:
        st.error("Date column not found in sales data")
        return
    
    sales_df['month'] = pd.to_datetime(sales_df['date']).dt.to_period('M')
    months_available = sales_df['month'].nunique()
    
    st.info(f"📊 **Data Available:** {months_available} month(s) of historical data")
    
    # Beef Tenderloin Forecast
    st.subheader("🥩 Beef Tenderloin Forecast / 牛肉発注予測")
    
    beef_config = DISH_INGREDIENT_MAP.get('Beef Tenderloin', {})
    beef_yield = beef_config.get('yield_percent', 0.65)
    if beef_yield <= 0:
        beef_yield = 0.65
    
    beef_sales = sales_df[sales_df['name'].str.contains('Beef Tenderloin', case=False, na=False)]
    
    if not beef_sales.empty:
        # Calculate monthly sales
        beef_monthly = beef_sales.groupby('month')['qty'].sum()
        avg_monthly_qty = beef_monthly.mean()
        
        # Calculate raw material needed (yield-adjusted)
        raw_per_serving_g = beef_per_serving / beef_yield
        expected_raw_g = avg_monthly_qty * raw_per_serving_g
        expected_raw_kg = expected_raw_g / 1000
        
        # Add safety stock
        recommended_order_kg = expected_raw_kg * (1 + safety_stock)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Avg Monthly Sales / 月平均販売数",
                f"{avg_monthly_qty:.0f} servings"
            )
        
        with col2:
            st.metric(
                "Expected Usage / 予想使用量",
                f"{expected_raw_kg:.1f} kg",
                help=f"Based on {beef_per_serving}g serving / {beef_yield*100:.0f}% yield"
            )
        
        with col3:
            st.metric(
                "🎯 Recommended Order / 推奨発注量",
                f"{recommended_order_kg:.1f} kg",
                delta=f"+{safety_stock*100:.0f}% safety stock",
                delta_color="normal"
            )
        
        # Monthly trend chart
        if len(beef_monthly) > 1:
            trend_df = beef_monthly.reset_index()
            trend_df.columns = ['Month', 'Qty Sold']
            trend_df['Month'] = trend_df['Month'].astype(str)
            
            fig = px.bar(trend_df, x='Month', y='Qty Sold', 
                        title="Monthly Beef Tenderloin Sales / 月別牛肉販売数")
            fig.add_hline(y=avg_monthly_qty, line_dash="dash", line_color="red",
                         annotation_text=f"Avg: {avg_monthly_qty:.0f}")
            st.plotly_chart(fig, use_container_width=True)
        
        # Cost estimation
        if not invoices_df.empty:
            beef_invoices = invoices_df[invoices_df['item_name'].str.contains('ヒレ|フィレ|tenderloin|牛', case=False, na=False)]
            if not beef_invoices.empty:
                total_cost = beef_invoices['amount'].sum()
                total_kg = beef_invoices['quantity'].sum()
                if total_kg > 0:
                    avg_cost_per_kg = total_cost / total_kg
                    estimated_cost = recommended_order_kg * avg_cost_per_kg
                    st.metric("💰 Estimated Cost / 予想仕入コスト", f"¥{estimated_cost:,.0f}",
                             help=f"Based on avg ¥{avg_cost_per_kg:,.0f}/kg")
    else:
        st.info("No Beef Tenderloin sales data found")
    
    st.divider()
    
    # Caviar Forecast
    st.subheader("🐟 Caviar Forecast / キャビア発注予測")
    
    caviar_config = DISH_INGREDIENT_MAP.get('Egg Toast Caviar', {})
    caviar_yield = caviar_config.get('yield_percent', 1.0)
    if caviar_yield <= 0:
        caviar_yield = 1.0
    
    caviar_sales = sales_df[sales_df['name'].str.contains('Egg Toast Caviar', case=False, na=False)]
    
    if not caviar_sales.empty:
        # Calculate monthly sales
        caviar_monthly = caviar_sales.groupby('month')['qty'].sum()
        avg_monthly_qty = caviar_monthly.mean()
        
        # Calculate raw material needed (yield-adjusted)
        raw_per_serving_g = caviar_per_serving / caviar_yield
        expected_raw_g = avg_monthly_qty * raw_per_serving_g
        
        # Add safety stock
        recommended_order_g = expected_raw_g * (1 + safety_stock)
        recommended_order_units = recommended_order_g / 100  # 100g per unit
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Avg Monthly Sales / 月平均販売数",
                f"{avg_monthly_qty:.0f} servings"
            )
        
        with col2:
            st.metric(
                "Expected Usage / 予想使用量",
                f"{expected_raw_g:.0f} g",
                help=f"Based on {caviar_per_serving}g serving / {caviar_yield*100:.0f}% yield"
            )
        
        with col3:
            st.metric(
                "🎯 Recommended Order / 推奨発注量",
                f"{recommended_order_g:.0f} g ({recommended_order_units:.0f} units)",
                delta=f"+{safety_stock*100:.0f}% safety stock",
                delta_color="normal"
            )
        
        # Monthly trend chart
        if len(caviar_monthly) > 1:
            trend_df = caviar_monthly.reset_index()
            trend_df.columns = ['Month', 'Qty Sold']
            trend_df['Month'] = trend_df['Month'].astype(str)
            
            fig = px.bar(trend_df, x='Month', y='Qty Sold',
                        title="Monthly Caviar Sales / 月別キャビア販売数")
            fig.add_hline(y=avg_monthly_qty, line_dash="dash", line_color="red",
                         annotation_text=f"Avg: {avg_monthly_qty:.0f}")
            st.plotly_chart(fig, use_container_width=True)
        
        # Cost estimation
        if not invoices_df.empty:
            caviar_invoices = invoices_df[invoices_df['item_name'].str.contains('キャビア|KAVIARI|caviar', case=False, na=False)]
            if not caviar_invoices.empty:
                total_cost = caviar_invoices['amount'].sum()
                total_g = caviar_invoices['quantity'].sum()
                if total_g < 100:  # Probably in units
                    total_g = total_g * 100
                if total_g > 0:
                    avg_cost_per_g = total_cost / total_g
                    estimated_cost = recommended_order_g * avg_cost_per_g
                    st.metric("💰 Estimated Cost / 予想仕入コスト", f"¥{estimated_cost:,.0f}",
                             help=f"Based on avg ¥{avg_cost_per_g:,.0f}/g")
    else:
        st.info("No Caviar sales data found")
    
    # Summary recommendation card
    st.divider()
    st.subheader("📋 Order Summary / 発注サマリー")
    
    summary_data = []
    
    if not beef_sales.empty:
        beef_monthly = beef_sales.groupby('month')['qty'].sum()
        avg_beef = beef_monthly.mean()
        raw_beef_kg = (avg_beef * beef_per_serving / beef_yield / 1000) * (1 + safety_stock)
        summary_data.append({
            'Item / 品目': '🥩 Beef Tenderloin / 和牛ヒレ',
            'Avg Monthly Sales / 月平均販売': f"{avg_beef:.0f}",
            'Recommended Order / 推奨発注': f"{raw_beef_kg:.1f} kg",
            'Yield / 歩留まり': f"{beef_yield*100:.0f}%"
        })
    
    if not caviar_sales.empty:
        caviar_monthly = caviar_sales.groupby('month')['qty'].sum()
        avg_caviar = caviar_monthly.mean()
        raw_caviar_g = (avg_caviar * caviar_per_serving / caviar_yield) * (1 + safety_stock)
        summary_data.append({
            'Item / 品目': '🐟 Caviar / キャビア',
            'Avg Monthly Sales / 月平均販売': f"{avg_caviar:.0f}",
            'Recommended Order / 推奨発注': f"{raw_caviar_g:.0f} g ({raw_caviar_g/100:.0f} units)",
            'Yield / 歩留まり': f"{caviar_yield*100:.0f}%"
        })
    
    if summary_data:
        st.dataframe(pd.DataFrame(summary_data), use_container_width=True)
        
        st.caption(f"※ Includes {safety_stock*100:.0f}% safety stock buffer / 安全在庫{safety_stock*100:.0f}%含む")


def display_vendor_items(invoices_df):
    """Display all items by vendor"""
    st.header("📋 Vendor Items List / 仕入先品目一覧")
    
    if invoices_df.empty:
        st.info("No invoice data available in selected period. Upload PDF invoices to see vendor items.")
        return
    
    # Group by vendor
    vendors = invoices_df['vendor'].unique()
    
    for vendor in vendors:
        st.subheader(f"🏪 {vendor}")
        vendor_items = invoices_df[invoices_df['vendor'] == vendor]
        
        # Summary table
        summary = vendor_items.groupby('item_name').agg({
            'quantity': 'sum',
            'amount': 'sum',
            'date': ['min', 'max', 'count']
        }).reset_index()
        summary.columns = ['Item/品目', 'Total Qty/総数量', 'Total Amount/合計金額', 
                          'First Order/初回', 'Last Order/最終', 'Order Count/注文回数']
        summary['Total Amount/合計金額'] = summary['Total Amount/合計金額'].apply(lambda x: f"¥{x:,.0f}")
        
        st.dataframe(summary, use_container_width=True)
        
        # Detailed view expander
        with st.expander(f"View all transactions / 全取引を表示"):
            detail_df = vendor_items[['date', 'item_name', 'quantity', 'unit', 'unit_price', 'amount']].copy()
            detail_df.columns = ['Date/日付', 'Item/品目', 'Qty/数量', 'Unit/単位', 'Unit Price/単価', 'Amount/金額']
            detail_df['Amount/金額'] = detail_df['Amount/金額'].apply(lambda x: f"¥{x:,.0f}" if pd.notna(x) else "")
            st.dataframe(detail_df, use_container_width=True)
        
        st.divider()


if __name__ == "__main__":
    main()
