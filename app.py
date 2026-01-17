import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import urllib.parse
import re
from datetime import date
from PIL import Image
import folium
from streamlit_folium import st_folium

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="Travel Planner", page_icon="✈️", layout="wide")

# --- 2. STYLE ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"], font, span, div, p, h1, h2, h3, h4, h5, h6 {
        font-family: 'Outfit', sans-serif !important;
    }
    .main-title { font-size: 3.5rem; color: #1a73e8; font-weight: 700; text-align: center; margin-top: -20px; }
    .currency-badge { background-color: #e8f0fe; color: #1a73e8; padding: 5px 15px; border-radius: 20px; font-weight: 600; font-size: 1rem; display: inline-block; margin-top: 10px; border: 1px solid #d2e3fc; }
    .stButton>button { background-color: #1a73e8; color: white; border: none; border-radius: 24px; height: 55px; font-size: 18px; font-weight: 600; width: 100%; transition: all 0.3s; }
    .stButton>button:hover { background-color: #1557b0; transform: translateY(-2px); }
    .status-success { padding: 20px; border-radius: 12px; background-color: #e6f4ea; color: #137333; font-weight: 600; text-align: center; border: 1px solid #ceead6; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# --- 3. SESSION STATE ---
if 'generated_trip' not in st.session_state: st.session_state.generated_trip = None
if 'map_data' not in st.session_state: st.session_state.map_data = None

# --- 4. AUTHENTICATION ---
try:
    if "GOOGLE_API_KEY" in st.secrets: api_key = st.secrets["GOOGLE_API_KEY"]
    else: api_key = st.text_input("API Key", type="password")
except: api_key = st.text_input("API Key", type="password")

# --- 5. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Settings")
    st.header("✈️ Trip Parameters")
    origin = st.text_input("🛫 Origin City", "London")
    destination = st.text_input("🛬 Destination", "Tokyo")
    col1, col2 = st.columns(2)
    with col1: start_date = st.date_input("📅 Start Date", date.today())
    with col2: duration = st.slider("⏳ Days", 3, 21, 7)
    is_flexible = st.checkbox("✅ Flexible Dates (+/- 3 days)")
    currency = st.selectbox("💱 Preferred Currency", ["USD ($)", "GBP (£)", "EUR (€)", "JPY (¥)", "AUD ($)", "CAD ($)"])
    budget = st.select_slider("💰 Budget Level", options=["Backpacker", "Standard", "Luxury", "VIP"])
    st.divider()
    interests = st.text_area("❤️ Interests", "Food, History, Hidden Gems, Photography")
    uploaded_file = st.file_uploader("📸 Upload Inspiration Image", type=["jpg", "png"])
    st.divider()
    st.info("**Travel Planner Pro v1.0**\nPrices are estimates.")
    st.caption("© 2025 Travel Planner Inc.")

# --- 6. FLIGHT LINKS ENGINE (MONETIZED) ---
def get_flight_links(org, dst, date_obj, flexible):
    # --- AFFILIATE SETTINGS (REPLACE THESE LATER) ---
    # Sign up at TravelPayouts or Skyscanner to get real IDs
    affiliate_tag = "YOUR_AFFILIATE_ID" 
    
    safe_org = urllib.parse.quote(org)
    safe_dst = urllib.parse.quote(dst)
    date_str = date_obj.strftime('%Y-%m-%d')
    
    # Google Flights (Hard to monetize, but good for user exp)
    gf_link = f"https://www.google.com/travel/flights?q=Flights%20to%20{safe_dst}%20from%20{safe_org}%20on%20{date_str}"
    
    # Skyscanner (Monetizable)
    if flexible:
        month_str = date_obj.strftime('%y%m')
        sky_link = f"https://www.skyscanner.com/transport/flights/{safe_org[:3]}/{safe_dst[:3]}/{month_str}?associateid={affiliate_tag}"
    else:
        day_str = date_obj.strftime('%y%m%d')
        sky_link = f"https://www.skyscanner.com/transport/flights/{safe_org[:3]}/{safe_dst[:3]}/{day_str}?associateid={affiliate_tag}"
        
    return gf_link, sky_link

# --- 7. MAIN APP ---
st.markdown('<div class="main-title">✈️ Travel Planner</div>', unsafe_allow_html=True)
st.markdown(f'<div align="center"><div class="currency-badge">Active Currency: {currency}</div></div>', unsafe_allow_html=True)

if not api_key: st.stop()

try:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
except Exception as e:
    st.error(f"❌ Connection Error: {e}")
    st.stop()

if st.button("🚀 Plan My Trip"):
    status = st.empty()
    status.info("⏳ Connecting to Global Satellites... Analyzing Routes...")
    try:
        date_desc = f"starting around {start_date} (Flexible)" if is_flexible else f"starting exactly on {start_date}"
        prompt = f"""
        Act as a world-class {budget} Travel Concierge. 
        Create a vibrant, emoji-filled 7-day itinerary for a trip to {destination} from {origin}.
        Dates: {date_desc}. Interests: {interests}.
        IMPORTANT: Provide ALL prices, flight estimates, and budget totals in {currency}.
        CRITICAL FORMATTING RULES:
        1. **MATHS LOGIC:** If using the Dollar sign ($), YOU MUST escape it with a backslash (write it as $) to prevent it from triggering LaTeX math formatting.
        2. Use lots of emojis (✈️, 🏨, 🍜, 📸).
        
        REQUIRED SECTIONS:
        ## 1. ✈️ Flight Strategy
        - Best airlines and price estimates in {currency}.
        ## 2. 🗺️ The Itinerary
        - Morning / Afternoon / Evening breakdown.
        - Specific restaurant names and activity costs.
        ## 3. 💰 Financial Breakdown
        - Total estimated cost in {currency}.
        ## 4. MAP_DATA_JSON
        - Strictly output a JSON list of top 5 locations.
        - Do not use markdown blocks. Just the raw JSON array.
        - Format: [{{"name": "Eiffel Tower", "lat": 48.8584, "lon": 2.2945}}, ...]
        """
        inputs = [prompt]
        if uploaded_file:
            inputs.append(Image.open(uploaded_file))
            inputs[0] += " NOTE: Include the uploaded image location in the plan."
        
        response = model.generate_content(inputs)
        text = response.text
        text = text.replace("$", "$") 
        st.session_state.generated_trip = text
        
        df = pd.DataFrame()
        try:
            match = re.search(r'\[\s*\{.*\}\s*\]', text, re.DOTALL)
            if match:
                json_str = match.group(0)
                data = json.loads(json_str)
                df = pd.DataFrame(data)
                st.session_state.map_data = df
        except: st.session_state.map_data = None
        status.empty()
    except Exception as e: st.error(f"❌ Error: {e}")

if st.session_state.generated_trip:
    st.markdown('<div class="status-success">✅ Trip Generated Successfully!</div>', unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["📅 Daily Plan", "✈️ Flight Booking", "📍 Live Map"])
    with tab1:
        clean_text = st.session_state.generated_trip.split("## 4. MAP_DATA_JSON")[0]
        st.markdown(clean_text, unsafe_allow_html=True)
        st.download_button("💾 Download Itinerary", clean_text, "my_trip.md")
    with tab2:
        st.success(f"Best flight options for {origin} ➡️ {destination}")
        gf, sky = get_flight_links(origin, destination, start_date, is_flexible)
        c1, c2 = st.columns(2)
        c1.link_button("🔎 Google Flights", gf)
        c2.link_button("🔎 Skyscanner Deals", sky)
    with tab3:
        if st.session_state.map_data is not None and not st.session_state.map_data.empty:
            df = st.session_state.map_data
            m = folium.Map(location=[df['lat'].mean(), df['lon'].mean()], zoom_start=12)
            for i, row in df.iterrows():
                folium.Marker([row['lat'], row['lon']], popup=row['name'], tooltip=row['name'], icon=folium.Icon(color="red", icon="info-sign")).add_to(m)
            st_folium(m, width=1000, height=500)
            st.caption("🔴 Click pins for details.")
        else: st.warning("⚠️ Could not pinpoint locations.")
