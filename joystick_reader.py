# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "RPi.GPIO",
#     "requests",
# ]
# ///

import RPi.GPIO as GPIO
import time
import requests
from datetime import datetime

# GPIO Pin for HW-504 Joystick Button (SW pin)
JOYSTICK_BUTTON_PIN = 17  # Change this to match your wiring

# Backend API endpoint
API_ENDPOINT = "http://localhost:8000/joystick/button"

def log(message):
    """Print log with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")

def setup_gpio():
    """Initialize GPIO for joystick button"""
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(JOYSTICK_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    log(f"✅ GPIO initialized - Button pin: {JOYSTICK_BUTTON_PIN}")

def button_callback(channel):
    """Callback function when button is pressed"""
    log("🎮 Joystick button PRESSED!")
    try:
        # Send button press to backend
        response = requests.post(API_ENDPOINT, json={"pressed": True}, timeout=0.5)
        if response.status_code == 200:
            log("✅ Button press sent to backend")
        else:
            log(f"⚠️ Backend responded with status {response.status_code}")
    except requests.exceptions.RequestException as e:
        log(f"❌ Failed to send button press: {e}")

def main():
    log("=" * 60)
    log("Joystick Button Reader for Raspberry Pi")
    log("=" * 60)
    log(f"Monitoring joystick button on GPIO pin {JOYSTICK_BUTTON_PIN}")
    log(f"Sending events to: {API_ENDPOINT}")
    log("Press Ctrl+C to exit")
    log("=" * 60)
    
    try:
        setup_gpio()
        
        # Add event detection for button press (falling edge = button pressed)
        GPIO.add_event_detect(
            JOYSTICK_BUTTON_PIN,
            GPIO.FALLING,
            callback=button_callback,
            bouncetime=200  # 200ms debounce
        )
        
        log("👂 Listening for button presses...")
        
        # Keep the script running
        while True:
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        log("\n🛑 Shutting down...")
    except Exception as e:
        log(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        GPIO.cleanup()
        log("✅ GPIO cleanup complete")

if __name__ == "__main__":
    main()