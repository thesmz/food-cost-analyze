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
from extractors import extract_sales_data, extract_invoice_data, get_debug_log
from config import YIELD_RATES, THRESHOLDS, get_total_yield, get_butchery_yield, get_cooking_yield
from utils import (
    calculate_revenue, convert_quantity_to_grams, convert_quantity_to_kg,
    get_yield_rate, calculate_raw_needed, calculate_yield_from_raw
)
from database import (
    init_supabase, save_invoices, save_sales, 
    load_invoices, load_sales, get_date_range, get_data_summary,
    delete_data_by_date_range, get_unique_vendors, delete_invoices_by_vendor,
    seed_reference_data
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
    if 'upload_completed' not in st.session_state:
        st.session_state.upload_completed = False
    if 'upload_message' not in st.session_state:
        st.session_state.upload_message = ""
    if 'upload_error' not in st.session_state:
        st.session_state.upload_error = ""
    
    # Initialize Supabase
    supabase = init_supabase()
    
    # Sidebar - Navigation & Database Status Only
    with st.sidebar:
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
        
        # File upload in sidebar
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
            
            # Delete by date range
            st.markdown("**Delete by Date Range:**")
            if st.button("Delete data in selected range", type="secondary"):
                if supabase:
                    deleted = delete_data_by_date_range(supabase, start_date, end_date)
                    st.info(f"Deleted {deleted['invoices']} invoices, {deleted['sales']} sales")
                    st.rerun()
            
            st.markdown("---")
            
            # Delete by vendor
            st.markdown("**Delete Invoices by Vendor:**")
            if supabase:
                vendors = get_unique_vendors(supabase)
                if vendors:
                    selected_vendors = st.multiselect(
                        "Select vendors to delete",
                        options=vendors,
                        help="Select one or more vendors to delete all their invoices"
                    )
                    
                    if selected_vendors:
                        st.warning(f"⚠️ Will delete ALL invoices from: {', '.join(selected_vendors)}")
                        if st.button("🗑️ DELETE Selected Vendors", type="primary"):
                            total_deleted = 0
                            for vendor in selected_vendors:
                                count = delete_invoices_by_vendor(supabase, vendor)
                                total_deleted += count
                                st.write(f"  • {vendor}: {count} records deleted")
                            st.success(f"✅ Total deleted: {total_deleted} invoice records")
                            st.cache_data.clear()
                            st.rerun()
                else:
                    st.info("No vendors found in database")
            
            st.markdown("---")
            
            # Seed reference data
            st.markdown("**🌱 Seed Reference Data (Oct 2025):**")
            st.caption("Load baseline test data from reference_data_oct2025.py")
            if st.button("Load Reference Data", type="secondary"):
                if supabase:
                    with st.spinner("Loading reference data..."):
                        results = seed_reference_data(supabase)
                    if 'error' in results:
                        st.error(f"Error: {results['error']}")
                    else:
                        st.success(f"✅ Loaded {results['invoices']} invoice records, {results['sales']} sales records")
                        st.cache_data.clear()
                        st.rerun()
                else:
                    st.error("Database not connected")
    
    # =========================================================================
    # MAIN PAGE - Configuration & Settings Expander (MOVED FROM SIDEBAR)
    # =========================================================================
    with st.expander("⚙️ Configuration & Settings / 設定", expanded=False):
        st.markdown("### 🥩 Beef Tenderloin Settings")
        st.caption("Yield Flow: **RAW** → (butchery) → **TRIMMED** → (cooking) → **COOKED**")
        
        beef_col1, beef_col2, beef_col3, beef_col4 = st.columns(4)
        
        with beef_col1:
            beef_per_serving = st.number_input(
                "Portion per serving (g)",
                min_value=50, max_value=500, value=150,
                help="COOKED weight per serving (what goes on the plate)"
            )
        
        with beef_col2:
            # Default butchery yield from config
            default_butchery = int(get_butchery_yield('beef_tenderloin') * 100)
            beef_butchery_pct = st.slider(
                "Butchery Yield (%)",
                min_value=40, max_value=100, value=default_butchery,
                help=f"Raw → Trimmed. Removes fat, silverskin, chain. Default {default_butchery}%"
            ) / 100
        
        with beef_col3:
            # Default cooking yield from config
            default_cooking = int(get_cooking_yield('beef_tenderloin') * 100)
            beef_cooking_pct = st.slider(
                "Cooking Yield (%)",
                min_value=60, max_value=100, value=default_cooking,
                help=f"Trimmed → Cooked. Moisture/fat loss. Default {default_cooking}%"
            ) / 100
        
        with beef_col4:
            # Show calculated total yield
            beef_total_yield = beef_butchery_pct * beef_cooking_pct
            st.metric(
                "Total Yield",
                f"{beef_total_yield*100:.0f}%",
                help="Butchery × Cooking"
            )
            st.caption(f"100kg raw → {beef_total_yield*100:.0f}kg cooked")
        
        st.markdown("---")
        st.markdown("### 🐟 Caviar Settings")
        
        caviar_col1, caviar_col2 = st.columns(2)
        
        with caviar_col1:
            caviar_per_serving = st.number_input(
                "Caviar per serving (g)",
                min_value=5, max_value=50, value=10,
                help="Grams of caviar per serving"
            )
        
        with caviar_col2:
            # Caviar has no loss
            caviar_yield_pct = 1.0
            st.metric("Caviar Yield", "100%", help="No processing loss")
    
    # =========================================================================
    # SHOW UPLOAD SUCCESS/ERROR MESSAGES (Persistent across reruns)
    # =========================================================================
    if st.session_state.upload_completed:
        st.success(st.session_state.upload_message)
        # Clear the flag after showing (user can dismiss by refreshing)
        if st.button("Dismiss", key="dismiss_success"):
            st.session_state.upload_completed = False
            st.session_state.upload_message = ""
            st.rerun()
    
    if st.session_state.upload_error:
        st.error(st.session_state.upload_error)
        if st.button("Dismiss Error", key="dismiss_error"):
            st.session_state.upload_error = ""
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
    
    # Handle file uploads - show Save button BEFORE processing
    if sales_files or invoice_files:
        st.subheader("📤 Files Ready to Process")
        
        # Show what files are selected
        if sales_files:
            st.write(f"**Sales files:** {', '.join([f.name for f in sales_files])}")
        if invoice_files:
            st.write(f"**Invoice files:** {', '.join([f.name for f in invoice_files])}")
        
        st.warning("⚠️ Files will be processed and saved to database when you click Save.")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            save_clicked = st.button("💾 Save to Database", type="primary", use_container_width=True)
        with col2:
            st.caption("Or upload different files to replace selection")
        
        # Only process if Save button clicked
        if save_clicked:
            debug_messages = []
            
            try:
                total_files = len(sales_files or []) + len(invoice_files or [])
                progress_bar = st.progress(0, text="Processing files...")
                current_file = 0
                sales_count = 0
                invoice_count = 0
                
                # Process sales files
                if sales_files:
                    sales_list = []
                    for file in sales_files:
                        current_file += 1
                        progress_bar.progress(current_file / total_files, text=f"Processing {file.name}...")
                        debug_messages.append(f"📄 {file.name}")
                        
                        df = extract_sales_data(file)
                        extractor_log = get_debug_log()
                        debug_messages.extend(extractor_log)
                        
                        if isinstance(df, pd.DataFrame) and not df.empty:
                            sales_list.append(df)
                    
                    if sales_list:
                        new_sales = pd.concat(sales_list, ignore_index=True)
                        if supabase:
                            saved = save_sales(supabase, new_sales)
                            debug_messages.append(f"✅ Saved {saved} sales records")
                            sales_count = saved
                
                # Process invoice files
                if invoice_files:
                    invoice_records = []
                    for file in invoice_files:
                        current_file += 1
                        progress_bar.progress(current_file / total_files, text=f"Processing {file.name}...")
                        debug_messages.append(f"📄 {file.name}")
                        
                        records = extract_invoice_data(file)
                        extractor_log = get_debug_log()
                        debug_messages.extend(extractor_log)
                        
                        if isinstance(records, list) and len(records) > 0:
                            invoice_records.extend(records)
                        elif isinstance(records, pd.DataFrame) and not records.empty:
                            invoice_records.extend(records.to_dict('records'))
                    
                    if invoice_records:
                        new_invoices = pd.DataFrame(invoice_records)
                        if supabase:
                            saved = save_invoices(supabase, new_invoices)
                            debug_messages.append(f"✅ Saved {saved} invoice records")
                            invoice_count = saved
                
                progress_bar.progress(1.0, text="Complete!")
                
                # Show result
                st.success(f"✅ Saved {sales_count} sales, {invoice_count} invoices to database!")
                
                # Show debug log
                with st.expander("🔍 Processing Log", expanded=False):
                    for msg in debug_messages:
                        st.text(msg)
                
                # Clear and refresh
                st.session_state.upload_key += 1
                st.cache_data.clear()
                if st.button("🔄 Refresh to see data"):
                    st.rerun()
                    
            except Exception as e:
                import traceback
                st.error(f"❌ Error: {str(e)}")
                with st.expander("Error details"):
                    st.code(traceback.format_exc())
    
    # Check data
    if sales_df.empty and invoices_df.empty and not (sales_files or invoice_files):
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
        display_overview(sales_df, invoices_df, beef_per_serving, caviar_per_serving, 
                        beef_butchery_pct, beef_cooking_pct, caviar_yield_pct)
    
    with tab2:
        display_beef_analysis(sales_df, invoices_df, beef_per_serving, 
                             beef_butchery_pct, beef_cooking_pct)
    
    with tab3:
        display_caviar_analysis(sales_df, invoices_df, caviar_per_serving, caviar_yield_pct)
    
    with tab4:
        display_vendor_items(invoices_df)


def display_overview(sales_df, invoices_df, beef_per_serving, caviar_per_serving, 
                    beef_butchery_pct, beef_cooking_pct, caviar_yield_pct):
    """Display overview dashboard"""
    st.header("📊 Overview / 概要")
    
    beef_total_yield = beef_butchery_pct * beef_cooking_pct
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🥩 Beef Tenderloin")
        if not sales_df.empty:
            beef_sales = sales_df[sales_df['name'].str.contains('Beef Tenderloin', case=False, na=False)]
            total_beef_qty = beef_sales['qty'].sum()
            
            # Calculate revenue using helper (no hardcoded prices)
            beef_sales_calc = calculate_revenue(beef_sales)
            total_beef_revenue = beef_sales_calc['calculated_revenue'].sum()
            
            # Cooked beef needed for sales
            cooked_needed_kg = (total_beef_qty * beef_per_serving) / 1000
            
            # Work backwards: cooked → trimmed → raw
            trimmed_needed_kg = cooked_needed_kg / beef_cooking_pct if beef_cooking_pct > 0 else cooked_needed_kg
            raw_needed_kg = trimmed_needed_kg / beef_butchery_pct if beef_butchery_pct > 0 else trimmed_needed_kg
            
            st.metric("Dishes Sold / 販売数", f"{total_beef_qty:.0f}")
            st.metric("Revenue / 売上", f"¥{total_beef_revenue:,.0f}")
            st.metric("Cooked Needed / 必要量(調理後)", f"{cooked_needed_kg:.2f} kg")
            st.metric("Raw Needed / 必要量(生)", f"{raw_needed_kg:.2f} kg",
                     help=f"At {beef_total_yield*100:.0f}% total yield ({beef_butchery_pct*100:.0f}% × {beef_cooking_pct*100:.0f}%)")
    
    with col2:
        st.subheader("🐟 Egg Toast Caviar")
        if not sales_df.empty:
            caviar_sales = sales_df[sales_df['name'].str.contains('Egg Toast Caviar', case=False, na=False)]
            total_caviar_qty = caviar_sales['qty'].sum()
            
            # Calculate revenue using helper (no hardcoded prices)
            caviar_sales_calc = calculate_revenue(caviar_sales)
            total_caviar_revenue = caviar_sales_calc['calculated_revenue'].sum()
            
            # Caviar needed (100% yield)
            caviar_needed_g = total_caviar_qty * caviar_per_serving
            
            st.metric("Dishes Sold / 販売数", f"{total_caviar_qty:.0f}")
            st.metric("Revenue / 売上", f"¥{total_caviar_revenue:,.0f}")
            st.metric("Caviar Needed / 必要量", f"{caviar_needed_g:.0f} g",
                     help="100% yield - no processing loss")
    
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


def display_beef_analysis(sales_df, invoices_df, beef_per_serving, 
                         beef_butchery_pct, beef_cooking_pct):
    """
    Detailed beef tenderloin analysis with separate butchery and cooking yields.
    
    Yield Flow:
    PURCHASED (raw) → BUTCHERY → TRIMMED → COOKING → COOKED
    
    Analysis compares:
    - What we PURCHASED (raw kg)
    - What we could GET after processing (cooked kg)
    - What we NEEDED for sales (cooked kg)
    """
    st.header("🥩 Beef Tenderloin Analysis / 牛肉分析")
    
    beef_total_yield = beef_butchery_pct * beef_cooking_pct
    
    # Show yield info with breakdown
    st.info(f"""
    📐 **Yield Flow / 歩留まり:**
    • Butchery: {beef_butchery_pct*100:.0f}% (raw → trimmed)
    • Cooking: {beef_cooking_pct*100:.0f}% (trimmed → cooked)
    • **Total: {beef_total_yield*100:.0f}%** (raw → cooked)
    | **Serving Size / 1人前:** {beef_per_serving}g (cooked weight)
    """)
    
    # Filter beef data
    beef_sales = sales_df[sales_df['name'].str.contains('Beef Tenderloin', case=False, na=False)] if not sales_df.empty else pd.DataFrame()
    beef_invoices = invoices_df[invoices_df['item_name'].str.contains('ヒレ|フィレ|tenderloin|牛', case=False, na=False)] if not invoices_df.empty else pd.DataFrame()
    
    if beef_sales.empty and beef_invoices.empty:
        st.warning("No beef data available for analysis in selected period")
        return
    
    # ==========================================
    # CALCULATE FROM PURCHASED (FORWARD FLOW)
    # ==========================================
    
    # Get purchased amount from invoices (RAW)
    if not beef_invoices.empty:
        beef_invoices_calc = convert_quantity_to_kg(beef_invoices)
        purchased_raw_kg = beef_invoices_calc['quantity_kg'].sum()
        total_cost = beef_invoices['amount'].sum()
    else:
        purchased_raw_kg = 0
        total_cost = 0
    
    # Apply yields forward: RAW → TRIMMED → COOKED
    trimmed_kg = purchased_raw_kg * beef_butchery_pct
    cooked_available_kg = trimmed_kg * beef_cooking_pct
    
    # ==========================================
    # CALCULATE FROM SALES (WHAT WE NEEDED)
    # ==========================================
    
    total_sold = beef_sales['qty'].sum() if not beef_sales.empty else 0
    
    # Calculate revenue
    if not beef_sales.empty:
        beef_sales_calc = calculate_revenue(beef_sales)
        total_revenue = beef_sales_calc['calculated_revenue'].sum()
    else:
        total_revenue = 0
    
    # Cooked beef NEEDED for sales
    cooked_needed_kg = (total_sold * beef_per_serving) / 1000
    
    # For reference: how much raw WOULD we need to produce that cooked amount?
    raw_needed_kg = cooked_needed_kg / beef_total_yield if beef_total_yield > 0 else cooked_needed_kg
    
    # ==========================================
    # VARIANCE ANALYSIS
    # ==========================================
    
    # Variance in cooked terms (what matters for serving)
    cooked_variance_kg = cooked_available_kg - cooked_needed_kg
    
    # Variance in raw terms (purchase efficiency)
    raw_variance_kg = purchased_raw_kg - raw_needed_kg
    
    # Display metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("##### 📥 Purchased (Raw)")
        st.metric("Raw Purchased / 仕入量(生)", f"{purchased_raw_kg:.2f} kg")
        st.metric("Total Cost / 仕入原価", f"¥{total_cost:,.0f}")
        if purchased_raw_kg > 0:
            cost_per_kg = total_cost / purchased_raw_kg
            st.caption(f"@ ¥{cost_per_kg:,.0f}/kg raw")
    
    with col2:
        st.markdown("##### 🔪 After Processing")
        st.metric("Trimmed / 整形後", f"{trimmed_kg:.2f} kg",
                 help=f"{purchased_raw_kg:.2f}kg × {beef_butchery_pct*100:.0f}%")
        st.metric("Cooked Available / 調理後", f"{cooked_available_kg:.2f} kg",
                 help=f"{trimmed_kg:.2f}kg × {beef_cooking_pct*100:.0f}%")
        st.caption(f"Butchery loss: {purchased_raw_kg - trimmed_kg:.2f}kg")
        st.caption(f"Cooking loss: {trimmed_kg - cooked_available_kg:.2f}kg")
    
    with col3:
        st.markdown("##### 📊 Sales & Variance")
        st.metric("Dishes Sold / 販売数", f"{total_sold:.0f} servings")
        st.metric("Cooked Needed / 必要量", f"{cooked_needed_kg:.2f} kg",
                 help=f"{total_sold} × {beef_per_serving}g")
        
        # Variance indicator
        if cooked_variance_kg >= 0:
            st.metric("Surplus / 余剰", f"{cooked_variance_kg:.2f} kg",
                     delta="Stock buildup or waste",
                     delta_color="off")
        else:
            st.metric("Shortage / 不足", f"{abs(cooked_variance_kg):.2f} kg",
                     delta="Used inventory",
                     delta_color="inverse")
    
    # Efficiency ratios
    st.divider()
    ratio_col1, ratio_col2, ratio_col3 = st.columns(3)
    
    with ratio_col1:
        if total_revenue > 0:
            cost_ratio = (total_cost / total_revenue) * 100
            st.metric("Food Cost Ratio / 原価率", f"{cost_ratio:.1f}%",
                     delta=f"{'⚠️ High' if cost_ratio > 35 else '✅ OK'}",
                     delta_color="inverse" if cost_ratio > 35 else "normal")
    
    with ratio_col2:
        if purchased_raw_kg > 0:
            utilization = (cooked_needed_kg / cooked_available_kg * 100) if cooked_available_kg > 0 else 0
            st.metric("Utilization / 利用率", f"{utilization:.1f}%",
                     help="Cooked needed ÷ Cooked available")
    
    with ratio_col3:
        if total_sold > 0:
            cost_per_serving = total_cost / total_sold
            st.metric("Cost per Serving / 1皿原価", f"¥{cost_per_serving:,.0f}")
    
    # Visual breakdown chart
    st.subheader("📈 Yield Flow Visualization / 歩留まりフロー")
    
    # Waterfall-style data
    flow_data = pd.DataFrame({
        'Stage': ['1. Purchased\n(Raw)', '2. Butchery Loss', '3. Trimmed', '4. Cooking Loss', '5. Cooked Available', '6. Cooked Needed', '7. Variance'],
        'Amount (kg)': [
            purchased_raw_kg,
            -(purchased_raw_kg - trimmed_kg),
            trimmed_kg,
            -(trimmed_kg - cooked_available_kg),
            cooked_available_kg,
            cooked_needed_kg,
            cooked_variance_kg
        ]
    })
    
    # Simple bar chart showing the flow
    comparison_df = pd.DataFrame({
        'Category': ['Purchased\n(Raw)', 'Trimmed\n(After Butchery)', 'Cooked\n(Available)', 'Cooked\n(Needed)', 'Variance'],
        'Amount (kg)': [purchased_raw_kg, trimmed_kg, cooked_available_kg, cooked_needed_kg, abs(cooked_variance_kg)],
        'Type': ['Input', 'Process', 'Process', 'Requirement', 'Surplus' if cooked_variance_kg >= 0 else 'Shortage']
    })
    
    fig = px.bar(comparison_df, x='Category', y='Amount (kg)', 
                 color='Type',
                 color_discrete_map={
                     'Input': '#3366cc',
                     'Process': '#ff9900', 
                     'Requirement': '#109618',
                     'Surplus': '#dc3912',
                     'Shortage': '#990099'
                 })
    fig.update_layout(showlegend=True)
    st.plotly_chart(fig, use_container_width=True)
    
    # Summary explanation
    st.caption(f"""
    **Summary:** Purchased {purchased_raw_kg:.2f}kg raw → After {beef_butchery_pct*100:.0f}% butchery yield: {trimmed_kg:.2f}kg trimmed 
    → After {beef_cooking_pct*100:.0f}% cooking yield: {cooked_available_kg:.2f}kg cooked available.
    Sales required {cooked_needed_kg:.2f}kg cooked ({total_sold} servings × {beef_per_serving}g).
    {'Surplus' if cooked_variance_kg >= 0 else 'Shortage'}: {abs(cooked_variance_kg):.2f}kg
    """)
    
    # Detailed invoice breakdown
    if not beef_invoices.empty:
        st.subheader("📋 Purchase Details / 仕入明細")
        display_df = beef_invoices[['date', 'item_name', 'quantity', 'unit', 'amount']].copy()
        display_df.columns = ['Date/日付', 'Item/品目', 'Qty/数量', 'Unit/単位', 'Amount/金額']
        display_df['Amount/金額'] = display_df['Amount/金額'].apply(lambda x: f"¥{x:,.0f}")
        st.dataframe(display_df, use_container_width=True)
    
    # Detailed sales breakdown - RESTORED
    if not beef_sales.empty:
        st.subheader("🍽️ Sales Details / 売上明細")
        
        # Calculate revenue using helper function (adds estimated_price column)
        sales_display = calculate_revenue(beef_sales)
        # Use estimated_price (adjusted) instead of original price
        sales_display = sales_display[['code', 'name', 'category', 'qty', 'estimated_price', 'calculated_revenue']].copy()
        
        sales_display.columns = ['Code/コード', 'Item/品目', 'Category/カテゴリ', 'Qty/数量', 'Price/単価', 'Revenue/売上']
        sales_display['Price/単価'] = sales_display['Price/単価'].apply(lambda x: f"¥{x:,.0f}" if pd.notna(x) and x > 0 else "N/A")
        sales_display['Revenue/売上'] = sales_display['Revenue/売上'].apply(lambda x: f"¥{x:,.0f}")
        
        st.dataframe(sales_display, use_container_width=True)
        
        # Summary by category
        st.subheader("📊 Sales by Category / カテゴリ別売上")
        beef_sales_calc = calculate_revenue(beef_sales)
        category_summary = beef_sales_calc.groupby('category').agg({
            'qty': 'sum',
            'calculated_revenue': 'sum'
        }).reset_index()
        category_summary.columns = ['Category/カテゴリ', 'Qty/数量', 'Revenue/売上']
        category_summary['Revenue/売上'] = category_summary['Revenue/売上'].apply(lambda x: f"¥{x:,.0f}")
        st.dataframe(category_summary, use_container_width=True)


def display_caviar_analysis(sales_df, invoices_df, caviar_per_serving, caviar_yield_pct):
    """Detailed caviar analysis with yield-adjusted calculations"""
    st.header("🐟 Caviar Analysis / キャビア分析")
    
    # Show yield info
    st.info(f"📐 **Yield Rate / 歩留まり率:** {caviar_yield_pct*100:.0f}% | **Serving Size / 1人前:** {caviar_per_serving}g")
    
    # Filter caviar data - include both spellings
    caviar_sales = sales_df[sales_df['name'].str.contains('Egg Toast Caviar', case=False, na=False)] if not sales_df.empty else pd.DataFrame()
    caviar_invoices = invoices_df[invoices_df['item_name'].str.contains('キャビア|キャヴィア|KAVIARI|caviar', case=False, na=False)] if not invoices_df.empty else pd.DataFrame()
    
    if caviar_sales.empty and caviar_invoices.empty:
        st.warning("No caviar data available for analysis in selected period")
        return
    
    col1, col2, col3 = st.columns(3)
    
    # Calculate metrics
    total_sold = caviar_sales['qty'].sum() if not caviar_sales.empty else 0
    
    # Calculate revenue using helper function (no hardcoded prices)
    if not caviar_sales.empty:
        caviar_sales_calc = calculate_revenue(caviar_sales)
        total_revenue = caviar_sales_calc['calculated_revenue'].sum()
    else:
        total_revenue = 0
    
    # YIELD-ADJUSTED: Expected usage
    expected_usage_g = (total_sold * caviar_per_serving) / caviar_yield_pct
    
    # Caviar purchases - USE ACTUAL UNIT COLUMN, not magic number inference
    if not caviar_invoices.empty:
        # Convert using actual unit column (100g per can/pc for caviar)
        caviar_invoices_calc = convert_quantity_to_grams(caviar_invoices, default_unit_grams=100)
        total_purchased_g = caviar_invoices_calc['quantity_grams'].sum()
        total_purchased_units = total_purchased_g / 100  # Display as "cans" (100g each)
        total_cost = caviar_invoices['amount'].sum()
        
        # Show unit breakdown for transparency
        if 'unit' in caviar_invoices.columns:
            unit_breakdown = caviar_invoices.groupby('unit')['quantity'].sum().to_dict()
            st.caption(f"📦 Purchase units: {unit_breakdown}")
    else:
        total_purchased_g = 0
        total_purchased_units = 0
        total_cost = 0
    
    with col1:
        st.metric("Total Sold / 販売総数", f"{total_sold:.0f} servings")
        st.metric("Total Revenue / 売上合計", f"¥{total_revenue:,.0f}")
    
    with col2:
        st.metric("Total Purchased / 仕入総量", f"{total_purchased_g:.0f} g ({total_purchased_units:.0f} cans)")
        st.metric("Total Cost / 仕入原価", f"¥{total_cost:,.0f}")
    
    with col3:
        # Yield-adjusted waste ratio
        if total_purchased_g > 0:
            waste_ratio = max(0, (total_purchased_g - expected_usage_g) / total_purchased_g * 100)
            st.metric("Waste Ratio / ロス率", f"{waste_ratio:.1f}%",
                     delta=f"{waste_ratio - 10:.1f}%" if waste_ratio > 10 else None,
                     delta_color="inverse",
                     help="Yield-adjusted calculation")
        
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
    
    # Detailed sales breakdown
    if not caviar_sales.empty:
        st.subheader("🍽️ Sales Details / 売上明細")
        
        # Calculate revenue using helper function (adds estimated_price column)
        sales_display = calculate_revenue(caviar_sales)
        # Use estimated_price (adjusted) instead of original price
        sales_display = sales_display[['code', 'name', 'category', 'qty', 'estimated_price', 'calculated_revenue']].copy()
        
        sales_display.columns = ['Code/コード', 'Item/品目', 'Category/カテゴリ', 'Qty/数量', 'Price/単価', 'Revenue/売上']
        sales_display['Price/単価'] = sales_display['Price/単価'].apply(lambda x: f"¥{x:,.0f}" if pd.notna(x) and x > 0 else "N/A")
        sales_display['Revenue/売上'] = sales_display['Revenue/売上'].apply(lambda x: f"¥{x:,.0f}")
        
        st.dataframe(sales_display, use_container_width=True)
        
        # Summary by category
        st.subheader("📊 Sales by Category / カテゴリ別売上")
        caviar_sales_calc = calculate_revenue(caviar_sales)
        category_summary = caviar_sales_calc.groupby('category').agg({
            'qty': 'sum',
            'calculated_revenue': 'sum'
        }).reset_index()
        category_summary.columns = ['Category/カテゴリ', 'Qty/数量', 'Revenue/売上']
        category_summary['Revenue/売上'] = category_summary['Revenue/売上'].apply(lambda x: f"¥{x:,.0f}")
        st.dataframe(category_summary, use_container_width=True)


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
