"""
Tasting Menu Analyzer
Analyze and adjust course menu costs to see margin impact
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import TASTING_MENU_RECIPES, FOOD_COST_WARNING_THRESHOLD

st.set_page_config(page_title="Tasting Menu Analyzer | The Shinmonzen", page_icon="🍽️", layout="wide")

st.title("🍽️ Tasting Menu Analyzer / コースメニュー分析")
st.markdown("Analyze and adjust course menu costs to see margin impact")

# Custom CSS
st.markdown("""
<style>
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
</style>
""", unsafe_allow_html=True)

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

# Session state for costs
if f'costs_{selected_menu}' not in st.session_state:
    st.session_state[f'costs_{selected_menu}'] = {
        c['name']: c['estimated_food_cost'] for c in menu['courses']
    }

edited_costs = st.session_state[f'costs_{selected_menu}']

# Editable costs table
st.subheader("📝 Course Components (Editable)")
st.caption("Adjust costs to see impact on margin")

cols = st.columns([1, 3, 2, 3])
cols[0].markdown("**#**")
cols[1].markdown("**Course**")
cols[2].markdown("**Cost (¥)**")
cols[3].markdown("**Key Ingredients**")

new_costs = {}
for course in menu['courses']:
    cols = st.columns([1, 3, 2, 3])
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

# Warning/Success boxes
if food_cost_pct > FOOD_COST_WARNING_THRESHOLD:
    st.markdown(f"""
    <div class="warning-box">
        ⚠️ <strong>Warning:</strong> Food cost ({food_cost_pct:.1f}%) exceeds {FOOD_COST_WARNING_THRESHOLD}% threshold!
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
]).sort_values('Cost', ascending=True)

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

# Course details expander
with st.expander("📋 Full Course Details"):
    for course in menu['courses']:
        st.markdown(f"**{course['course_number']}. {course['name']}** ({course['name_jp']})")
        st.caption(f"{course['description']}")
        st.caption(f"Ingredients: {', '.join(course['key_ingredients'])}")
        st.divider()
