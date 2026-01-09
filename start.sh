#!/bin/bash

# Hybrid Solar-Wind Energy System - Startup Script
# This script starts all components of the monitoring system on a Raspberry Pi
#
# Usage:
#   ./start.sh              # Start all services in background
#   ./start.sh --foreground # Start all services in foreground (for debugging)
#   ./start.sh --stop       # Stop all running services

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# SERIAL_PORT is optional - if not set, serial_reader.py will auto-detect Arduino
SERIAL_PORT="${SERIAL_PORT:-}"
API_PORT="${API_PORT:-8000}"
STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"

# PID files
PID_DIR="$SCRIPT_DIR/.pids"
SERIAL_PID_FILE="$PID_DIR/serial_reader.pid"
API_PID_FILE="$PID_DIR/api_server.pid"
DASHBOARD_PID_FILE="$PID_DIR/dashboard.pid"

# Log files
LOG_DIR="$SCRIPT_DIR/logs"
SERIAL_LOG="$LOG_DIR/serial_reader.log"
API_LOG="$LOG_DIR/api_server.log"
DASHBOARD_LOG="$LOG_DIR/dashboard.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create necessary directories
mkdir -p "$PID_DIR"
mkdir -p "$LOG_DIR"

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if a process is running
is_running() {
    local pid_file=$1
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$pid_file"
            return 1
        fi
    fi
    return 1
}

# Function to stop a service
stop_service() {
    local service_name=$1
    local pid_file=$2
    
    if is_running "$pid_file"; then
        local pid=$(cat "$pid_file")
        print_info "Stopping $service_name (PID: $pid)..."
        kill "$pid" 2>/dev/null || true
        sleep 1
        if ps -p "$pid" > /dev/null 2>&1; then
            print_warn "Process still running, force killing..."
            kill -9 "$pid" 2>/dev/null || true
        fi
        rm -f "$pid_file"
        print_info "$service_name stopped"
    else
        print_warn "$service_name is not running"
    fi
}

# Function to stop all services
stop_all() {
    print_info "Stopping all services..."
    stop_service "Serial Reader" "$SERIAL_PID_FILE"
    stop_service "API Server" "$API_PID_FILE"
    stop_service "Dashboard" "$DASHBOARD_PID_FILE"
    print_info "All services stopped"
    exit 0
}

# Handle --stop flag
if [ "$1" == "--stop" ]; then
    stop_all
fi

# Check if services are already running
if is_running "$SERIAL_PID_FILE" || is_running "$API_PID_FILE" || is_running "$DASHBOARD_PID_FILE"; then
    print_warn "Some services appear to be already running"
    print_info "Use './start.sh --stop' to stop them first, or use --force to restart"
    if [ "$1" != "--force" ]; then
        exit 1
    fi
    stop_all
fi

# Check Python installation
if ! command -v python3 &> /dev/null; then
    print_error "Python3 is not installed"
    exit 1
fi

# Check if virtual environment exists, create if not
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    print_info "Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/venv"
fi

# Activate virtual environment
print_info "Activating virtual environment..."
source "$SCRIPT_DIR/venv/bin/activate"

# Install/update dependencies
print_info "Checking dependencies..."
pip install -q --upgrade pip
pip install -q -r "$SCRIPT_DIR/requirements.txt"

# Check serial port (only if explicitly set)
if [ -n "$SERIAL_PORT" ] && [ ! -e "$SERIAL_PORT" ]; then
    print_warn "Specified serial port $SERIAL_PORT not found"
    print_info "Available serial ports:"
    ls -1 /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || echo "  (none found)"
    print_warn "Continuing anyway - serial reader will auto-detect if port not specified"
elif [ -z "$SERIAL_PORT" ]; then
    print_info "Serial port not specified - serial reader will auto-detect Arduino"
fi

# Function to start serial reader
start_serial_reader() {
    if [ "$FOREGROUND" = true ]; then
        print_info "Starting Serial Reader (foreground)..."
        cd "$SCRIPT_DIR"
        if [ -n "$SERIAL_PORT" ]; then
            python3 serial_reader.py "$SERIAL_PORT"
        else
            python3 serial_reader.py
        fi
    else
        print_info "Starting Serial Reader (background)..."
        cd "$SCRIPT_DIR"
        if [ -n "$SERIAL_PORT" ]; then
            nohup python3 serial_reader.py "$SERIAL_PORT" > "$SERIAL_LOG" 2>&1 &
        else
            nohup python3 serial_reader.py > "$SERIAL_LOG" 2>&1 &
        fi
        echo $! > "$SERIAL_PID_FILE"
        sleep 2
        if is_running "$SERIAL_PID_FILE"; then
            print_info "Serial Reader started (PID: $(cat $SERIAL_PID_FILE), Log: $SERIAL_LOG)"
        else
            print_error "Serial Reader failed to start. Check $SERIAL_LOG"
            return 1
        fi
    fi
}

# Function to start API server
start_api_server() {
    if [ "$FOREGROUND" = true ]; then
        print_info "Starting API Server (foreground)..."
        cd "$SCRIPT_DIR"
        uvicorn api_server:app --host 0.0.0.0 --port "$API_PORT"
    else
        print_info "Starting API Server (background)..."
        cd "$SCRIPT_DIR"
        nohup uvicorn api_server:app --host 0.0.0.0 --port "$API_PORT" > "$API_LOG" 2>&1 &
        echo $! > "$API_PID_FILE"
        sleep 2
        if is_running "$API_PID_FILE"; then
            print_info "API Server started (PID: $(cat $API_PID_FILE), Log: $API_LOG)"
            print_info "API available at: http://localhost:$API_PORT"
        else
            print_error "API Server failed to start. Check $API_LOG"
            return 1
        fi
    fi
}

# Function to start dashboard
start_dashboard() {
    if [ "$FOREGROUND" = true ]; then
        print_info "Starting Dashboard (foreground)..."
        cd "$SCRIPT_DIR"
        streamlit run dashboard.py --server.port "$STREAMLIT_PORT" --server.address 0.0.0.0
    else
        print_info "Starting Dashboard (background)..."
        cd "$SCRIPT_DIR"
        nohup streamlit run dashboard.py --server.port "$STREAMLIT_PORT" --server.address 0.0.0.0 --server.headless true > "$DASHBOARD_LOG" 2>&1 &
        echo $! > "$DASHBOARD_PID_FILE"
        sleep 3
        if is_running "$DASHBOARD_PID_FILE"; then
            print_info "Dashboard started (PID: $(cat $DASHBOARD_PID_FILE), Log: $DASHBOARD_LOG)"
            print_info "Dashboard available at: http://localhost:$STREAMLIT_PORT"
        else
            print_error "Dashboard failed to start. Check $DASHBOARD_LOG"
            return 1
        fi
    fi
}

# Handle --foreground flag
FOREGROUND=false
if [ "$1" == "--foreground" ]; then
    FOREGROUND=true
    print_info "Starting services in foreground mode..."
    print_info "Press Ctrl+C to stop all services"
    
    # Trap Ctrl+C to cleanup
    trap 'print_info "\nShutting down..."; stop_all; exit 0' INT TERM
    
    # Start services (they'll run in foreground)
    start_serial_reader &
    SERIAL_PID=$!
    sleep 1
    
    start_api_server &
    API_PID=$!
    sleep 1
    
    start_dashboard &
    DASHBOARD_PID=$!
    
    # Wait for all processes
    wait
else
    # Start all services in background
    print_info "Starting all services in background mode..."
    print_info "Use './start.sh --stop' to stop all services"
    print_info ""
    
    start_serial_reader
    sleep 1
    
    start_api_server
    sleep 1
    
    start_dashboard
    
    print_info ""
    print_info "=========================================="
    print_info "All services started successfully!"
    print_info "=========================================="
    print_info "Dashboard: http://localhost:$STREAMLIT_PORT"
    print_info "API:       http://localhost:$API_PORT"
    print_info ""
    print_info "To view logs:"
    print_info "  tail -f $SERIAL_LOG"
    print_info "  tail -f $API_LOG"
    print_info "  tail -f $DASHBOARD_LOG"
    print_info ""
    print_info "To stop all services:"
    print_info "  ./start.sh --stop"
    print_info ""
fi

