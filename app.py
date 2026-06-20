import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import time
from datetime import datetime, timedelta

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Logical Option Buying Dashboard", layout="wide")
st.title("🚀 Logical Leading Indicator Dashboard (Nifty/BankNifty)")
st.markdown("Tracking **OI Shifts, IV Spread, Straddle & Proxy CVD** for Option Buying Entries")

# --- SIDEBAR & API CONFIGURATION ---
st.sidebar.header("API Configuration")

# Check if running on Streamlit Cloud (safely)
try:
    client_id = st.secrets["DHAN_CLIENT_ID"]
    access_token = st.secrets["DHAN_ACCESS_TOKEN"]
    st.sidebar.success("API Keys loaded from Cloud Secrets!")
except:
    # Fallback for local running
    client_id = st.sidebar.text_input("Dhan Client ID", "")
    access_token = st.sidebar.text_input("Dhan Access Token", "")

st.sidebar.header("Instrument Settings")
index_choice = st.sidebar.selectbox("Select Index", ["NIFTY", "BANKNIFTY"])
security_ids = {
    "NIFTY": {"id": "13", "step": 50},
    "BANKNIFTY": {"id": "25", "step": 100}
}

# --- MAIN AREA ---
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("📊 Spot & Expected Range")
    spot_price_placeholder = st.empty()
    atm_strike_placeholder = st.empty()
    straddle_placeholder = st.empty()

with col2:
    st.subheader("⚡ OI Shift (Today's Change)")
    call_oi_placeholder = st.empty()
    put_oi_placeholder = st.empty()
    oi_signal_placeholder = st.empty()

with col3:
    st.subheader("📉 IV Spread & Momentum")
    call_iv_placeholder = st.empty()
    put_iv_placeholder = st.empty()
    iv_signal_placeholder = st.empty()

st.divider()

# Signal Engine Row
st.subheader("🧠 Confluence Trade Signal")
signal_engine_placeholder = st.empty()

st.subheader("📈 Cumulative Volume Delta (Proxy)")
cvd_chart_placeholder = st.empty()
status_placeholder = st.empty()

# Initialize CVD history
if 'cvd_history' not in st.session_state:
    st.session_state.cvd_history = [0]

# --- LOGIC ---
if client_id and access_token:
    if st.button("Start Live Feed", type="primary"):
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "client-id": client_id,
            "access-token": access_token
        }
        
        underlying_id = security_ids[index_choice]["id"]
        progress_bar = st.progress(0)
        
        for i in range(100): # Run for 100 iterations
            try:
                spot_price = None
                source = ""
                
                # ==========================================
                # 1. FETCH SPOT PRICE (Live first, then Historical)
                # ==========================================
                quote_res = requests.post("https://api.dhan.co/v2/quote", json={"IDX_I": [underlying_id]}, headers=headers)
                quote_json = quote_res.json()
                
                if 'data' in quote_json and 'IDX_I' in quote_json['data'] and len(quote_json['data']['IDX_I']) > 0:
                    spot_price = quote_json['data']['IDX_I'][0].get('last_price', 0)
                    source = "Live Spot"
                else:
                    # Fallback to Historical Data if market is closed
                    today_str = datetime.now().strftime('%Y-%m-%d')
                    start_str = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
                    hist_payload = {
                        "securityId": underlying_id,
                        "exchangeSegment": "IDX_I",
                        "instrument": "INDEX",
                        "expiryCode": 0,
                        "fromDate": start_str,
                        "toDate": today_str
                    }
                    hist_res = requests.post("https://api.dhan.co/v2/charts/historical", json=hist_payload, headers=headers)
                    hist_json = hist_res.json()
                    
                    if 'close' in hist_json and len(hist_json['close']) > 0:
                        spot_price = hist_json['close'][-1]
                        source = "Last Close (Market Closed)"
                    else:
                        spot_price_placeholder.warning("Waiting for Dhan API data...")
                
                if spot_price:
                    step = security_ids[index_choice]["step"]
                    atm_strike = round(spot_price / step) * step
                    
                    spot_price_placeholder.metric(f"Spot Price ({source})", f"₹{spot_price:.2f}")
                    atm_strike_placeholder.metric("ATM Strike", atm_strike)
                    
                    # ==========================================
                    # 2. FETCH OPTION CHAIN
                    # ==========================================
                    oc_res = requests.post("https://api.dhan.co/v2/optionchain", json={"underlyingScrip": int(underlying_id), "underlyingSeg": "IDX_I"}, headers=headers)
                    oc_json = oc_res.json()
                    
                    if 'data' in oc_json and 'oc' in oc_json['data']:
                        oc = oc_json['data']['oc']
                        atm_str = str(atm_strike)
                        
                        if atm_str in oc:
                            ce_data = oc[atm_str].get('ce', {})
                            pe_data = oc[atm_str].get('pe', {})
                            
                            # Extract Data
                            c_oi = ce_data.get('oi', 0)
                            p_oi = pe_data.get('oi', 0)
                            c_oi_chg = ce_data.get('oi_change', 0) or 0
                            p_oi_chg = pe_data.get('oi_change', 0) or 0
                            
                            c_iv = ce_data.get('iv', 0) or 0
                            p_iv = pe_data.get('iv', 0) or 0
                            
                            c_ltp = ce_data.get('ltp', 0) or 0
                            p_ltp = pe_data.get('ltp', 0) or 0
                            
                            # Logical Calculations
                            straddle = c_ltp + p_ltp
                            upper_range = atm_strike + straddle
                            lower_range = atm_strike - straddle
                            iv_spread = p_iv - c_iv
                            
                            # Update UI - Col 1
                            straddle_placeholder.metric("ATM Straddle (Expected Move)", f"₹{straddle:.2f}", delta=f"Range: {lower_range:.0f} - {upper_range:.0f}")
                            
                            # Update UI - Col 2 (OI Change)
                            call_oi_placeholder.metric("Call OI (Today's Chg)", f"{c_oi:,}", delta=f"{c_oi_chg:,}")
                            put_oi_placeholder.metric("Put OI (Today's Chg)", f"{p_oi:,}", delta=f"{p_oi_chg:,}")
                            
                            # Update UI - Col 3 (IV)
                            call_iv_placeholder.metric("Call IV", f"{c_iv:.2f}%")
                            put_iv_placeholder.metric("Put IV", f"{p_iv:.2f}%")
                            
                            # --- LOGICAL CONFLUENCE ENGINE ---
                            bullish_score = 0
                            bearish_score = 0
                            
                            # Logic 1: OI Change
                            if p_oi_chg > c_oi_chg:
                                bullish_score += 1
                                oi_text = "Put writing exceeds Call writing (Bullish)"
                            elif c_oi_chg > p_oi_chg:
                                bearish_score += 1
                                oi_text = "Call writing exceeds Put writing (Bearish)"
                            else:
                                oi_text = "OI addition balanced"
                                
                            # Logic 2: IV Skew
                            if iv_spread > 0.5:
                                bearish_score += 1
                                iv_text = "Traders buying Puts (Bearish protection)"
                            elif iv_spread < -0.5:
                                bullish_score += 1
                                iv_text = "Traders buying Calls (Bullish breakout)"
                            else:
                                iv_text = "IV balanced"
                                
                            oi_signal_placeholder.info(oi_text)
                            iv_signal_placeholder.info(iv_text)
                            
                            # Final Signal Output
                            if bullish_score == 2:
                                signal_engine_placeholder.success(f"🟢 STRONG BUY CALL SIGNAL | Scores: Bull={bullish_score}, Bear={bearish_score}")
                                st.session_state.cvd_history.append(st.session_state.cvd_history[-1] + 15) # Mock CVD goes up
                            elif bearish_score == 2:
                                signal_engine_placeholder.error(f"🔴 STRONG BUY PUT SIGNAL | Scores: Bull={bullish_score}, Bear={bearish_score}")
                                st.session_state.cvd_history.append(st.session_state.cvd_history[-1] - 15) # Mock CVD goes down
                            else:
                                signal_engine_placeholder.warning(f"🟡 WAIT FOR CONFLUENCE | Mixed signals. Bull={bullish_score}, Bear={bearish_score}")
                                st.session_state.cvd_history.append(st.session_state.cvd_history[-1] + 2) # Mock CVD sideways
                                
                        else:
                            call_oi_placeholder.warning(f"ATM {atm_str} not in chain.")
                    else:
                        call_oi_placeholder.warning("Option Chain unavailable")
                        put_oi_placeholder.warning("Option Chain unavailable")
                        
                    # ==========================================
                    # 3. UPDATE CVD & TIMESTAMP
                    # ==========================================
                    current_time = datetime.now().strftime('%H:%M:%S')
                    status_placeholder.caption(f"Last Updated: {current_time}")
                    
                    df_cvd = pd.DataFrame(st.session_state.cvd_history, columns=['CVD'])
                    
                    fig = go.Figure(go.Scatter(
                        x=df_cvd.index, 
                        y=df_cvd['CVD'], 
                        mode='lines', 
                        name='CVD', 
                        line=dict(color='cyan', width=2)
                    ))
                    
                    fig.update_layout(
                        height=300, 
                        paper_bgcolor='rgba(0,0,0,0)', 
                        plot_bgcolor='rgba(15,17,21,1)',
                        font=dict(color='white'),
                        margin=dict(l=20, r=20, t=30, b=20),
                        title="Proxy CVD (Driven by Trade Signal Engine)",
                        xaxis_title="Time (Ticks)",
                        yaxis_title="Momentum",
                        xaxis=dict(showgrid=True, gridcolor='rgba(50,50,50,0.5)'),
                        yaxis=dict(showgrid=True, gridcolor='rgba(50,50,50,0.5)')
                    )
                    
                    # Fix for Streamlit duplicate ID error: pass a unique key using the loop index 'i'
                    cvd_chart_placeholder.plotly_chart(fig, use_container_width=True, key=f"cvd_chart_{i}")
                    
            except Exception as e:
                st.error(f"Loop Error: {e}")
                break
                
            time.sleep(2)
            progress_bar.progress((i + 1) / 100)

else:
    st.warning("Please enter your Dhan API credentials in the sidebar to start.")

# --- STRATEGY PLAYBOOK ---
st.divider()
with st.expander("📜 Logical Strategy Playbook", expanded=True):
    st.markdown("""
    **How the Confluence Engine Works:**
    The app scores the market on two logical parameters:
    1. **OI Change (Who is writing today?):** If Put OI is added more than Call OI, it is Bullish (Put writers support the market).
    2. **IV Skew (Who is buying aggressively?):** If Call IV > Put IV, it is Bullish (Call buyers expect breakout).
    
    **Reading the Expected Move (Straddle):**
    - ATM Straddle = Call LTP + Put LTP.
    - If Nifty is at 24,000 and Straddle is 120, the market expects Nifty to stay between 23,880 and 24,120.
    - **Option Buying Rule:** If the Confluence Engine gives a STRONG signal, buy the ATM option. Set your Stop Loss just outside the Expected Range (e.g., if Buy Call, SL at 23,880).
    """)
