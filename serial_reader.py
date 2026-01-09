"""
Hybrid Solar-Wind Energy System - Serial Data Reader

This module reads real telemetry data from an Arduino Uno over serial communication.
The Arduino sends sensor data in a specific format, which is parsed and stored in
a SQLite database for the API server and dashboard to access.

The Arduino sends data in this format:
    SOL V:18.50 I:1200
    WND V:12.30 I:0.500
    SP:22.20 WP:6.15
    LUX:45000 FAN:75%
    --------------------------

The reader:
- Connects to the Arduino via /dev/ttyACM0 (or specified port)
- Parses the serial data format
- Extracts sensor values (v_pv, i_pv, v_wind, i_wind, lux, fan_pwm)
- Calculates or estimates missing values (v_bat, soc, wind_speed)
- Inserts all data into the telemetry table

Run this script to start reading from Arduino:
    python serial_reader.py
"""

import sqlite3
import serial
import time
import re
from typing import Optional, Dict, Any, Tuple
from datetime import datetime


# Serial port configuration
SERIAL_PORT = "/dev/ttyACM0"  # Default Arduino port on Linux
BAUD_RATE = 115200
TIMEOUT = 1.0

# Database configuration
DB_NAME = "hybrid_system.db"


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


def parse_arduino_data(line: str, previous_values: Dict[str, float]) -> Optional[Dict[str, float]]:
    """
    Parse a line of Arduino serial data.
    
    The Arduino sends data in this format:
        SOL V:18.50 I:1200
        WND V:12.30 I:0.500
        SP:22.20 WP:6.15
        LUX:45000 FAN:75%
        --------------------------
    
    Args:
        line: A line of serial data from Arduino
        previous_values: Dictionary of previous sensor values for missing data
        
    Returns:
        Dictionary with parsed values, or None if line doesn't contain data
    """
    values = {}
    
    # Parse SOL V: and I: (solar voltage and current in mA)
    sol_match = re.search(r'SOL V:([\d.]+)\s+I:([\d.]+)', line)
    if sol_match:
        values['v_pv'] = float(sol_match.group(1))
        values['i_pv'] = float(sol_match.group(2)) / 1000.0  # Convert mA to A
    
    # Parse WND V: and I: (wind voltage and current)
    wnd_match = re.search(r'WND V:([\d.]+)\s+I:([\d.]+)', line)
    if wnd_match:
        values['v_wind'] = float(wnd_match.group(1))
        values['i_wind'] = float(wnd_match.group(2))
    
    # Parse LUX: and FAN: (light level and fan PWM percentage)
    lux_fan_match = re.search(r'LUX:([\d.]+)\s+FAN:([\d.]+)%', line)
    if lux_fan_match:
        values['lux'] = float(lux_fan_match.group(1))
        values['fan_pwm'] = float(lux_fan_match.group(2))
    
    # If we got any values, return them (we'll accumulate across multiple lines)
    if values:
        return values
    
    return None


def estimate_missing_values(
    v_pv: float,
    i_pv: float,
    v_wind: float,
    i_wind: float,
    previous_v_bat: float,
    previous_soc: float,
    previous_wind_speed: float
) -> Tuple[float, float, float]:
    """
    Estimate missing values (v_bat, soc, wind_speed) based on available data.
    
    Args:
        v_pv: PV voltage
        i_pv: PV current
        v_wind: Wind voltage
        i_wind: Wind current
        previous_v_bat: Previous battery voltage
        previous_soc: Previous state of charge
        previous_wind_speed: Previous wind speed
        
    Returns:
        Tuple of (v_bat, soc, wind_speed)
    """
    # Estimate wind speed from wind power (rough approximation)
    # Assume wind power correlates with wind speed: P ≈ 0.5 * ρ * A * v^3
    # Simplified: v ≈ (P * k)^(1/3), where k is a constant
    p_wind = v_wind * i_wind
    if p_wind > 0:
        # Rough estimate: wind_speed ≈ 2 * sqrt(p_wind) for small turbines
        wind_speed = 2.0 * (p_wind ** 0.5)
        wind_speed = max(0, min(10, wind_speed))  # Clamp to 0-10 m/s
    else:
        wind_speed = 0.0
    
    # Smooth wind speed with previous value
    wind_speed = 0.7 * previous_wind_speed + 0.3 * wind_speed
    
    # Estimate battery voltage and SOC from net power
    # Assume a simple model: battery charges/discharges based on net power
    p_pv = v_pv * i_pv
    p_net = p_pv + p_wind - 5.0  # Assume ~5W constant load
    
    # Battery capacity: 84Wh (12V, 7Ah)
    battery_capacity_wh = 84.0
    dt_hours = 1.0 / 3600.0  # ~1 second per sample
    
    # Update SOC
    delta_energy_wh = p_net * dt_hours
    soc = previous_soc + (delta_energy_wh / battery_capacity_wh) * 100
    soc = max(0, min(100, soc))
    
    # Battery voltage: linear with SOC, 7.0V (empty) to 8.4V (full)
    v_bat = 7.0 + (soc / 100.0) * 1.4
    v_bat = max(7.0, min(8.4, v_bat))
    
    return v_bat, soc, wind_speed


def read_arduino_data(ser: serial.Serial) -> Optional[Dict[str, float]]:
    """
    Read and parse a complete data block from Arduino.
    The Arduino sends multiple lines, we need to accumulate them.
    
    Args:
        ser: Serial port object
        
    Returns:
        Dictionary with all sensor values, or None if incomplete/error
    """
    accumulated = {}
    lines_read = 0
    max_lines = 10  # Safety limit
    
    # Read lines until we get the separator line
    while lines_read < max_lines:
        if ser.in_waiting == 0:
            time.sleep(0.1)
            continue
        
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        
        if not line:
            continue
        
        # Check for separator line
        if '---' in line:
            # We've got a complete block
            break
        
        # Parse the line
        parsed = parse_arduino_data(line, accumulated)
        if parsed:
            accumulated.update(parsed)
        
        lines_read += 1
    
    # Check if we have the minimum required data
    required_fields = ['v_pv', 'i_pv', 'v_wind', 'i_wind', 'lux', 'fan_pwm']
    if all(field in accumulated for field in required_fields):
        return accumulated
    
    return None


def insert_sample(conn: sqlite3.Connection, sample: Dict[str, float]) -> None:
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


def run_serial_reader(port: str = SERIAL_PORT) -> None:
    """
    Main serial reader loop. Reads data from Arduino and stores in database.
    
    Args:
        port: Serial port path (default: /dev/ttyACM0)
    """
    print("Starting Hybrid Solar-Wind Energy System Serial Reader")
    print("=" * 60)
    print(f"Connecting to Arduino on {port} at {BAUD_RATE} baud...")
    
    # Initialize database
    conn = init_database()
    
    # Initialize state variables for missing data estimation
    previous_v_bat = 7.5  # Initial battery voltage
    previous_soc = 50.0  # Initial SOC at 50%
    previous_wind_speed = 0.0  # Initial wind speed
    
    sample_count = 0
    
    try:
        # Open serial port
        ser = serial.Serial(port, BAUD_RATE, timeout=TIMEOUT)
        print(f"Connected to {port}")
        print("Waiting for Arduino data...")
        time.sleep(2)  # Give Arduino time to initialize
        
        # Clear any buffered data
        ser.reset_input_buffer()
        
        while True:
            # Read data from Arduino
            data = read_arduino_data(ser)
            
            if data is None:
                # No complete data block yet, continue
                time.sleep(0.1)
                continue
            
            # Estimate missing values
            v_bat, soc, wind_speed = estimate_missing_values(
                data['v_pv'],
                data['i_pv'],
                data['v_wind'],
                data['i_wind'],
                previous_v_bat,
                previous_soc,
                previous_wind_speed
            )
            
            # Update previous values
            previous_v_bat = v_bat
            previous_soc = soc
            previous_wind_speed = wind_speed
            
            # Create complete sample
            sample = {
                "timestamp": int(time.time()),
                "v_pv": round(data['v_pv'], 2),
                "i_pv": round(data['i_pv'], 3),
                "v_wind": round(data['v_wind'], 2),
                "i_wind": round(data['i_wind'], 3),
                "v_bat": round(v_bat, 2),
                "soc": round(soc, 1),
                "wind_speed": round(wind_speed, 2),
                "lux": round(data['lux'], 0),
                "fan_pwm": round(data['fan_pwm'], 1)
            }
            
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
            
    except serial.SerialException as e:
        print(f"\nError: Could not open serial port {port}")
        print(f"Details: {e}")
        print("\nMake sure:")
        print("  1. Arduino is connected via USB")
        print("  2. The correct port is specified (check with: ls /dev/ttyACM*)")
        print("  3. You have permission to access the serial port (may need to add user to dialout group)")
    except KeyboardInterrupt:
        print("\n\nSerial reader stopped by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'ser' in locals():
            ser.close()
            print("Serial port closed")
        conn.close()
        print("Database connection closed")


if __name__ == "__main__":
    import sys
    
    # Allow port to be specified as command line argument
    port = sys.argv[1] if len(sys.argv) > 1 else SERIAL_PORT
    run_serial_reader(port)

