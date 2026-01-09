# Hybrid Solar-Wind Energy Monitoring System

A comprehensive real-time monitoring and evaluation system for hybrid renewable energy generation, combining solar photovoltaic (PV) and wind turbine sources. This project provides end-to-end data collection, storage, API access, and web-based visualization with energy analysis capabilities.

## 📋 Project Overview

This system monitors a hybrid renewable energy setup that combines:
- **Solar PV panels** for photovoltaic energy generation
- **Wind turbine** for wind-based energy generation
- **Battery storage** for energy management
- **Load management** with fan control based on system state

The monitoring system collects real-time sensor data, stores it in a database, provides REST API access, and displays comprehensive dashboards with energy evaluation metrics including power generation, energy contribution shares, and system performance analysis.

### Key Features

- **Real-time Data Collection**: Continuous monitoring of voltage, current, power, and environmental conditions
- **Data Persistence**: SQLite database for historical data storage and analysis
- **RESTful API**: FastAPI-based backend for programmatic data access
- **Interactive Dashboard**: Streamlit web interface with live metrics, historical charts, and energy evaluation
- **Energy Analysis**: Automatic calculation of energy generation (Wh), contribution shares, and performance metrics
- **Remote Access**: Web-based dashboard accessible from any device on the network
- **Automated Operation**: Systemd service support for automatic startup on boot

## 🔧 Technologies Used

### Hardware Components

- **Arduino Uno**: Microcontroller for sensor data acquisition
- **Raspberry Pi**: Single-board computer running the monitoring software stack
- **INA226**: I2C current/power monitor for wind generator measurements
- **ACS712**: Hall-effect current sensor for solar panel current measurement
- **BH1750**: Digital light sensor (lux meter) for ambient light monitoring
- **Voltage Dividers**: Analog voltage measurement circuits for PV and battery monitoring
- **LCD Display (20x4 I2C)**: Local display for system status
- **PWM Fan**: Controlled cooling/ventilation fan

### Software Stack

#### Backend & Data Processing
- **Python 3.10+**: Primary programming language
- **PySerial**: Serial communication with Arduino
- **SQLite3**: Lightweight relational database for time-series data storage
- **FastAPI**: Modern, high-performance web framework for building REST APIs
- **Uvicorn**: ASGI server for FastAPI applications

#### Frontend & Visualization
- **Streamlit**: Rapid web application framework for data visualization
- **Pandas**: Data manipulation and analysis library
- **NumPy**: Numerical computing for energy calculations

#### System & Deployment
- **Bash Scripting**: Automated service management and startup
- **Systemd**: Linux service management for auto-start on boot
- **Virtual Environment**: Python dependency isolation

### Communication Protocols

- **Serial/UART**: 115200 baud communication between Arduino and Raspberry Pi
- **I2C**: Communication with INA226, BH1750, and LCD display
- **HTTP/REST**: API communication between dashboard and backend
- **WebSocket**: Real-time updates in Streamlit dashboard

## 🏗️ System Architecture

### Data Flow

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐      ┌──────────────┐
│   Arduino   │─────▶│ Serial       │─────▶│  SQLite     │─────▶│  FastAPI     │
│   Sensors   │Serial│ Reader       │      │  Database   │      │  REST API    │
└─────────────┘      └──────────────┘      └─────────────┘      └──────────────┘
                                                                        │
                                                                        ▼
                                                               ┌──────────────┐
                                                               │  Streamlit   │
                                                               │  Dashboard   │
                                                               └──────────────┘
```

### Component Responsibilities

1. **Arduino (`hybrid_low_level.ino`)**
   - Reads analog and digital sensors
   - Performs sensor calibration and filtering
   - Formats and transmits data over serial at 1-second intervals
   - Controls fan PWM based on system state

2. **Serial Reader (`serial_reader.py`)**
   - Receives serial data from Arduino
   - Parses formatted sensor readings
   - Estimates missing parameters (battery voltage, SOC, wind speed)
   - Inserts timestamped data into SQLite database

3. **API Server (`api_server.py`)**
   - Provides REST endpoints for data access
   - Handles query parameters for time-range filtering
   - Computes aggregated statistics
   - Enables CORS for cross-origin requests

4. **Dashboard (`dashboard.py`)**
   - Fetches live and historical data via API
   - Displays real-time KPIs and metrics
   - Renders time-series charts
   - Calculates and visualizes energy generation and contribution shares

## 📊 Data Model

### Telemetry Schema

The system stores the following sensor readings in the `telemetry` table:

| Field | Type | Description | Unit |
|-------|------|-------------|------|
| `id` | INTEGER | Primary key, auto-increment | - |
| `timestamp` | INTEGER | Unix timestamp (seconds) | s |
| `v_pv` | REAL | Solar panel voltage | V |
| `i_pv` | REAL | Solar panel current | A |
| `v_wind` | REAL | Wind generator voltage | V |
| `i_wind` | REAL | Wind generator current | A |
| `v_bat` | REAL | Battery voltage | V |
| `soc` | REAL | Battery state of charge | % |
| `wind_speed` | REAL | Estimated wind speed | m/s |
| `lux` | REAL | Ambient light level | lux |
| `fan_pwm` | REAL | Fan PWM duty cycle | % |

### Derived Metrics

The dashboard calculates additional metrics:

- **Instantaneous Power**: `P = V × I` for each source
- **Total Power**: `P_total = P_pv + P_wind`
- **Energy (Wh)**: Numerical integration of power over time
- **Contribution Shares**: Percentage of total energy from each source

## 🔬 Methodologies

### Sensor Data Acquisition

1. **Solar Panel Monitoring**
   - Voltage: Analog voltage divider (5:1 ratio) on pin A0
   - Current: ACS712 Hall-effect sensor on pin A1
   - Calibration: Zero-point calibration for current sensor at startup
   - Sampling: 200-sample averaging for noise reduction

2. **Wind Generator Monitoring**
   - Voltage & Current: INA226 power monitor via I2C
   - Configuration: 1.0A max current, 2mΩ shunt resistor
   - Averaging: 1024-sample hardware averaging

3. **Environmental Sensing**
   - Light Level: BH1750 digital lux sensor (continuous high-res mode)
   - Wind Speed: Estimated from wind power using simplified turbine model

4. **Battery Management**
   - Voltage & SOC: Estimated from net power flow
   - Model: 84Wh capacity (12V, 7Ah), linear SOC-voltage relationship
   - Charging/Discharging: Based on net power (generation - load)

### Data Processing Pipeline

1. **Serial Parsing**: Regex-based extraction of sensor values from formatted strings
2. **Data Validation**: Range checking and error handling for sensor readings
3. **Missing Data Estimation**: Physics-based models for unavailable sensors
4. **Time-Series Storage**: Timestamped insertion into SQLite with indexing
5. **API Querying**: Efficient database queries with time-range filtering
6. **Energy Calculation**: Numerical integration using trapezoidal rule

### Energy Evaluation Methodology

The dashboard implements energy analysis using:

1. **Power Calculation**: `P(t) = V(t) × I(t)` for each time point
2. **Time Integration**: `E = Σ P_avg × Δt` where:
   - `P_avg = (P(t_i) + P(t_{i+1})) / 2`
   - `Δt = (t_{i+1} - t_i) / 3600` (convert seconds to hours)
3. **Contribution Analysis**: `Share = (E_source / E_total) × 100%`

## 🚀 Installation & Setup

### Prerequisites

- Raspberry Pi (any model with Python 3.10+)
- Arduino Uno with required sensors and libraries
- USB cable for Arduino-Pi connection
- Internet connection (for initial package installation)

### Step 1: Hardware Setup

1. **Assemble Arduino Circuit**
   - Connect solar panel voltage divider to pin A0
   - Connect ACS712 current sensor to pin A1
   - Connect INA226 to I2C bus (SDA/SCL)
   - Connect BH1750 to I2C bus
   - Connect LCD display to I2C bus
   - Connect fan to pin 5 (PWM)

2. **Upload Arduino Code**
   ```bash
   # Install required Arduino libraries:
   # - INA226 by wollewald
   # - LiquidCrystal_I2C by Frank de Brabander
   # - BH1750 by Christopher Laws
   
   # Upload hybrid_low_level.ino to Arduino Uno
   ```

3. **Connect Arduino to Raspberry Pi**
   - Connect via USB cable
   - Verify connection: `ls /dev/ttyACM*`

### Step 2: Software Installation

1. **Clone or Download Project**
   ```bash
   cd ~/hybrid/demo
   ```

2. **Install System Dependencies**
   ```bash
   # Update package list
   sudo apt update
   
   # Install Python and pip (if not already installed)
   sudo apt install python3 python3-pip python3-venv
   
   # Add user to dialout group for serial access
   sudo usermod -a -G dialout $USER
   # Log out and back in for changes to take effect
   ```

3. **Set Up Python Environment**
   ```bash
   # Create virtual environment
   python3 -m venv venv
   
   # Activate virtual environment
   source venv/bin/activate
   
   # Install Python dependencies
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Make Startup Script Executable**
   ```bash
   chmod +x start.sh
   ```

### Step 3: Configuration

1. **Verify Serial Port**
   ```bash
   # Check available serial ports
   ls -l /dev/ttyACM*
   
   # If Arduino is on a different port, update start.sh or use:
   export SERIAL_PORT=/dev/ttyACM1
   ```

2. **Test Arduino Communication**
   ```bash
   # Monitor serial output
   screen /dev/ttyACM0 115200
   # Press Ctrl+A then K to exit
   ```

### Step 4: Run the System

**Option A: Using Startup Script (Recommended)**
```bash
# Start all services in background
./start.sh

# Or start in foreground for debugging
./start.sh --foreground
```

**Option B: Manual Start**
```bash
# Terminal 1: Serial Reader
source venv/bin/activate
python serial_reader.py

# Terminal 2: API Server
source venv/bin/activate
uvicorn api_server:app --host 0.0.0.0 --port 8000

# Terminal 3: Dashboard
source venv/bin/activate
streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0
```

### Step 5: Access the Dashboard

Open a web browser and navigate to:
- **Local**: `http://localhost:8501`
- **Network**: `http://<raspberry-pi-ip>:8501`

## 🔄 Running on Boot (Optional)

To automatically start the system on Raspberry Pi boot:

1. **Edit Service File**
   ```bash
   nano hybrid-energy-monitor.service
   ```
   Update the `WorkingDirectory` and paths to match your installation.

2. **Install Service**
   ```bash
   sudo cp hybrid-energy-monitor.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable hybrid-energy-monitor.service
   sudo systemctl start hybrid-energy-monitor.service
   ```

3. **Check Status**
   ```bash
   sudo systemctl status hybrid-energy-monitor.service
   ```

4. **View Logs**
   ```bash
   sudo journalctl -u hybrid-energy-monitor.service -f
   ```

## 📖 Usage Guide

### Startup Script Commands

```bash
# Start all services (background)
./start.sh

# Start in foreground (for debugging)
./start.sh --foreground

# Stop all services
./start.sh --stop

# Force restart
./start.sh --force

# Custom configuration
SERIAL_PORT=/dev/ttyACM1 API_PORT=8080 ./start.sh
```

### API Endpoints

The API server provides the following endpoints:

- **`GET /`** - API information and version
- **`GET /live`** - Latest telemetry sample
  ```bash
  curl http://localhost:8000/live
  ```
- **`GET /history`** - Historical data with optional filters
  ```bash
  curl "http://localhost:8000/history?limit=100"
  curl "http://localhost:8000/history?start_ts=1234567890&end_ts=1234567900"
  ```
- **`GET /summary`** - Aggregated statistics (last hour)
  ```bash
  curl http://localhost:8000/summary
  ```

### Dashboard Features

- **Live Metrics**: Real-time display of all sensor readings
- **Historical Charts**: Time-series visualization of voltages, currents, and SOC
- **Energy Evaluation**: 
  - Total energy generation (Wh) from each source
  - Contribution percentages (PV vs Wind)
  - Power trends over time
- **Environmental Data**: Wind speed and light level trends
- **Auto-refresh**: Configurable refresh interval (1-10 seconds)

### Database Access

View stored data directly:
```bash
sqlite3 hybrid_system.db

# Example queries
SELECT * FROM telemetry ORDER BY timestamp DESC LIMIT 10;
SELECT COUNT(*) FROM telemetry;
SELECT AVG(v_pv), AVG(i_pv) FROM telemetry;
```

## 🛠️ Troubleshooting

### Serial Port Issues

**Problem**: Permission denied accessing `/dev/ttyACM0`
```bash
# Solution: Add user to dialout group
sudo usermod -a -G dialout $USER
newgrp dialout  # Or log out and back in
```

**Problem**: Arduino not detected
```bash
# Check connection
ls -l /dev/ttyACM*

# Test serial communication
screen /dev/ttyACM0 115200
```

### Port Conflicts

**Problem**: Port already in use
```bash
# Find process using port
sudo lsof -i :8000
sudo lsof -i :8501

# Kill specific process
kill <PID>

# Or stop all services
./start.sh --stop
```

### Service Issues

**Problem**: Services not starting
```bash
# Check logs
tail -f logs/serial_reader.log
tail -f logs/api_server.log
tail -f logs/dashboard.log

# Check Python environment
source venv/bin/activate
python --version
pip list
```

### Data Issues

**Problem**: No data appearing in dashboard
1. Verify Arduino is sending data (use `screen` command)
2. Check serial reader is running and parsing correctly
3. Verify database has data: `sqlite3 hybrid_system.db "SELECT COUNT(*) FROM telemetry;"`
4. Check API is responding: `curl http://localhost:8000/live`

## 📁 Project Structure

```
demo/
├── arduino/
│   └── hybrid_low_level.ino      # Arduino sensor reading code
├── serial_reader.py              # Serial communication & data parsing
├── api_server.py                 # FastAPI REST API server
├── dashboard.py                  # Streamlit web dashboard
├── simulator.py                  # Data simulator (for testing without hardware)
├── start.sh                      # Startup script
├── requirements.txt              # Python dependencies
├── hybrid-energy-monitor.service # Systemd service file
├── hybrid_system.db              # SQLite database (created at runtime)
├── logs/                         # Log files (created at runtime)
│   ├── serial_reader.log
│   ├── api_server.log
│   └── dashboard.log
└── README.md                     # This file
```

## 🔬 Recreating the Project

To recreate this project from scratch:

1. **Set up Arduino code** with sensor libraries and serial communication
2. **Create database schema** with telemetry table structure
3. **Implement serial reader** with parsing logic and data validation
4. **Build FastAPI server** with REST endpoints and CORS
5. **Develop Streamlit dashboard** with data visualization and energy calculations
6. **Create startup automation** with process management and logging
7. **Add systemd integration** for production deployment

Key implementation details:
- Serial parsing uses regex to extract values from formatted strings
- Missing sensors (battery, wind speed) are estimated using physics-based models
- Energy calculation uses numerical integration (trapezoidal rule)
- All components communicate via SQLite database as the central data store

## 📝 Notes & Limitations

- **Estimated Values**: `v_bat`, `soc`, and `wind_speed` are estimated from available sensor data, not directly measured
- **Sampling Rate**: Data is collected at ~1 second intervals (Arduino PERIOD_MS = 1000)
- **Battery Model**: Simplified linear model; actual battery behavior may vary
- **Wind Speed**: Estimated from power output; not a direct measurement
- **Single Device**: All services run on a single Raspberry Pi

## 📄 License

This project is developed for educational and research purposes.

## 👥 Authors

Developed as part of a hybrid renewable energy monitoring system project.

---

**For questions or issues**, check the logs in the `logs/` directory or review the troubleshooting section above.
