# The Shinmonzen - Purchasing Evaluation System

A comprehensive tool for analyzing ingredient purchases vs dish sales to evaluate waste and cost efficiency.

## Features

### Main App (app.py)
- **Overview Dashboard**: Summary of beef and caviar sales vs purchases
- **Beef Tenderloin Analysis**: Yield-adjusted waste and cost ratios
- **Caviar Analysis**: Yield-adjusted waste and cost ratios  
- **Vendor Items**: Invoice breakdown by vendor

### Additional Pages (pages/)
- **Menu Engineering**: BCG Matrix analysis for A la Carte items
- **YoY Forecasting**: Year-over-year forecasting from historical data
- **Recipe & Menu Costing**: Build menus from ingredient breakdowns with AI-translated names

## Setup

### Required Secrets (in Streamlit Cloud)

Go to App Settings > Secrets and add:

```toml
SUPABASE_URL = "your-supabase-url"
SUPABASE_KEY = "your-supabase-key"

# Optional: For AI translation of ingredient names in Recipe & Menu Costing
ANTHROPIC_API_KEY = "your-anthropic-api-key"
```

## Deployment

1. **Upload this folder to GitHub** (drag & drop at github.com/new)
2. **Go to [share.streamlit.io](https://share.streamlit.io)** and sign in with GitHub
3. **Click "New app"** → Select your repo → Main file: `app.py` → Deploy

Done! Share the URL with Chef.
