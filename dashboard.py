"""
Hybrid Solar-Wind Energy System - Streamlit Dashboard

This module provides a Streamlit web dashboard for visualizing and evaluating
telemetry data from the hybrid solar-wind energy monitoring system. The dashboard
displays live metrics, historical charts, and energy evaluation calculations.

Features:
- Live KPI metrics (voltages, currents, SOC, wind speed, lux, fan PWM)
- Historical line charts for voltages and SOC
- Energy evaluation: calculates energy (Wh) and contribution shares
- Auto-refresh functionality with configurable intervals
- Configurable history window size

The dashboard fetches data from the FastAPI backend running on port 8000.

To run the dashboard:
    streamlit run dashboard.py
"""

import streamlit as st
import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# API configuration
API_BASE_URL = "http://localhost:8000"


def fetch_live_data() -> Optional[Dict[str, Any]]:
    """
    Fetch the latest telemetry data from the API.
    
    Returns:
        Dictionary containing live telemetry data, or None if error
    """
    try:
        response = requests.get(f"{API_BASE_URL}/live", timeout=2)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching live data: {e}")
        return None


def fetch_history(limit: int = 500) -> pd.DataFrame:
    """
    Fetch historical telemetry data from the API.
    
    Args:
        limit: Maximum number of records to fetch
        
    Returns:
        DataFrame with telemetry data, or empty DataFrame if error
    """
    try:
        response = requests.get(
            f"{API_BASE_URL}/history",
            params={"limit": limit},
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        
        # Convert timestamp to datetime
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
        
        # Set datetime as index
        df.set_index("datetime", inplace=True)
        
        return df
    except Exception as e:
        st.error(f"Error fetching history: {e}")
        return pd.DataFrame()


def calculate_energy_metrics(df: pd.DataFrame) -> Dict[str, float]:
    """
    Calculate energy metrics and contribution shares from historical data.
    
    Args:
        df: DataFrame with telemetry data (must have datetime index)
        
    Returns:
        Dictionary with energy metrics and shares
    """
    if df.empty or len(df) < 2:
        return {
            "E_pv": 0.0,
            "E_wind": 0.0,
            "E_total": 0.0,
            "pv_share": 0.0,
            "wind_share": 0.0
        }
    
    # Calculate instantaneous powers
    df["p_pv"] = df["v_pv"] * df["i_pv"]
    df["p_wind"] = df["v_wind"] * df["i_wind"]
    df["p_total"] = df["p_pv"] + df["p_wind"]
    
    # Calculate time differences in hours
    # Convert index to numeric (seconds since epoch) for calculation
    timestamps = df.index.astype(np.int64) / 1e9  # Convert nanoseconds to seconds
    dt_seconds = np.diff(timestamps)
    dt_hours = dt_seconds / 3600.0
    
    # Calculate energy for each interval (power * time)
    # Use average power between consecutive points
    p_pv_avg = (df["p_pv"].iloc[:-1].values + df["p_pv"].iloc[1:].values) / 2
    p_wind_avg = (df["p_wind"].iloc[:-1].values + df["p_wind"].iloc[1:].values) / 2
    
    e_pv_wh = p_pv_avg * dt_hours
    e_wind_wh = p_wind_avg * dt_hours
    
    # Sum total energy
    E_pv = float(np.sum(e_pv_wh))
    E_wind = float(np.sum(e_wind_wh))
    E_total = E_pv + E_wind
    
    # Calculate contribution shares
    if E_total > 0:
        pv_share = 100.0 * E_pv / E_total
        wind_share = 100.0 * E_wind / E_total
    else:
        pv_share = 0.0
        wind_share = 0.0
    
    return {
        "E_pv": E_pv,
        "E_wind": E_wind,
        "E_total": E_total,
        "pv_share": pv_share,
        "wind_share": wind_share
    }


def main():
    """Main dashboard application."""
    st.set_page_config(
        page_title="Hybrid Energy System Dashboard",
        page_icon="⚡",
        layout="wide"
    )
    
    st.title("⚡ Hybrid Solar–Wind Energy System Dashboard")
    
    # Sidebar configuration
    st.sidebar.header("Configuration")
    
    refresh_interval = st.sidebar.slider(
        "Refresh Interval (seconds)",
        min_value=1,
        max_value=10,
        value=2,
        step=1
    )
    
    history_window = st.sidebar.slider(
        "History Window (samples)",
        min_value=50,
        max_value=1000,
        value=500,
        step=50
    )
    
    auto_refresh = st.sidebar.checkbox("Auto Refresh", value=True)
    
    # Main content area
    # Create placeholder for live data
    live_placeholder = st.empty()
    
    # Fetch and display live data
    live_data = fetch_live_data()
    
    if live_data and "error" not in live_data:
        with live_placeholder.container():
            st.header("📊 Live Metrics")
            
            # Create columns for KPIs
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("PV Voltage", f"{live_data['v_pv']:.2f} V")
                st.metric("PV Current", f"{live_data['i_pv']:.3f} A")
            
            with col2:
                st.metric("Wind Voltage", f"{live_data['v_wind']:.2f} V")
                st.metric("Wind Current", f"{live_data['i_wind']:.3f} A")
            
            with col3:
                st.metric("Battery Voltage", f"{live_data['v_bat']:.2f} V")
                st.metric("Battery SOC", f"{live_data['soc']:.1f} %")
            
            with col4:
                st.metric("Wind Speed", f"{live_data['wind_speed']:.2f} m/s")
                st.metric("Light Level", f"{live_data['lux']:.0f} lux")
                st.metric("Fan PWM", f"{live_data['fan_pwm']:.1f} %")
            
            # Display timestamp
            timestamp = datetime.fromtimestamp(live_data["timestamp"])
            st.caption(f"Last update: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        st.warning("No live data available. Make sure the simulator and API server are running.")
    
    # Fetch and display history
    st.header("📈 Historical Data")
    
    history_df = fetch_history(limit=history_window)
    
    if not history_df.empty:
        # Calculate energy metrics
        energy_metrics = calculate_energy_metrics(history_df)
        
        # Display energy evaluation section
        st.subheader("🔋 Energy Evaluation")
        
        eval_col1, eval_col2, eval_col3, eval_col4, eval_col5 = st.columns(5)
        
        with eval_col1:
            st.metric("PV Energy", f"{energy_metrics['E_pv']:.3f} Wh")
        with eval_col2:
            st.metric("Wind Energy", f"{energy_metrics['E_wind']:.3f} Wh")
        with eval_col3:
            st.metric("Total Energy", f"{energy_metrics['E_total']:.3f} Wh")
        with eval_col4:
            st.metric("PV Share", f"{energy_metrics['pv_share']:.1f} %")
        with eval_col5:
            st.metric("Wind Share", f"{energy_metrics['wind_share']:.1f} %")
        
        # Contribution share visualization
        if energy_metrics['E_total'] > 0:
            share_col1, share_col2 = st.columns(2)
            
            with share_col1:
                st.bar_chart({
                    "PV": [energy_metrics['pv_share']],
                    "Wind": [energy_metrics['wind_share']]
                })
            
            with share_col2:
                # Pie chart data
                share_data = pd.DataFrame({
                    "Source": ["PV", "Wind"],
                    "Share": [energy_metrics['pv_share'], energy_metrics['wind_share']]
                })
                st.bar_chart(share_data.set_index("Source"))
        
        # Voltage charts
        st.subheader("⚡ Voltage Trends")
        
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            # PV, Wind, and Battery voltages
            voltage_df = pd.DataFrame({
                "PV Voltage": history_df["v_pv"],
                "Wind Voltage": history_df["v_wind"],
                "Battery Voltage": history_df["v_bat"]
            })
            st.line_chart(voltage_df)
        
        with chart_col2:
            # SOC trend
            soc_df = pd.DataFrame({
                "Battery SOC (%)": history_df["soc"]
            })
            st.line_chart(soc_df)
        
        # Power and current trends
        st.subheader("🔌 Power & Current Trends")
        
        # Calculate powers for display
        history_df["p_pv"] = history_df["v_pv"] * history_df["i_pv"]
        history_df["p_wind"] = history_df["v_wind"] * history_df["i_wind"]
        history_df["p_total"] = history_df["p_pv"] + history_df["p_wind"]
        
        power_col1, power_col2 = st.columns(2)
        
        with power_col1:
            power_df = pd.DataFrame({
                "PV Power": history_df["p_pv"],
                "Wind Power": history_df["p_wind"],
                "Total Power": history_df["p_total"]
            })
            st.line_chart(power_df)
        
        with power_col2:
            current_df = pd.DataFrame({
                "PV Current": history_df["i_pv"],
                "Wind Current": history_df["i_wind"]
            })
            st.line_chart(current_df)
        
        # Additional metrics
        st.subheader("🌬️ Environmental Data")
        
        env_col1, env_col2 = st.columns(2)
        
        with env_col1:
            wind_df = pd.DataFrame({
                "Wind Speed (m/s)": history_df["wind_speed"]
            })
            st.line_chart(wind_df)
        
        with env_col2:
            lux_df = pd.DataFrame({
                "Light Level (lux)": history_df["lux"]
            })
            st.line_chart(lux_df)
        
        # Data table (optional, can be collapsed)
        with st.expander("📋 View Raw Data"):
            st.dataframe(history_df[["v_pv", "i_pv", "v_wind", "i_wind", "v_bat", "soc", 
                                     "wind_speed", "lux", "fan_pwm"]])
    else:
        st.warning("No historical data available. Make sure the simulator is running and generating data.")
    
    # Auto-refresh logic
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()


if __name__ == "__main__":
    main()

