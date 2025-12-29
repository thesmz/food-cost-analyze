"""
Purchasing Evaluation System for The Shinmonzen
Analyzes ingredient purchases vs dish sales to evaluate waste and cost efficiency
Original Analysis: Beef Tenderloin & Caviar
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta

# Import our modules
from extractors import extract_sales_data, extract_invoice_data
from config import VENDOR_CONFIG, DISH_INGREDIENT_MAP, DEFAULT_TARGETS
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
</style>
""", unsafe_allow_html=True)


def main():
    st.title("🍽️ The Shinmonzen - Purchasing Evaluation")
    st.markdown("*Ingredient Cost & Waste Analysis*")
    
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
        st.subheader("💾 Database")
        if supabase:
            summary = get_data_summary(supabase)
            st.markdown('<div class="db-status-connected">✅ Connected</div>', unsafe_allow_html=True)
            st.caption(f"📊 {summary.get('invoice_count', 0)} invoices, {summary.get('sales_count', 0)} sales")
            if summary.get('min_date') and summary.get('max_date'):
                st.caption(f"📅 {summary['min_date']} ~ {summary['max_date']}")
        else:
            st.markdown('<div class="db-status-disconnected">❌ Not connected</div>', unsafe_allow_html=True)
        
        st.divider()
        
        # Date filter
        st.subheader("📅 Date Filter / 期間選択")
        
        db_min_date, db_max_date = None, None
        if supabase:
            db_min_date, db_max_date = get_date_range(supabase)
            if db_min_date and db_max_date:
                st.caption(f"Data: {db_min_date} ~ {db_max_date}")
        
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
            "Beef per serving (g) / 1人前の牛肉量",
            min_value=50, max_value=500, value=150,
            help="Grams of beef tenderloin per serving"
        )
        
        caviar_per_serving = st.number_input(
            "Caviar per serving (g) / 1人前のキャビア量",
            min_value=5, max_value=50, value=10,
            help="Grams of caviar per serving"
        )
        
        st.divider()
        
        # File upload
        st.subheader("📁 Upload Data")
        
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
        with st.expander("🗑️ Data Management / データ管理"):
            st.warning("⚠️ Danger zone / 危険ゾーン")
            if st.button("Delete data in selected range", type="secondary"):
                if supabase:
                    deleted = delete_data_by_date_range(supabase, start_date, end_date)
                    st.info(f"Deleted {deleted['invoices']} invoices, {deleted['sales']} sales")
                    st.rerun()
    
    # Main content
    sales_df = pd.DataFrame()
    invoices_df = pd.DataFrame()
    
    # Load from database
    db_has_data = False
    if supabase:
        summary = get_data_summary(supabase)
        db_has_data = (summary.get('invoice_count', 0) > 0 or summary.get('sales_count', 0) > 0)
    
    if supabase and db_has_data:
        invoices_df = load_invoices(supabase, start_date, end_date)
        sales_df = load_sales(supabase, start_date, end_date)
    
    # Process uploaded files
    if sales_files or invoice_files:
        with st.spinner("Processing files..."):
            if sales_files:
                sales_list = []
                for file in sales_files:
                    df = extract_sales_data(file)
                    if not df.empty:
                        sales_list.append(df)
                if sales_list:
                    new_sales = pd.concat(sales_list, ignore_index=True)
                    if supabase:
                        save_sales(supabase, new_sales)
                    sales_df = pd.concat([sales_df, new_sales], ignore_index=True) if not sales_df.empty else new_sales
            
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
            st.success("✅ Files processed!")
            st.rerun()
    
    # Check data
    if sales_df.empty and invoices_df.empty:
        st.info("📤 Upload sales reports and invoices to begin, or adjust date filter.")
        return
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Overview / 概要",
        "🥩 Beef Analysis / 牛肉分析",
        "🐟 Caviar Analysis / キャビア分析",
        "📋 Vendor Items / 仕入先品目"
    ])
    
    with tab1:
        display_overview(sales_df, invoices_df, beef_per_serving, caviar_per_serving)
    
    with tab2:
        display_beef_analysis(sales_df, invoices_df, beef_per_serving)
    
    with tab3:
        display_caviar_analysis(sales_df, invoices_df, caviar_per_serving)
    
    with tab4:
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
            
            caviar_price = 3247
            caviar_sales_calc = caviar_sales.copy()
            caviar_sales_calc['calc_price'] = caviar_sales_calc.apply(
                lambda row: caviar_price if row['price'] == 0 or pd.isna(row['price']) else row['price'],
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
    st.divider()
    st.subheader("📦 Purchase Summary / 仕入サマリー")
    
    if not invoices_df.empty:
        vendor_summary = invoices_df.groupby('vendor').agg({
            'amount': 'sum',
            'item_name': 'nunique'
        }).reset_index()
        vendor_summary.columns = ['Vendor/仕入先', 'Total Amount/合計金額', 'Items/品目数']
        vendor_summary['Total Amount/合計金額'] = vendor_summary['Total Amount/合計金額'].apply(lambda x: f"¥{x:,.0f}")
        st.dataframe(vendor_summary, use_container_width=True)
        
        total_purchases = invoices_df['amount'].sum()
        st.metric("Total Purchases / 仕入合計", f"¥{total_purchases:,.0f}")
    else:
        st.info("No invoice data in selected period")


def display_beef_analysis(sales_df, invoices_df, beef_per_serving):
    """Detailed beef tenderloin analysis"""
    st.header("🥩 Beef Tenderloin Analysis / 牛肉分析")
    
    # Filter beef data
    beef_sales = sales_df[sales_df['name'].str.contains('Beef Tenderloin', case=False, na=False)] if not sales_df.empty else pd.DataFrame()
    beef_invoices = invoices_df[invoices_df['item_name'].str.contains('ヒレ|フィレ|tenderloin|牛', case=False, na=False)] if not invoices_df.empty else pd.DataFrame()
    
    if beef_sales.empty and beef_invoices.empty:
        st.warning("No beef data available for analysis in selected period")
        return
    
    col1, col2, col3 = st.columns(3)
    
    # Fixed price for Beef Tenderloin Dinner course items
    beef_dinner_price = 5682
    
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
    
    expected_usage_g = total_sold * beef_per_serving
    expected_usage_kg = expected_usage_g / 1000
    
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
        if total_purchased_kg > 0:
            waste_ratio = max(0, (total_purchased_kg - expected_usage_kg) / total_purchased_kg * 100)
            st.metric("Waste Ratio / ロス率", f"{waste_ratio:.1f}%",
                     delta=f"{waste_ratio - 35:.1f}%" if waste_ratio > 35 else None,
                     delta_color="inverse")
        
        if total_revenue > 0:
            cost_ratio = (total_cost / total_revenue) * 100
            st.metric("Cost Ratio / 原価率", f"{cost_ratio:.1f}%",
                     delta=f"{cost_ratio - 30:.1f}%" if cost_ratio > 30 else None,
                     delta_color="inverse")
    
    # Usage comparison chart
    st.subheader("📈 Usage Comparison / 使用量比較")
    
    comparison_data = pd.DataFrame({
        'Category': ['Purchased\n仕入量', 'Expected Usage\n予想使用量', 'Potential Waste\n予想ロス'],
        'Amount (kg)': [total_purchased_kg, expected_usage_kg, max(0, total_purchased_kg - expected_usage_kg)]
    })
    
    fig = px.bar(comparison_data, x='Category', y='Amount (kg)', 
                 color='Category',
                 color_discrete_sequence=['#3366cc', '#109618', '#dc3912'])
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    
    # Detailed invoice breakdown
    if not beef_invoices.empty:
        st.subheader("📋 Purchase Details / 仕入明細")
        display_df = beef_invoices[['date', 'item_name', 'quantity', 'unit', 'amount']].copy()
        display_df.columns = ['Date/日付', 'Item/品目', 'Qty/数量', 'Unit/単位', 'Amount/金額']
        display_df['Amount/金額'] = display_df['Amount/金額'].apply(lambda x: f"¥{x:,.0f}")
        st.dataframe(display_df, use_container_width=True)
    
    # Sales breakdown by category
    if not beef_sales.empty:
        st.subheader("📊 Sales Breakdown / 販売内訳")
        if 'category' in beef_sales.columns:
            beef_sales_calc = beef_sales.copy()
            beef_sales_calc['calc_price'] = beef_sales_calc.apply(
                lambda row: beef_dinner_price if row['price'] == 0 or pd.isna(row['price']) else row['price'],
                axis=1
            )
            beef_sales_calc['calc_revenue'] = beef_sales_calc.apply(
                lambda row: row['net_total'] if row['net_total'] != 0 else row['qty'] * row['calc_price'],
                axis=1
            )
            category_summary = beef_sales_calc.groupby('category').agg({
                'qty': 'sum',
                'calc_revenue': 'sum'
            }).reset_index()
            category_summary.columns = ['Category/カテゴリ', 'Qty/数量', 'Revenue/売上']
            category_summary['Revenue/売上'] = category_summary['Revenue/売上'].apply(lambda x: f"¥{x:,.0f}")
            st.dataframe(category_summary, use_container_width=True)


def display_caviar_analysis(sales_df, invoices_df, caviar_per_serving):
    """Detailed caviar analysis"""
    st.header("🐟 Caviar Analysis / キャビア分析")
    
    # Filter caviar data
    caviar_sales = sales_df[sales_df['name'].str.contains('Egg Toast Caviar', case=False, na=False)] if not sales_df.empty else pd.DataFrame()
    caviar_invoices = invoices_df[invoices_df['item_name'].str.contains('キャビア|KAVIARI|caviar', case=False, na=False)] if not invoices_df.empty else pd.DataFrame()
    
    if caviar_sales.empty and caviar_invoices.empty:
        st.warning("No caviar data available for analysis in selected period")
        return
    
    col1, col2, col3 = st.columns(3)
    
    # Course price estimation
    estimated_course_item_price = 3247
    
    # Calculate metrics
    total_sold = caviar_sales['qty'].sum() if not caviar_sales.empty else 0
    
    # Calculate revenue
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
    
    expected_usage_g = total_sold * caviar_per_serving
    
    # Caviar purchases
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
            st.metric("Waste Ratio / ロス率", f"{waste_ratio:.1f}%",
                     delta=f"{waste_ratio - 10:.1f}%" if waste_ratio > 10 else None,
                     delta_color="inverse")
        
        if total_revenue > 0:
            cost_ratio = (total_cost / total_revenue) * 100
            st.metric("Cost Ratio / 原価率", f"{cost_ratio:.1f}%",
                     delta=f"{cost_ratio - 25:.1f}%" if cost_ratio > 25 else None,
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
        display_df = caviar_invoices[['date', 'item_name', 'quantity', 'unit_price', 'amount']].copy()
        display_df.columns = ['Date/日付', 'Item/品目', 'Qty/数量', 'Unit Price/単価', 'Amount/金額']
        display_df['Unit Price/単価'] = display_df['Unit Price/単価'].apply(lambda x: f"¥{x:,.0f}")
        display_df['Amount/金額'] = display_df['Amount/金額'].apply(lambda x: f"¥{x:,.0f}")
        st.dataframe(display_df, use_container_width=True)


def display_vendor_items(invoices_df):
    """Display all items by vendor"""
    st.header("📋 Vendor Items List / 仕入先品目一覧")
    
    if invoices_df.empty:
        st.info("No invoice data available. Upload PDF invoices to see vendor items.")
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
        summary.columns = ['Item/品目', 'Total Qty/総数量', 'Total Amount/合計金額', 
                          'First Order/初回', 'Last Order/最終', 'Order Count/注文回数']
        summary['Total Amount/合計金額'] = summary['Total Amount/合計金額'].apply(lambda x: f"¥{x:,.0f}")
        
        st.dataframe(summary, use_container_width=True)
        st.divider()


if __name__ == "__main__":
    main()
