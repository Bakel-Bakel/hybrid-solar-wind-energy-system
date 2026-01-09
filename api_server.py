"""
Hybrid Solar-Wind Energy System - API Server

This module provides a FastAPI REST API server for accessing telemetry data
from the hybrid solar-wind energy monitoring system. The server reads data
from a SQLite database and exposes endpoints for live data, historical data,
and summary statistics.

Endpoints:
- GET /live: Returns the most recent telemetry sample
- GET /history: Returns historical telemetry data with optional filtering
- GET /summary: Returns aggregated statistics over recent data

The server uses CORS middleware to allow cross-origin requests from the
Streamlit dashboard.

To run the server:
    uvicorn api_server:app --host 0.0.0.0 --port 8000

Or using Python:
    python -m uvicorn api_server:app --host 0.0.0.0 --port 8000
"""

import sqlite3
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta

# Database configuration
DB_NAME = "hybrid_system.db"

# Initialize FastAPI app
app = FastAPI(
    title="Hybrid Solar-Wind Energy System API",
    description="REST API for hybrid energy system telemetry data",
    version="1.0.0"
)

# Add CORS middleware (allow all origins for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db_connection() -> sqlite3.Connection:
    """
    Create and return a database connection.
    
    Returns:
        sqlite3.Connection: Database connection object
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """
    Convert a database row to a dictionary with proper field names.
    
    Args:
        row: SQLite row object
        
    Returns:
        Dictionary with telemetry fields
    """
    return {
        "id": row["id"],
        "timestamp": row["timestamp"],
        "v_pv": row["v_pv"],
        "i_pv": row["i_pv"],
        "v_wind": row["v_wind"],
        "i_wind": row["i_wind"],
        "v_bat": row["v_bat"],
        "soc": row["soc"],
        "wind_speed": row["wind_speed"],
        "lux": row["lux"],
        "fan_pwm": row["fan_pwm"]
    }


@app.get("/")
def root():
    """Root endpoint with API information."""
    return {
        "message": "Hybrid Solar-Wind Energy System API",
        "version": "1.0.0",
        "endpoints": {
            "/live": "Get latest telemetry sample",
            "/history": "Get historical telemetry data",
            "/summary": "Get aggregated statistics"
        }
    }


@app.get("/live")
def get_live() -> Dict[str, Any]:
    """
    Get the most recent telemetry sample.
    
    Returns:
        Dictionary containing the latest telemetry data, or error if no data exists
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM telemetry
            ORDER BY timestamp DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        
        if row is None:
            return {"error": "No telemetry data available"}
        
        return row_to_dict(row)
    finally:
        conn.close()


@app.get("/history")
def get_history(
    start_ts: Optional[int] = Query(None, description="Start timestamp (Unix seconds)"),
    end_ts: Optional[int] = Query(None, description="End timestamp (Unix seconds)"),
    limit: int = Query(500, description="Maximum number of records to return")
) -> List[Dict[str, Any]]:
    """
    Get historical telemetry data with optional filtering.
    
    Args:
        start_ts: Optional start timestamp filter
        end_ts: Optional end timestamp filter
        limit: Maximum number of records to return (default: 500)
        
    Returns:
        List of telemetry dictionaries, ordered by timestamp ascending
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Build query with optional filters
        query = "SELECT * FROM telemetry WHERE 1=1"
        params = []
        
        if start_ts is not None:
            query += " AND timestamp >= ?"
            params.append(start_ts)
        
        if end_ts is not None:
            query += " AND timestamp <= ?"
            params.append(end_ts)
        
        query += " ORDER BY timestamp ASC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [row_to_dict(row) for row in rows]
    finally:
        conn.close()


@app.get("/summary")
def get_summary() -> Dict[str, Any]:
    """
    Get aggregated statistics over recent telemetry data.
    Computes averages, minimums, and maximums over the last hour of data.
    
    Returns:
        Dictionary containing aggregated statistics
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Get data from the last hour
        one_hour_ago = int((datetime.now() - timedelta(hours=1)).timestamp())
        
        cursor.execute("""
            SELECT 
                COUNT(*) as count,
                AVG(v_pv) as avg_v_pv,
                MIN(v_pv) as min_v_pv,
                MAX(v_pv) as max_v_pv,
                AVG(i_pv) as avg_i_pv,
                MIN(i_pv) as min_i_pv,
                MAX(i_pv) as max_i_pv,
                AVG(v_wind) as avg_v_wind,
                MIN(v_wind) as min_v_wind,
                MAX(v_wind) as max_v_wind,
                AVG(i_wind) as avg_i_wind,
                MIN(i_wind) as min_i_wind,
                MAX(i_wind) as max_i_wind,
                AVG(v_bat) as avg_v_bat,
                MIN(v_bat) as min_v_bat,
                MAX(v_bat) as max_v_bat,
                AVG(soc) as avg_soc,
                MIN(soc) as min_soc,
                MAX(soc) as max_soc,
                AVG(wind_speed) as avg_wind_speed,
                MIN(wind_speed) as min_wind_speed,
                MAX(wind_speed) as max_wind_speed,
                AVG(lux) as avg_lux,
                MIN(lux) as min_lux,
                MAX(lux) as max_lux,
                AVG(fan_pwm) as avg_fan_pwm,
                MIN(fan_pwm) as min_fan_pwm,
                MAX(fan_pwm) as max_fan_pwm
            FROM telemetry
            WHERE timestamp >= ?
        """, (one_hour_ago,))
        
        row = cursor.fetchone()
        
        if row is None or row["count"] == 0:
            return {
                "error": "No data available in the last hour",
                "period": "last 1 hour"
            }
        
        # Calculate average powers
        avg_p_pv = row["avg_v_pv"] * row["avg_i_pv"] if row["avg_v_pv"] and row["avg_i_pv"] else 0
        avg_p_wind = row["avg_v_wind"] * row["avg_i_wind"] if row["avg_v_wind"] and row["avg_i_wind"] else 0
        avg_p_total = avg_p_pv + avg_p_wind
        
        return {
            "period": "last 1 hour",
            "sample_count": row["count"],
            "pv": {
                "voltage": {
                    "avg": round(row["avg_v_pv"], 2) if row["avg_v_pv"] else 0,
                    "min": round(row["min_v_pv"], 2) if row["min_v_pv"] else 0,
                    "max": round(row["max_v_pv"], 2) if row["max_v_pv"] else 0
                },
                "current": {
                    "avg": round(row["avg_i_pv"], 3) if row["avg_i_pv"] else 0,
                    "min": round(row["min_i_pv"], 3) if row["min_i_pv"] else 0,
                    "max": round(row["max_i_pv"], 3) if row["max_i_pv"] else 0
                },
                "power_avg": round(avg_p_pv, 2)
            },
            "wind": {
                "voltage": {
                    "avg": round(row["avg_v_wind"], 2) if row["avg_v_wind"] else 0,
                    "min": round(row["min_v_wind"], 2) if row["min_v_wind"] else 0,
                    "max": round(row["max_v_wind"], 2) if row["max_v_wind"] else 0
                },
                "current": {
                    "avg": round(row["avg_i_wind"], 3) if row["avg_i_wind"] else 0,
                    "min": round(row["min_i_wind"], 3) if row["min_i_wind"] else 0,
                    "max": round(row["max_i_wind"], 3) if row["max_i_wind"] else 0
                },
                "power_avg": round(avg_p_wind, 2)
            },
            "battery": {
                "voltage": {
                    "avg": round(row["avg_v_bat"], 2) if row["avg_v_bat"] else 0,
                    "min": round(row["min_v_bat"], 2) if row["min_v_bat"] else 0,
                    "max": round(row["max_v_bat"], 2) if row["max_v_bat"] else 0
                },
                "soc": {
                    "avg": round(row["avg_soc"], 1) if row["avg_soc"] else 0,
                    "min": round(row["min_soc"], 1) if row["min_soc"] else 0,
                    "max": round(row["max_soc"], 1) if row["max_soc"] else 0
                }
            },
            "wind_speed": {
                "avg": round(row["avg_wind_speed"], 2) if row["avg_wind_speed"] else 0,
                "min": round(row["min_wind_speed"], 2) if row["min_wind_speed"] else 0,
                "max": round(row["max_wind_speed"], 2) if row["max_wind_speed"] else 0
            },
            "lux": {
                "avg": round(row["avg_lux"], 0) if row["avg_lux"] else 0,
                "min": round(row["min_lux"], 0) if row["min_lux"] else 0,
                "max": round(row["max_lux"], 0) if row["max_lux"] else 0
            },
            "fan_pwm": {
                "avg": round(row["avg_fan_pwm"], 1) if row["avg_fan_pwm"] else 0,
                "min": round(row["min_fan_pwm"], 1) if row["min_fan_pwm"] else 0,
                "max": round(row["max_fan_pwm"], 1) if row["max_fan_pwm"] else 0
            },
            "total_power_avg": round(avg_p_total, 2)
        }
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)





