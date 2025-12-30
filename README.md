# The Shinmonzen - Purchasing Evaluation System

A comprehensive tool for analyzing ingredient purchases vs dish sales to evaluate waste and cost efficiency.

## Features

### Main App (app.py)
- **Overview Dashboard**: Summary of beef and caviar sales vs purchases
- **Beef Tenderloin Analysis**: Yield-adjusted waste and cost ratios
- **Caviar Analysis**: Yield-adjusted waste and cost ratios  
- **Vendor Items**: Invoice breakdown by vendor
- **Configuration Settings**: Yield % and serving size in main page expander

### Additional Pages (pages/)
- **Menu Engineering**: BCG Matrix analysis for A la Carte items
- **YoY Forecasting**: Year-over-year forecasting from historical data
- **Recipe & Menu Costing**: Build menus from ingredient breakdowns
  - Pantry auto-populated from invoice data
  - Quick-fill syncs input fields
  - Translation feature for dish names

## Bug Fixes Applied
1. ✅ Yield settings moved from sidebar to main page expander
2. ✅ Upload UI now shows persistent success/error messages
3. ✅ Error handling added for file uploads
4. ✅ Caviar items split into separate entries (Fresh vs Selection)
5. ✅ Pantry quick-fill now properly syncs input fields
6. ✅ Translation feature moved to Recipe & Menu Costing page

## Setup

### Required Secrets (in Streamlit Cloud)

Go to App Settings > Secrets and add:

```toml
SUPABASE_URL = "your-supabase-url"
SUPABASE_KEY = "your-supabase-key"
```

## Deployment

1. **Upload this folder to GitHub**
2. **Go to [share.streamlit.io](https://share.streamlit.io)** and sign in with GitHub
3. **Click "New app"** → Select your repo → Main file: `app.py` → Deploy

Done!
