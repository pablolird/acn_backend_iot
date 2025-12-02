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
API_ENDPOINT = "http://10.42.0.225:8000/joystick/button"

def log(message):
    """Print log with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")

def setup_gpio():
    """Initialize GPIO for joystick button"""
    # Clean up any previous GPIO settings
    GPIO.setwarnings(False)
    GPIO.cleanup()
    
    # Set mode and configure pin
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(JOYSTICK_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    # Give it a moment to stabilize
    time.sleep(0.1)
    
    log(f"✅ GPIO initialized - Button pin: {JOYSTICK_BUTTON_PIN}")

def send_button_press():
    """Send button press to backend"""
    log("🎮 Joystick button PRESSED!")
    try:
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
        
        log("👂 Listening for button presses (polling mode)...")
        log("💡 Tip: Run with sudo if you encounter permission issues")
        
        last_state = GPIO.input(JOYSTICK_BUTTON_PIN)
        button_pressed = False
        
        # Polling loop instead of event detection
        while True:
            current_state = GPIO.input(JOYSTICK_BUTTON_PIN)
            
            # Button is pressed when state goes from HIGH (1) to LOW (0)
            if last_state == 1 and current_state == 0 and not button_pressed:
                send_button_press()
                button_pressed = True
            
            # Button is released when state goes back to HIGH
            elif current_state == 1 and button_pressed:
                button_pressed = False
            
            last_state = current_state
            time.sleep(0.01)  # Poll every 10ms
            
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
