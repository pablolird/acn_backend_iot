# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastapi",
#     "uvicorn[standard]",
#     "pyserial",
# ]
# ///

import serial.tools.list_ports
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import serial
from typing import Set
from datetime import datetime
from pydantic import BaseModel
import uvicorn
import argparse


app = FastAPI()

# Enable CORS for frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active WebSocket connections
active_connections: Set[WebSocket] = set()

# Arduino Uno VID:PID combinations
ARDUINO_UNO_IDS = [
    (0x2341, 0x0043),  # Arduino Uno Rev3
    (0x2341, 0x0001),  # Arduino Uno
    (0x2A03, 0x0043),  # Arduino Uno clone
    (0x1A86, 0x7523),  # CH340 chip (common in clones)
]
BAUD_RATE = 9600

class JoystickButton(BaseModel):
    pressed: bool

def log(message):
    """Print log with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")

def find_arduino_port():
    """Automatically find the Arduino Uno port by VID:PID"""
    log("Scanning for Arduino ports...")
    ports = serial.tools.list_ports.comports()
    
    log(f"Found {len(ports)} total serial ports:")
    for port in ports:
        vid_pid = f"{port.vid:04X}:{port.pid:04X}" if port.vid else "N/A"
        log(f"  - {port.device}: {port.description} (VID:PID = {vid_pid})")
        
        if port.vid is not None and port.pid is not None:
            if (port.vid, port.pid) in ARDUINO_UNO_IDS:
                log(f"✅ Found Arduino Uno on port: {port.device}")
                return port.device
    
    log("❌ Arduino Uno not found by VID:PID")
    return None

async def read_arduino_data():
    """Read data from Arduino serial port"""
    serial_port = find_arduino_port()
    
    if not serial_port:
        log("ERROR: Could not find Arduino. Please check:")
        log("  1. Arduino is connected via USB")
        log("  2. Arduino sketch is uploaded and running")
        log("  3. Correct drivers are installed")
        return
    
    try:
        log(f"Opening serial connection to {serial_port} at {BAUD_RATE} baud...")
        ser = serial.Serial(serial_port, BAUD_RATE, timeout=1)
        log(f"✅ Connected to Arduino on {serial_port}")
        
        # Clear any initial garbage data
        log("Waiting 2 seconds for Arduino to stabilize...")
        await asyncio.sleep(2)
        ser.reset_input_buffer()
        log("Buffer cleared, starting to read data...")
        
        line_count = 0
        valid_json_count = 0
        
        while True:
            if ser.in_waiting > 0:
                try:
                    raw_line = ser.readline()
                    line_count += 1
                    
                    # Decode with error handling
                    line = raw_line.decode('utf-8', errors='ignore').strip()
                    
                    if not line:
                        continue
                    
                    log(f"📥 Raw line #{line_count}: {line}")
                    
                    # Replace 'nan' with 'null' to make it valid JSON
                    line_fixed = line.replace(':nan,', ':null,').replace(':nan}', ':null}')
                    
                    # Try to parse as JSON
                    data = json.loads(line_fixed)
                    valid_json_count += 1
                    
                    # Extract the values we need
                    filtered_data = {
                        "temperature_c": data.get("temperature_c"),
                        "humidity": data.get("humidity"),
                        "brightness": data.get("brightness"),
                        "sound": data.get("sound"),
                        "intruder": data.get("intruder", False),
                        "fire": data.get("fire", False)
                    }
                    
                    log(f"✅ Valid JSON #{valid_json_count}: {filtered_data}")
                    log(f"📤 Broadcasting to {len(active_connections)} client(s)")
                    
                    # Broadcast to all connected clients
                    await broadcast(filtered_data)
                    
                except json.JSONDecodeError as e:
                    log(f"⚠️ JSON decode error on line #{line_count}: {e}")
                    log(f"   Content was: {line[:100]}")
                except UnicodeDecodeError as e:
                    log(f"⚠️ Unicode decode error: {e}")
                except Exception as e:
                    log(f"❌ Unexpected error: {e}")
                    
            await asyncio.sleep(0.01)
            
    except serial.SerialException as e:
        log(f"❌ Serial error: {e}")
    except Exception as e:
        log(f"❌ Error reading Arduino: {e}")
        import traceback
        traceback.print_exc()

async def broadcast(data: dict):
    """Send data to all connected WebSocket clients"""
    disconnected = set()
    for connection in active_connections:
        try:
            await connection.send_json(data)
        except Exception as e:
            log(f"⚠️ Error sending to client: {e}")
            disconnected.add(connection)
    
    # Remove disconnected clients
    if disconnected:
        log(f"Removing {len(disconnected)} disconnected client(s)")
        active_connections.difference_update(disconnected)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    client_id = id(websocket)
    log(f"🔗 New WebSocket client connected (ID: {client_id})")
    log(f"   Total clients: {len(active_connections)}")
    
    try:
        while True:
            # Keep connection alive and wait for messages
            data = await websocket.receive_text()
            log(f"📨 Received from client {client_id}: {data}")
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        log(f"🔌 Client {client_id} disconnected")
        log(f"   Remaining clients: {len(active_connections)}")

@app.post("/joystick/button")
async def joystick_button_pressed(button: JoystickButton):
    """Handle joystick button press and broadcast to all WebSocket clients"""
    log(f"🎮 Joystick button event received: {button.pressed}")
    
    # Broadcast button press to all connected WebSocket clients
    await broadcast({"type": "joystick_button", "pressed": button.pressed})
    
    return {"status": "ok", "message": "Button press broadcasted"}

@app.on_event("startup")
async def startup_event():
    """Start Arduino data reading on server startup"""
    log("🚀 Server starting up...")
    log(f"   Configured baud rate: {BAUD_RATE}")
    log(f"   Looking for VID:PID combinations: {ARDUINO_UNO_IDS}")
    asyncio.create_task(read_arduino_data())

@app.get("/")
async def root():
    return {
        "message": "Arduino WebSocket Server",
        "endpoint": "/ws",
        "joystick_endpoint": "/joystick/button",
        "active_connections": len(active_connections),
        "status": "running"
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind")
    parser.add_argument("--port", default=8000, type=int, help="Port to bind")
    args = parser.parse_args()

    log("=" * 60)
    log("Arduino WebSocket Server with Joystick Support")
    log(f"Host: {args.host}")
    log(f"Port: {args.port}")
    log("=" * 60)

    uvicorn.run(app, host=args.host, port=args.port)