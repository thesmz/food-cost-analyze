"""
Database module for Supabase operations
Handles all data persistence for the Purchasing Evaluation System
"""

import streamlit as st
from supabase import create_client, Client
import pandas as pd
import re
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Union
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# CONNECTION
# =============================================================================

def init_supabase() -> Optional[Client]:
    """Initialize Supabase client from Streamlit secrets"""
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.warning(f"⚠️ Supabase not configured. Using file upload only. Error: {e}")
        return None


# =============================================================================
# HELPER FUNCTIONS (DRY - Don't Repeat Yourself)
# =============================================================================

def parse_date(date_value: Any, formats: List[str] = None) -> Optional[str]:
    """
    Parse various date formats into ISO format (YYYY-MM-DD).
    
    Args:
        date_value: Date string, datetime, or date object
        formats: List of strptime formats to try
    
    Returns:
        ISO formatted date string or None if parsing fails
    """
    if formats is None:
        formats = ['%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%Y-%m']
    
    if date_value is None or (isinstance(date_value, float) and pd.isna(date_value)):
        return None
    
    # Already a date object
    if isinstance(date_value, date):
        return date_value.isoformat()
    
    # Datetime object
    if isinstance(date_value, datetime):
        return date_value.date().isoformat()
    
    # String parsing
    date_str = str(date_value).strip()
    if not date_str:
        return None
    
    # Handle YYYY-MM format (add day)
    if re.match(r'^\d{4}-\d{2}$', date_str):
        date_str = f"{date_str}-01"
    
    # Try each format
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date().isoformat()
        except ValueError:
            continue
    
    return None


def batch_upsert(
    supabase: Client,
    table: str,
    records: List[Dict],
    conflict_columns: str = None,
    chunk_size: int = 50
) -> int:
    """
    Generic batch upsert/insert for any table.
    
    Args:
        supabase: Supabase client
        table: Table name
        records: List of record dicts
        conflict_columns: Comma-separated columns for upsert (or None for insert)
        chunk_size: Records per batch
    
    Returns:
        Number of records saved
    """
    if not records:
        return 0
    
    saved_count = 0
    
    try:
        for i in range(0, len(records), chunk_size):
            chunk = records[i:i + chunk_size]
            
            if conflict_columns:
                # Upsert (update on conflict)
                supabase.table(table).upsert(
                    chunk,
                    on_conflict=conflict_columns
                ).execute()
            else:
                # Simple insert
                supabase.table(table).insert(chunk).execute()
            
            saved_count += len(chunk)
            
    except Exception as e:
        logger.warning(f"Batch operation failed: {e}, trying individual inserts")
        
        # Fallback to individual inserts
        for record in records[saved_count:]:
            try:
                supabase.table(table).insert(record).execute()
                saved_count += 1
            except Exception as e2:
                logger.debug(f"Individual insert failed: {e2}")
                continue
    
    return saved_count


def to_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


# =============================================================================
# SAVE FUNCTIONS
# =============================================================================

def save_invoices(supabase: Client, records: Union[pd.DataFrame, List[Dict]]) -> int:
    """
    Save invoice records to Supabase.
    
    Args:
        supabase: Supabase client
        records: DataFrame or list of dicts with invoice data
    
    Returns:
        Number of records saved
    """
    if not supabase:
        return 0
    
    # Convert DataFrame to list of dicts
    if isinstance(records, pd.DataFrame):
        if records.empty:
            return 0
        records = records.to_dict('records')
    
    if not records:
        return 0
    
    # Transform to database schema
    batch_data = []
    for record in records:
        invoice_date = parse_date(record.get('date'))
        if not invoice_date:
            continue
        
        batch_data.append({
            'vendor': str(record.get('vendor', '')),
            'invoice_date': invoice_date,
            'item_name': str(record.get('item_name', '')),
            'quantity': to_float(record.get('quantity')),
            'unit': str(record.get('unit', '')),
            'unit_price': to_float(record.get('unit_price')),
            'amount': to_float(record.get('amount'))
        })
    
    logger.info(f"Saving {len(batch_data)} invoice records")
    
    return batch_upsert(
        supabase,
        table='invoices',
        records=batch_data,
        conflict_columns='vendor,invoice_date,item_name,amount'
    )


def save_sales(supabase: Client, df: pd.DataFrame) -> int:
    """
    Save sales records to Supabase.
    
    Args:
        supabase: Supabase client
        df: DataFrame with sales data
    
    Returns:
        Number of records saved
    """
    if not supabase or df.empty:
        return 0
    
    # Transform to database schema
    batch_data = []
    for _, row in df.iterrows():
        sale_date = parse_date(row.get('sale_date'))
        if not sale_date:
            continue
        
        batch_data.append({
            'sale_date': sale_date,
            'code': str(row.get('code', '')),
            'item_name': str(row.get('item_name', '')),
            'category': str(row.get('category', '')),
            'qty': to_float(row.get('qty')),
            'price': to_float(row.get('price')),
            'net_total': to_float(row.get('net_total'))
        })
    
    logger.info(f"Saving {len(batch_data)} sales records")
    
    return batch_upsert(
        supabase,
        table='sales',
        records=batch_data,
        conflict_columns=None  # No upsert for sales, just insert
    )


# =============================================================================
# LOAD FUNCTIONS
# =============================================================================

def load_invoices(
    supabase: Client,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    vendor_filter: Optional[str] = None
) -> pd.DataFrame:
    """Load invoices from Supabase with optional filters"""
    if not supabase:
        return pd.DataFrame()
    
    try:
        all_data = []
        page_size = 1000
        offset = 0
        
        while True:
            query = supabase.table('invoices').select('*')
            
            if start_date:
                query = query.gte('invoice_date', start_date.isoformat())
            if end_date:
                query = query.lte('invoice_date', end_date.isoformat())
            if vendor_filter:
                query = query.ilike('vendor', f'%{vendor_filter}%')
            
            result = query.order('id').range(offset, offset + page_size - 1).execute()
            
            if result.data:
                all_data.extend(result.data)
                if len(result.data) < page_size:
                    break
                offset += page_size
            else:
                break
        
        if all_data:
            df = pd.DataFrame(all_data)
            df = df.rename(columns={'invoice_date': 'date'})
            return df
        
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Error loading invoices: {e}")
        return pd.DataFrame()


def load_sales(
    supabase: Client,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    item_filter: Optional[str] = None
) -> pd.DataFrame:
    """Load sales from Supabase with optional filters"""
    if not supabase:
        return pd.DataFrame()
    
    try:
        all_data = []
        page_size = 1000
        offset = 0
        
        while True:
            query = supabase.table('sales').select('*')
            
            if start_date:
                query = query.gte('sale_date', start_date.isoformat())
            if end_date:
                query = query.lte('sale_date', end_date.isoformat())
            if item_filter:
                query = query.ilike('item_name', f'%{item_filter}%')
            
            result = query.order('id').range(offset, offset + page_size - 1).execute()
            
            if result.data:
                all_data.extend(result.data)
                if len(result.data) < page_size:
                    break
                offset += page_size
            else:
                break
        
        if all_data:
            df = pd.DataFrame(all_data)
            df = df.rename(columns={'sale_date': 'date', 'item_name': 'name'})
            return df
        
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Error loading sales: {e}")
        return pd.DataFrame()


# =============================================================================
# QUERY FUNCTIONS
# =============================================================================

def get_date_range(supabase: Client) -> tuple:
    """Get min and max dates from both invoices and sales"""
    if not supabase:
        return None, None
    
    try:
        dates = []
        
        # Invoice dates
        for order in [False, True]:  # min, max
            result = supabase.table('invoices').select('invoice_date').order(
                'invoice_date', desc=order
            ).limit(1).execute()
            if result.data:
                date_val = result.data[0].get('invoice_date')
                if date_val:
                    dates.append(datetime.fromisoformat(date_val).date())
        
        # Sales dates
        for order in [False, True]:
            result = supabase.table('sales').select('sale_date').order(
                'sale_date', desc=order
            ).limit(1).execute()
            if result.data:
                date_val = result.data[0].get('sale_date')
                if date_val:
                    dates.append(datetime.fromisoformat(date_val).date())
        
        if dates:
            return min(dates), max(dates)
        
        return None, None
        
    except Exception as e:
        st.error(f"Error getting date range: {e}")
        return None, None


def get_data_summary(supabase: Client) -> Dict:
    """Get summary statistics of stored data"""
    if not supabase:
        return {}
    
    summary = {}
    
    try:
        # Invoice count
        result = supabase.table('invoices').select('id', count='exact').execute()
        summary['invoice_count'] = result.count if result.count else 0
        
        # Sales count
        result = supabase.table('sales').select('id', count='exact').execute()
        summary['sales_count'] = result.count if result.count else 0
        
        # Date range
        min_date, max_date = get_date_range(supabase)
        summary['min_date'] = min_date.isoformat() if min_date else None
        summary['max_date'] = max_date.isoformat() if max_date else None
        
    except Exception as e:
        logger.error(f"Error getting summary: {e}")
    
    return summary


# =============================================================================
# DELETE FUNCTIONS
# =============================================================================

def delete_data_by_date_range(
    supabase: Client,
    start_date: date,
    end_date: date,
    tables: List[str] = None
) -> Dict[str, int]:
    """Delete data within date range from specified tables"""
    if not supabase:
        return {}
    
    if tables is None:
        tables = ['invoices', 'sales']
    
    deleted = {}
    date_columns = {'invoices': 'invoice_date', 'sales': 'sale_date'}
    
    try:
        for table in tables:
            date_col = date_columns.get(table)
            if not date_col:
                continue
            
            result = supabase.table(table).delete().gte(
                date_col, start_date.isoformat()
            ).lte(
                date_col, end_date.isoformat()
            ).execute()
            
            deleted[table] = len(result.data) if result.data else 0
            
    except Exception as e:
        st.error(f"Error deleting data: {e}")
    
    return deleted


def get_unique_vendors(supabase: Client) -> List[str]:
    """Get list of unique vendors from invoices table"""
    if not supabase:
        return []
    
    try:
        result = supabase.table('invoices').select('vendor').execute()
        if result.data:
            vendors = set(row['vendor'] for row in result.data if row.get('vendor'))
            return sorted(list(vendors))
    except Exception as e:
        logger.error(f"Error getting vendors: {e}")
    
    return []


def delete_invoices_by_vendor(supabase: Client, vendor: str) -> int:
    """Delete all invoices from a specific vendor"""
    if not supabase:
        return 0
    
    try:
        # Get count first
        count_result = supabase.table('invoices').select('id', count='exact').eq('vendor', vendor).execute()
        count = count_result.count if count_result.count else 0
        
        if count == 0:
            return 0
        
        # Delete
        supabase.table('invoices').delete().eq('vendor', vendor).execute()
        logger.info(f"Deleted {count} invoices from vendor: {vendor}")
        
        return count
        
    except Exception as e:
        logger.error(f"Error deleting invoices: {e}")
        st.error(f"Error deleting invoices: {e}")
        return 0
