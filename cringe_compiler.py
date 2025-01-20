import os
import sys
import requests
import pyperclip
import shutil
import time
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Constants for API URLs
REMOVE_BG_URL = "https://api.remove.bg/v1.0/removebg"
CATBOX_API_URL = "https://catbox.moe/user/api.php"

# Default configuration file path
CONFIG_FILE = "config.json"

# Helper function to get resource paths
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class ScreenshotHandler(FileSystemEventHandler):
    def __init__(self, on_new_screenshot):
        self.on_new_screenshot = on_new_screenshot

    def on_created(self, event):
        if not event.is_directory:
            filepath = event.src_path
            print(f"New file detected: {filepath}")
            # Only process high-resolution images (ignores thumbnails)
            if self.is_high_resolution_image(filepath):
                self.on_new_screenshot(filepath)

    def is_high_resolution_image(self, filepath):
        try:
            with Image.open(filepath) as img:
                width, height = img.size
                return width > 800 and height > 600  # Adjust resolution threshold as needed
        except Exception as e:
            print(f"Error checking image resolution: {e}")
            return False

class ScreenshotUploader:
    def __init__(self, root):
        self.root = root
        self.root.geometry("800x600")
        self.root.overrideredirect(True)  # Remove title bar and border
        self.root.wm_attributes("-transparentcolor", "pink")  # Set transparency for a specific color

        # Load the Shrek-shaped background image
        self.bg_image = Image.open(resource_path("assets/kytkc87s6vd81-removebg-preview.png")).convert("RGBA")
        self.bg_image_tk = ImageTk.PhotoImage(self.bg_image)

        # Set the background image
        self.canvas = tk.Canvas(self.root, width=self.bg_image.width, height=self.bg_image.height, bg="pink", highlightthickness=0)
        self.canvas.create_image(0, 0, anchor="nw", image=self.bg_image_tk)
        self.canvas.pack(fill="both", expand=True)

        # Add a draggable area
        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag_window)

        # Load configuration
        self.config = self.load_config()
        self.remove_bg_enabled = tk.BooleanVar(value=self.config.get("remove_bg_enabled", False))

        # Add all UI elements over the background
        self.add_ui_elements()

        # Start folder watcher
        self.setup_folder_watcher()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        return {}

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=4)

    def add_ui_elements(self):
        # Arrange elements in a logical order

        # API Key entry
        api_key_label = tk.Label(self.canvas, text="Remove.bg API Key:", bg="#1c1c1c", fg="white", font=("Arial", 10, "bold"))
        api_key_label.place(x=50, y=50)
        self.api_key_entry = tk.Entry(self.canvas, width=40, font=("Arial", 10))
        self.api_key_entry.place(x=200, y=50)
        self.api_key_entry.insert(0, self.config.get("remove_bg_api_key", ""))

        # Remove Background button
        remove_bg_button = tk.Checkbutton(self.canvas, text="Remove Background", variable=self.remove_bg_enabled, bg="#1c1c1c", fg="white", selectcolor="#2b2b2b", font=("Arial", 10, "bold"), command=self.save_settings)
        remove_bg_button.place(x=50, y=100)

        # Save settings button
        save_button = tk.Button(self.canvas, text="Save Settings", command=self.save_settings, bg="#4caf50", fg="white", font=("Arial", 10, "bold"), relief="flat", width=15)
        save_button.place(x=200, y=100)

        # Change directory button
        change_dir_button = tk.Button(self.canvas, text="Change Directory", command=self.change_directory, bg="#2196f3", fg="white", font=("Arial", 10, "bold"), relief="flat", width=15)
        change_dir_button.place(x=200, y=150)

        # Upload history placeholder (centered and larger)
        history_label = tk.Label(self.canvas, text="Upload History", bg="#1c1c1c", fg="white", font=("Arial", 10, "bold"))
        history_label.place(x=50, y=200)
        self.history_list = tk.Listbox(self.canvas, bg="#1c1c1c", fg="#ffffff", width=70, height=15, font=("Arial", 10))
        self.history_list.place(x=50, y=230)

        # Close button
        close_button = tk.Button(self.canvas, text="X", command=self.root.destroy, bg="red", fg="white", font=("Arial", 10, "bold"), relief="flat", width=3)
        close_button.place(x=750, y=10)

    def setup_folder_watcher(self):
        watch_dir = self.config.get("watch_directory", "")
        if not watch_dir:
            watch_dir = filedialog.askdirectory(title="Select Screenshot Folder")
            if not watch_dir:
                return
            self.config["watch_directory"] = watch_dir
            self.save_config()

        event_handler = ScreenshotHandler(self.process_screenshot)
        observer = Observer()
        observer.schedule(event_handler, path=watch_dir, recursive=False)
        observer.start()
        print(f"Watching directory: {watch_dir}")

    def process_screenshot(self, filepath):
        time.sleep(2)  # Ensure file is fully written

        if self.remove_bg_enabled.get():
            filepath = self.remove_background(filepath)

        self.upload_to_catbox(filepath)

    def remove_background(self, filepath):
        api_key = self.api_key_entry.get()
        if not api_key:
            messagebox.showerror("Error", "Please provide a remove.bg API key.")
            return filepath

        with open(filepath, "rb") as file:
            response = requests.post(
                REMOVE_BG_URL,
                headers={"X-Api-Key": api_key},
                files={"image_file": file}
            )

        if response.status_code == 200:
            output_path = filepath.replace(".jpg", "_no_bg.png")
            with open(output_path, "wb") as out_file:
                out_file.write(response.content)
            return output_path
        else:
            print(f"Error from remove.bg: {response.text}")
            return filepath

    def upload_to_catbox(self, filepath):
        try:
            with open(filepath, "rb") as file:
                response = requests.post(
                    CATBOX_API_URL,
                    data={"reqtype": "fileupload"},
                    files={"fileToUpload": file}
                )

            if response.status_code == 200 and response.text.startswith("https"):
                url = response.text
                pyperclip.copy(url)
                self.history_list.insert(tk.END, url)
                print(f"Uploaded to Catbox: {url}")

                # Save the link to a .txt file in the screenshot directory
                screenshot_dir = self.config.get("watch_directory", "")
                if screenshot_dir:
                    history_file = os.path.join(screenshot_dir, "catbox_links.txt")
                    with open(history_file, "a") as f:
                        f.write(url + "\n")
            else:
                print(f"Failed to upload to Catbox: {response.text}")

        except Exception as e:
            print(f"Error uploading file: {e}")

    def change_directory(self):
        new_dir = filedialog.askdirectory(title="Select Screenshot Folder")
        if new_dir:
            self.config["watch_directory"] = new_dir
            self.save_config()
            messagebox.showinfo("Directory Changed", f"Now watching: {new_dir}")

    def save_settings(self):
        self.config["remove_bg_api_key"] = self.api_key_entry.get()
        self.config["remove_bg_enabled"] = self.remove_bg_enabled.get()
        self.save_config()
        messagebox.showinfo("Settings Saved", "Your settings have been saved.")

    def start_drag(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def drag_window(self, event):
        x = self.root.winfo_x() + event.x - self._drag_start_x
        y = self.root.winfo_y() + event.y - self._drag_start_y
        self.root.geometry(f"+{x}+{y}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ScreenshotUploader(root)
    root.mainloop()
