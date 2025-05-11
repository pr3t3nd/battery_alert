import sys
sys.path.append(r"c:\users\erton\appdata\local\packages\pythonsoftwarefoundation.python.3.13_qbz5n2kfra8p0\localcache\local-packages\python313\site-packages")
import psutil
import time
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageDraw
import pystray
import threading

root = tk.Tk()
root.withdraw()

# --- send_notification and get_battery_status remain the same ---
def get_battery_status():
    """Gets the current battery percentage and charging status."""
    battery = psutil.sensors_battery()
    if battery:
        percentage = battery.percent
        is_charging = battery.power_plugged
        return percentage, is_charging
    else:
        return None, None

def send_notification(title, message):
    """
    Sends a desktop notification using tkinter.
    Ensures the messagebox is shown from the Tkinter main thread.
    """
    def _show_message():
        try:
            if root.winfo_exists():
                messagebox.showwarning(title, message)
            else:
                print(f"Notification '{title}' suppressed: Tkinter root window destroyed.")
        except tk.TclError as e:
            print(f"TclError while trying to show notification '{title}': {e}")

    try:
        if root.winfo_exists():
            root.after(0, _show_message)
        else:
            print(f"Cannot schedule notification '{title}': Tkinter root window destroyed.")
    except tk.TclError:
        print(f"Error scheduling notification (Tkinter root likely destroyed): {title}")
# --- End of unchanged functions ---


def f():
    config = {
        "low_threshold": 20,
        "critical_threshold": 10,
        "notification_interval": 300,
        "check_interval": 60,
    }

    last_notification_time_low = 0
    last_notification_time_critical = 0
    
    # icon_title_var will store the current title string
    # We'll pass the icon object to notify_if_needed or access it via nonlocal
    icon_instance_ref = [None] # Use a list to pass by reference for icon object

    def notify_if_needed():
        nonlocal last_notification_time_low, last_notification_time_critical
        # Access the icon instance via the reference
        current_icon = icon_instance_ref[0] 
        
        percent, charging = get_battery_status()

        if percent is not None:
            # print(f"Battery: {percent}%, Charging: {charging}") # Debug
            current_time = time.time()

            new_title = f"Battery: {percent}%"
            if charging:
                new_title += " (Charging)"
            
            # Update the icon's title if it has changed and the icon exists
            if current_icon and new_title != current_icon.title:
                current_icon.title = new_title

            if not charging:
                if percent <= config["critical_threshold"]:
                    if (current_time - last_notification_time_critical >= config["notification_interval"]):
                        send_notification("Critical Battery", f"Battery is critically low at {percent}%. Please connect to power immediately!")
                        last_notification_time_critical = current_time
                        last_notification_time_low = current_time
                elif percent <= config["low_threshold"]:
                    if (current_time - last_notification_time_low >= config["notification_interval"]):
                        send_notification("Low Battery", f"Battery is low at {percent}%. Consider connecting to power.")
                        last_notification_time_low = current_time
        else:
            print("Could not retrieve battery information.")
            if current_icon and "Error" not in current_icon.title:
                 # Avoid spamming "Error" if it's already set
                current_icon.title = "Battery: Error"


    def on_tray_exit(tray_icon_obj, item):
        print("Tray icon: Exit requested.")
        tray_icon_obj.stop()
        if root.winfo_exists():
            root.after(0, root.quit)

    def create_icon_image(color=(255, 0, 0)):
        image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 63, 63), fill=color)
        return image

    tray_icon_image = create_icon_image()
    initial_title = "Battery: Initializing..."
    menu = (pystray.MenuItem('Exit', on_tray_exit),)
    
    # Create the icon instance and store it in the reference
    icon_instance_ref[0] = pystray.Icon(
        "BatteryMonitor",
        tray_icon_image,
        initial_title, # Set initial title directly
        menu
    )

    monitor_thread_stop_event = threading.Event()

    def run_monitor_loop():
        try:
            notify_if_needed() # Initial check
        except Exception as e:
            print(f"Error during initial notify_if_needed: {e}") # This is where your error occurred

        while not monitor_thread_stop_event.wait(config["check_interval"]):
            if monitor_thread_stop_event.is_set():
                break
            try:
                notify_if_needed()
            except Exception as e:
                print(f"Error in notify_if_needed loop: {e}")
                if not root.winfo_exists() or monitor_thread_stop_event.is_set():
                    print("Root window gone or stop event set, stopping battery check loop.")
                    break
        print("Battery monitor thread finished.")

    monitor_thread = threading.Thread(target=run_monitor_loop)
    monitor_thread.daemon = True

    def run_pystray_icon():
        print("pystray thread started.")
        current_icon = icon_instance_ref[0]
        try:
            if current_icon:
                current_icon.run()
        except Exception as e:
            print(f"Exception in pystray thread: {e}")
        finally:
            print("pystray thread finished.")
            if root.winfo_exists():
                root.after(0, root.quit)

    pystray_thread = threading.Thread(target=run_pystray_icon)
    pystray_thread.daemon = True

    try:
        monitor_thread.start()
        pystray_thread.start()
        print("Starting Tkinter mainloop in main thread.")
        root.mainloop()
    except KeyboardInterrupt:
        print("KeyboardInterrupt received. Shutting down...")
    except Exception as e:
        print(f"Error in main execution block: {e}")
    finally:
        print("Tkinter mainloop finished or interrupted. Cleaning up...")
        monitor_thread_stop_event.set()
        
        current_icon = icon_instance_ref[0]
        if current_icon and current_icon.visible:
            print("Stopping pystray icon (if still visible)...")
            current_icon.stop()

        print("Waiting for pystray thread to join...")
        pystray_thread.join(timeout=2)
        if pystray_thread.is_alive():
            print("pystray thread did not join in time.")

        print("Waiting for monitor thread to join...")
        monitor_thread.join(timeout=2)
        if monitor_thread.is_alive():
            print("Monitor thread did not join in time.")

        if root.winfo_exists():
            print("Destroying Tkinter root window.")
            root.destroy()
        print("Application cleanup complete. Exiting.")

if __name__ == "__main__":
    f()