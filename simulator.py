"""
Hybrid Solar-Wind Energy System - Data Simulator

This module simulates telemetry data for a hybrid solar-wind energy monitoring system.
Instead of reading from a real Arduino over serial, it generates synthetic sensor
data based on time-of-day patterns and simulated environmental conditions.

The simulator:
- Creates and initializes a SQLite database (hybrid_system.db)
- Generates realistic sensor readings every 2 seconds
- Simulates day/night cycles for solar panels
- Simulates wind patterns with smooth random variations
- Models battery charging/discharging based on net power
- Inserts all data into the telemetry table

Run this script to start generating simulated data:
    python simulator.py
"""

import sqlite3
import time
import math
import random
from typing import Tuple
from datetime import datetime


# Database configuration
DB_NAME = "hybrid_system.db"
SAMPLE_INTERVAL = 2  # seconds between samples


def init_database() -> sqlite3.Connection:
    """
    Initialize the SQLite database and create the telemetry table if it doesn't exist.
    
    Returns:
        sqlite3.Connection: Database connection object
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER NOT NULL,
            v_pv REAL NOT NULL,
            i_pv REAL NOT NULL,
            v_wind REAL NOT NULL,
            i_wind REAL NOT NULL,
            v_bat REAL NOT NULL,
            soc REAL NOT NULL,
            wind_speed REAL NOT NULL,
            lux REAL NOT NULL,
            fan_pwm REAL NOT NULL
        )
    """)
    
    conn.commit()
    print(f"Database initialized: {DB_NAME}")
    return conn


def simulate_solar(time_of_day: float) -> Tuple[float, float, float]:
    """
    Simulate solar panel voltage, current, and light level based on time of day.
    
    Args:
        time_of_day: Time in hours (0-24), where 6-18 represents daylight hours
        
    Returns:
        Tuple of (v_pv, i_pv, lux)
    """
    # Normalize time to 0-24 hour cycle
    hour = time_of_day % 24
    
    # Day/night cycle: peak at noon (12:00), zero at night
    if 6 <= hour <= 18:
        # Daytime: sine wave peaking at noon
        solar_factor = math.sin((hour - 6) * math.pi / 12)
    else:
        # Nighttime: minimal values
        solar_factor = 0.05 * random.random()  # Small random noise
    
    # PV voltage: 0-18V, higher during day
    v_pv = 3.0 + 15.0 * solar_factor + random.gauss(0, 0.5)
    v_pv = max(0, min(18, v_pv))
    
    # PV current: 0-1.5A, proportional to light
    i_pv = 1.5 * solar_factor * (0.8 + 0.4 * random.random())
    i_pv = max(0, min(1.5, i_pv))
    
    # Light level: 0-100000 lux
    lux = 100000 * solar_factor * (0.9 + 0.2 * random.random())
    lux = max(0, min(100000, lux))
    
    return v_pv, i_pv, lux


def simulate_wind(previous_wind_speed: float) -> Tuple[float, float, float]:
    """
    Simulate wind speed, wind generator voltage, and current.
    Uses a random walk with smoothing to create realistic wind patterns.
    
    Args:
        previous_wind_speed: Previous wind speed value for smoothing
        
    Returns:
        Tuple of (wind_speed, v_wind, i_wind)
    """
    # Random walk with smoothing (simulates wind gusts)
    target_speed = random.uniform(0, 10)
    wind_speed = 0.7 * previous_wind_speed + 0.3 * target_speed
    wind_speed = max(0, min(10, wind_speed))
    
    # Wind generator voltage: 0-20V, depends on wind speed
    # Add some noise to simulate generator behavior
    v_wind = 2.0 * wind_speed * (0.8 + 0.4 * random.random())
    v_wind = max(0, min(20, v_wind))
    
    # Wind current: only flows when wind speed > threshold (e.g., 2 m/s)
    if wind_speed > 2.0:
        i_wind = (wind_speed / 10.0) * 1.0 * (0.7 + 0.6 * random.random())
        i_wind = max(0, min(1.0, i_wind))
    else:
        i_wind = 0.0
    
    return wind_speed, v_wind, i_wind


def simulate_battery(
    v_bat_prev: float,
    soc_prev: float,
    p_pv: float,
    p_wind: float,
    dt_hours: float
) -> Tuple[float, float]:
    """
    Simulate battery voltage and state of charge based on net power.
    
    Args:
        v_bat_prev: Previous battery voltage
        soc_prev: Previous state of charge (0-100)
        p_pv: PV power (W)
        p_wind: Wind power (W)
        dt_hours: Time step in hours
        
    Returns:
        Tuple of (v_bat, soc)
    """
    # Assume a constant load of ~5W
    p_load = 5.0
    
    # Net power: generation minus load
    p_net = p_pv + p_wind - p_load
    
    # Battery capacity: assume 12V, 7Ah battery = 84Wh
    battery_capacity_wh = 84.0
    
    # Energy change in Wh
    delta_energy_wh = p_net * dt_hours
    
    # Update SOC (0-100%)
    soc = soc_prev + (delta_energy_wh / battery_capacity_wh) * 100
    soc = max(0, min(100, soc))
    
    # Battery voltage: roughly linear with SOC, 7.0V (empty) to 8.4V (full)
    # For a 12V battery system, this represents a 2S Li-ion pack
    v_bat = 7.0 + (soc / 100.0) * 1.4
    v_bat = max(7.0, min(8.4, v_bat))
    
    # Add small noise
    v_bat += random.gauss(0, 0.05)
    v_bat = max(7.0, min(8.4, v_bat))
    
    return v_bat, soc


def simulate_fan_pwm(v_bat: float, soc: float) -> float:
    """
    Simulate fan PWM control based on battery state.
    Fan turns on when battery is high (cooling/ventilation).
    
    Args:
        v_bat: Battery voltage
        soc: State of charge
        
    Returns:
        Fan PWM value (0-100)
    """
    # Turn on fan when SOC > 80% or v_bat > 8.0V
    if soc > 80 or v_bat > 8.0:
        fan_pwm = 50 + 50 * random.random()  # 50-100%
    else:
        fan_pwm = 0.0
    
    return max(0, min(100, fan_pwm))


def generate_telemetry_sample(
    start_time: float,
    previous_wind_speed: float,
    previous_v_bat: float,
    previous_soc: float
) -> Tuple[dict, float, float, float]:
    """
    Generate a single telemetry sample with all sensor values.
    
    Args:
        start_time: System start time (for day/night cycle)
        previous_wind_speed: Previous wind speed for smoothing
        previous_v_bat: Previous battery voltage
        previous_soc: Previous state of charge
        
    Returns:
        Tuple of (sample_dict, new_wind_speed, new_v_bat, new_soc)
    """
    current_time = time.time()
    elapsed_hours = (current_time - start_time) / 3600.0
    
    # Time of day in hours (simulate a 24-hour cycle)
    time_of_day = (elapsed_hours % 24)
    
    # Simulate solar
    v_pv, i_pv, lux = simulate_solar(time_of_day)
    
    # Simulate wind
    wind_speed, v_wind, i_wind = simulate_wind(previous_wind_speed)
    
    # Calculate powers
    p_pv = v_pv * i_pv
    p_wind = v_wind * i_wind
    
    # Time step in hours (2 seconds = 2/3600 hours)
    dt_hours = SAMPLE_INTERVAL / 3600.0
    
    # Simulate battery
    v_bat, soc = simulate_battery(previous_v_bat, previous_soc, p_pv, p_wind, dt_hours)
    
    # Simulate fan
    fan_pwm = simulate_fan_pwm(v_bat, soc)
    
    # Create sample dictionary
    sample = {
        "timestamp": int(current_time),
        "v_pv": round(v_pv, 2),
        "i_pv": round(i_pv, 3),
        "v_wind": round(v_wind, 2),
        "i_wind": round(i_wind, 3),
        "v_bat": round(v_bat, 2),
        "soc": round(soc, 1),
        "wind_speed": round(wind_speed, 2),
        "lux": round(lux, 0),
        "fan_pwm": round(fan_pwm, 1)
    }
    
    return sample, wind_speed, v_bat, soc


def insert_sample(conn: sqlite3.Connection, sample: dict) -> None:
    """
    Insert a telemetry sample into the database.
    
    Args:
        conn: Database connection
        sample: Dictionary containing telemetry data
    """
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO telemetry (
            timestamp, v_pv, i_pv, v_wind, i_wind, v_bat, soc,
            wind_speed, lux, fan_pwm
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        sample["timestamp"],
        sample["v_pv"],
        sample["i_pv"],
        sample["v_wind"],
        sample["i_wind"],
        sample["v_bat"],
        sample["soc"],
        sample["wind_speed"],
        sample["lux"],
        sample["fan_pwm"]
    ))
    conn.commit()


def run_simulator() -> None:
    """
    Main simulator loop. Generates and inserts telemetry data continuously.
    """
    print("Starting Hybrid Solar-Wind Energy System Simulator")
    print("=" * 60)
    
    # Initialize database
    conn = init_database()
    
    # Initialize state variables
    start_time = time.time()
    previous_wind_speed = 5.0  # Initial wind speed
    previous_v_bat = 7.5  # Initial battery voltage
    previous_soc = 50.0  # Initial SOC at 50%
    
    sample_count = 0
    
    try:
        while True:
            # Generate sample
            sample, previous_wind_speed, previous_v_bat, previous_soc = \
                generate_telemetry_sample(
                    start_time,
                    previous_wind_speed,
                    previous_v_bat,
                    previous_soc
                )
            
            # Insert into database
            insert_sample(conn, sample)
            sample_count += 1
            
            # Print status
            timestamp_str = datetime.fromtimestamp(sample["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp_str}] Sample #{sample_count}: "
                  f"PV={sample['v_pv']:.1f}V/{sample['i_pv']:.2f}A, "
                  f"Wind={sample['v_wind']:.1f}V/{sample['i_wind']:.2f}A, "
                  f"Battery={sample['v_bat']:.2f}V ({sample['soc']:.1f}%), "
                  f"WindSpeed={sample['wind_speed']:.1f}m/s, "
                  f"Lux={sample['lux']:.0f}")
            
            # Wait for next sample
            time.sleep(SAMPLE_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\nSimulator stopped by user")
    finally:
        conn.close()
        print("Database connection closed")


if __name__ == "__main__":
    run_simulator()





