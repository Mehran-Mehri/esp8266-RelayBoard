import customtkinter as ctk
import websocket
import threading
import json
import os
import time
import serial
import serial.tools.list_ports
from zeroconf import Zeroconf, ServiceBrowser
from PIL import Image
import qrcode
import sys

# --- VISUAL CONFIGURATION ---
THEME = {
    "bg_main": "#141414",       
    "bg_card": "#212121",       
    "bg_menu": "#2b2b2b",       
    "accent": "#5E62FF",        
    "success": "#00E676",       
    "danger": "#FF1744",        
    "text_main": "#FFFFFF",
    "text_sub": "#9E9E9E",
    "border": "#333333"
}

# 1. ASSET PATH (Where the script/exe is running)
# This is used for finding "qr_icon.png"
if getattr(sys, 'frozen', False):
    # If compiled as an .exe (PyInstaller)
    SCRIPT_DIR = sys._MEIPASS 
else:
    # If running as a .py script
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. USER DATA PATH (Where we save the config)
# This is used for "relay_config_v2.json"
APP_NAME = "DamonControl"
if os.name == 'nt':
    base_dir = os.environ["APPDATA"]
else:
    base_dir = os.path.join(os.path.expanduser("~"), ".config")

DATA_DIR = os.path.join(base_dir, APP_NAME)
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

CONFIG_FILE = os.path.join(DATA_DIR, "relay_config_v2.json")
PORT = "81"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# ==========================================
# ENCAPSULATED RELAY BOARD LOGIC
# ==========================================
class RelayBoardTab(ctk.CTkFrame):
    """Handles the UI and WebSocket connection for a single relay board."""
    # Update the arguments to accept delete_callback
    def __init__(self, master, board_name, board_config, save_callback, delete_callback, refresh_callback):
        super().__init__(master, fg_color="transparent")
        self.board_name = board_name
        self.config = board_config
        self.save_callback = save_callback
        self.delete_callback = delete_callback
        self.refresh_callback = refresh_callback

        self.target_ip = self.config.get("ip", "")
        self.relay_names = self.config.get("names", {"1":"Light", "2":"Fan", "3":"Outlet", "4":"Aux"})
        
        self.ws = None
        self.is_connected = False
        self.relay_controls = {}
        self.keep_trying = True

        # --- TAB UI LAYOUT ---
        self.status_frame = ctk.CTkFrame(self, fg_color=THEME["bg_card"], corner_radius=20, border_width=1, border_color=THEME["border"])
        self.status_frame.pack(pady=(10, 20), fill="x", padx=10) # <--- Added fill="x" and padx so it stretches
        
        self.status_dot = ctk.CTkLabel(self.status_frame, text="●", text_color=THEME["text_sub"], font=("Arial", 16))
        self.status_dot.pack(side="left", padx=(15, 5), pady=5)
        
        self.lbl_status = ctk.CTkLabel(self.status_frame, text="DISCONNECTED", text_color=THEME["text_sub"], 
                                       font=ctk.CTkFont(size=11, weight="bold"))
        self.lbl_status.pack(side="left", padx=(0, 15), pady=5)

        # --- NEW DELETE BUTTON ---
        self.btn_delete = ctk.CTkButton(self.status_frame, text="Delete", width=60, height=24, 
                                        fg_color="transparent", text_color=THEME["danger"], 
                                        border_width=1, border_color=THEME["danger"],
                                        font=ctk.CTkFont(size=11), corner_radius=12,
                                        hover_color="#5c1010",
                                        command=self.confirm_delete)
        self.btn_delete.pack(side="right", padx=15, pady=5)

        # Scrollable container just in case
        self.scroll_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_container.pack(fill="both", expand=True, padx=10, pady=0)

        for i in range(1, 5):
            self.create_relay_card(i)

        if self.target_ip:
            self.after(500, self.connect)

    def create_relay_card(self, r_num):
        r_str = str(r_num)
        card = ctk.CTkFrame(self.scroll_container, corner_radius=12, fg_color=THEME["bg_card"], 
                            border_width=1, border_color=THEME["border"], height=80)
        card.pack(fill="x", pady=8)
        card.grid_columnconfigure(0, weight=1) 

        # 1. Relay Name (Column 0)
        lbl_name = ctk.CTkLabel(card, text=self.relay_names.get(r_str, f"Relay {r_str}"), 
                                font=ctk.CTkFont(size=16, weight="bold"), anchor="w", text_color=THEME["text_main"])
        lbl_name.grid(row=0, column=0, sticky="w", padx=20, pady=25)
        
                # 2. Edit Name Button (Column 1)
        btn_rename = ctk.CTkButton(card, text="Edit", width=50, height=24, fg_color="transparent", 
                                   text_color=THEME["text_sub"], border_width=1, border_color=THEME["border"],
                                   font=ctk.CTkFont(size=11), corner_radius=12,
                                   command=lambda r=r_str, l=lbl_name: self.ask_rename(r, l))
        btn_rename.grid(row=0, column=1, padx=(5, 10))

        # 3. The Main Switch (Column 2)
        switch_var = ctk.StringVar(master=card, value="OFF") 
        switch = ctk.CTkSwitch(card, text="", variable=switch_var, onvalue="ON", offvalue="OFF",
                               width=50, height=25, progress_color=THEME["accent"], button_hover_color="#AAAAAA",
                               command=lambda r=r_str, v=switch_var: self.toggle_relay(r, v))
        switch.grid(row=0, column=2, padx=(5, 20))
        
        self.relay_controls[r_str] = {'switch': switch, 'var': switch_var, 'label': lbl_name}

    def ask_rename(self, r_str, label_widget):
        dialog = ctk.CTkInputDialog(text=f"Rename Relay {r_str}:", title="Edit Name")
        new = dialog.get_input()
        if new:
            self.send_command(f"SET_NAME:{r_str}:{new}")

    def toggle_relay(self, r_str, var):
        if not self.is_connected:
            self.status_frame.configure(border_color=THEME["danger"])
            self.lbl_status.configure(text="NOT CONNECTED", text_color=THEME["danger"])
            self.status_dot.configure(text_color=THEME["danger"])
            self.after(1000, lambda: self.update_status_ui(False)) 
            var.set("OFF" if var.get() == "ON" else "ON")
            return
        self.send_command(f"{r_str}_{var.get()}")

    def confirm_delete(self):
        # Create a popup confirmation dialog
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm")
        dialog.geometry("300x150")
        dialog.grab_set() # Forces user to interact with this window
        dialog.configure(fg_color=THEME["bg_card"])
        
        lbl = ctk.CTkLabel(dialog, text=f"Delete '{self.board_name}'?", font=ctk.CTkFont(size=16, weight="bold"))
        lbl.pack(pady=(25, 15))
        
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20)
        
        # Cancel button
        btn_cancel = ctk.CTkButton(btn_frame, text="Cancel", width=100, fg_color="transparent", 
                                   border_width=1, border_color=THEME["border"], text_color=THEME["text_main"],
                                   command=dialog.destroy)
        btn_cancel.pack(side="left", padx=10)
        
        # Confirm button (triggers the main app's delete function)
        btn_confirm = ctk.CTkButton(btn_frame, text="Delete", width=100, fg_color=THEME["danger"], hover_color="#8b0000",
                                    command=lambda: [dialog.destroy(), self.delete_callback(self.board_name)])
        btn_confirm.pack(side="right", padx=10)

    # --- WEBSOCKET LOGIC ---
    def connect(self):
        self.lbl_status.configure(text="CONNECTING...", text_color="orange")
        self.status_dot.configure(text_color="orange")
        threading.Thread(target=self.start_ws, daemon=True).start()

    def start_ws(self):
        try:
            self.ws = websocket.WebSocketApp(f"ws://{self.target_ip}:{PORT}", 
                                             on_open=self.on_open, on_message=self.on_message, 
                                             on_error=self.on_error, on_close=self.on_close_ws)
            # ADD PING INTERVAL AND TIMEOUT HERE:
            self.ws.run_forever(ping_interval=5, ping_timeout=3)
            
        except Exception as e:
            self.on_error(None, str(e))
            
        # If run_forever() ends (because connection failed or dropped), 
        # wait 3 seconds and try again, unless the app is closing.
        if self.keep_trying:
            self.after(3000, self.connect)

    def disconnect(self):
        self.keep_trying = False
        if self.ws: self.ws.close()

    def send_command(self, cmd):
        if self.ws and self.is_connected: self.ws.send(cmd)

    def on_open(self, ws):
        self.is_connected = True
        self.after(0, lambda: self.update_status_ui(True))

    def on_message(self, ws, msg): 
        # --- NEW ESP NAME INTERCEPTOR ---
        if msg.startswith("NAMES:"):
            names = msg.replace("NAMES:", "").split("|")
            if len(names) == 4:
                for i in range(4):
                    self.relay_names[str(i+1)] = names[i]
                
                # Cache them locally just in case the board goes offline
                self.config["names"] = self.relay_names
                self.save_callback()
                
                # Update the UI on the main Tkinter thread
                self.after(0, self.update_relay_labels)
            return

        # --- ORIGINAL RELAY SYNC/TOGGLE INTERCEPTOR ---
        parts = msg.split(":")[1:] if msg.startswith("SYNC") else [msg]
        for part in parts:
            try:
                r, s = part.split("_")
                if r in self.relay_controls: 
                    self.after(0, lambda relay_id=r, state=s: self.relay_controls[relay_id]['var'].set(state))
            except: pass

    def update_relay_labels(self):
        # Update the names on this specific board's tab
        for r_str in ["1", "2", "3", "4"]:
            if r_str in self.relay_controls and r_str in self.relay_names:
                self.relay_controls[r_str]['label'].configure(text=self.relay_names[r_str])
        
        # Redraw the main combined dashboard to reflect the new names
        if self.refresh_callback:
            self.refresh_callback()

    def on_error(self, ws, err):
        self.after(0, lambda: self.update_status_ui(False))

    def on_close_ws(self, ws, *args):
        self.is_connected = False
        self.after(0, lambda: self.update_status_ui(False))

    def update_status_ui(self, connected):
        color = THEME["success"] if connected else THEME["border"]
        text_c = THEME["success"] if connected else THEME["text_sub"]
        text = f"ONLINE ({self.target_ip})" if connected else f"OFFLINE ({self.target_ip})"
        
        # Update the individual tab's UI
        self.lbl_status.configure(text=text, text_color=text_c)
        self.status_dot.configure(text_color=text_c if connected else THEME["danger"])
        self.status_frame.configure(border_color=color)

        # --- NEW: UPDATE THE DASHBOARD LABEL IF IT EXISTS ---
        if hasattr(self, 'dash_status_lbl') and self.dash_status_lbl.winfo_exists():
            dash_text = "● ONLINE" if connected else "● OFFLINE"
            dash_color = THEME["success"] if connected else THEME["danger"]
            self.dash_status_lbl.configure(text=dash_text, text_color=dash_color)

    def show_qr_code(self):
        # 1. Package the exact configuration needed for the mobile app
        payload = {
            "name": self.board_name,
            "ip": self.target_ip,
            "names": self.relay_names
        }
        json_payload = json.dumps(payload)

        # 2. Generate the QR Code image
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(json_payload)
        qr.make(fit=True)
        
        # --- THE FIX: Extract the raw PIL Image object ---
        qr_wrapper = qr.make_image(fill_color="black", back_color="white")
        pil_img = qr_wrapper.get_image().convert("RGB")

        # 3. Show it in a popup
        dialog = ctk.CTkToplevel(self)
        dialog.title("Scan with Mobile App")
        dialog.geometry("350x400")
        dialog.grab_set()
        dialog.configure(fg_color=THEME["bg_card"])
        
        ctk.CTkLabel(dialog, text="Add Board to Android", font=ctk.CTkFont(size=16, weight="bold"), text_color=THEME["text_main"]).pack(pady=(20, 10))
        
        # Convert the raw PIL image to CTkImage
        qr_ctk = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(250, 250))
        lbl_qr = ctk.CTkLabel(dialog, text="", image=qr_ctk)
        lbl_qr.pack(pady=10)
        
        ctk.CTkLabel(dialog, text=f"IP: {self.target_ip}", text_color=THEME["text_sub"], font=ctk.CTkFont(size=11)).pack()

# ==========================================
# MAIN APP (TAB MANAGER)
# ==========================================
class RelayApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Damon Control")
        self.geometry("450x650")
        self.configure(fg_color=THEME["bg_main"])
        self.resizable(False, False)

        self.menu_visible = False
        self.board_tabs = {} 

        self.config_data = self.load_config()

        self.create_header()

        # --- TABVIEW & EMPTY STATE ---
        self.tabview = ctk.CTkTabview(self, fg_color="transparent", segmented_button_selected_color=THEME["accent"],
                                      segmented_button_selected_hover_color="#4d51d0")
        
        # Big button for when no boards exist
        self.btn_add_first = ctk.CTkButton(self, text="+ Add New Board", fg_color=THEME["accent"], 
                                           hover_color="#4d51d0", height=50, width=200, 
                                           font=ctk.CTkFont(size=16, weight="bold"),
                                           command=self.open_board_wizard)

        # Check if we have boards. If yes, load tabs. If no, show the big add button.
        if self.config_data.get("boards"):
            self.tabview.pack(fill="both", expand=True, padx=15, pady=0)

            self.dashboard_tab = self.tabview.add("Dashboard") 
            self.scroll_dash = ctk.CTkScrollableFrame(self.dashboard_tab, fg_color="transparent")
            self.scroll_dash.pack(fill="both", expand=True, padx=5, pady=5)

            for board_name, board_config in self.config_data["boards"].items():
                self.add_board_tab(board_name, board_config, is_startup=True)
            
            self.refresh_dashboard() # Populate the dashboard
        else:
            self.btn_add_first.place(relx=0.5, rely=0.45, anchor="center")

        # --- CUSTOM MENU ---
        self.menu_shadow = ctk.CTkFrame(self, width=180, height=105, corner_radius=10, fg_color="#000000")
        self.overlay_frame = ctk.CTkFrame(self, width=180, height=105, corner_radius=10, 
                                          fg_color=THEME["bg_menu"], border_width=1, border_color=THEME["border"])
        self.create_menu_items()

        self.bind("<Button-1>", self.check_menu_close)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def add_board_tab(self, board_name, board_config, is_startup=False):
        # If adding the first board while the app is already running
        if not is_startup and not self.board_tabs:
            self.btn_add_first.place_forget()
            self.tabview.pack(fill="both", expand=True, padx=15, pady=0)
            
            self.dashboard_tab = self.tabview.add("Dashboard")
            self.scroll_dash = ctk.CTkScrollableFrame(self.dashboard_tab, fg_color="transparent")
            self.scroll_dash.pack(fill="both", expand=True, padx=5, pady=5)

        tab_frame = self.tabview.add(board_name)
        
        # Pass self.refresh_dashboard into the board instance
        board_instance = RelayBoardTab(tab_frame, board_name, board_config, self.save_config, self.delete_board, self.refresh_dashboard)
        board_instance.pack(fill="both", expand=True)
        
        self.board_tabs[board_name] = board_instance
        
        if not is_startup:
            self.refresh_dashboard()

    def delete_board(self, board_name):
        if board_name in self.board_tabs:
            self.board_tabs[board_name].disconnect()
            del self.board_tabs[board_name]
        
        if board_name in self.config_data["boards"]:
            del self.config_data["boards"][board_name]
            self.save_config()
            
        self.tabview.delete(board_name)
        
        # If no boards left, nuke the Dashboard and show the big + button
        if not self.config_data["boards"]:
            self.tabview.pack_forget()
            self.tabview.delete("Dashboard") 
            self.btn_add_first.place(relx=0.5, rely=0.45, anchor="center")
        else:
            self.refresh_dashboard()
            self.tabview.set("Dashboard") # Kick user back to the dashboard

    def create_header(self):
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=25, pady=(20, 5))
        
        title_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_frame.pack(side="left")
        
        title = ctk.CTkLabel(title_frame, text="DAMON", 
                             font=ctk.CTkFont(family="Arial", size=28, weight="bold"), text_color=THEME["text_main"])
        title.pack(anchor="w")
        
        subtitle = ctk.CTkLabel(title_frame, text="MULTI-RELAY CONTROLLER", 
                                font=ctk.CTkFont(family="Arial", size=10, weight="bold"), text_color=THEME["accent"])
        subtitle.pack(anchor="w")

        self.btn_menu = ctk.CTkButton(header_frame, text="⋮", width=40, height=40,
                                      fg_color=THEME["bg_card"], text_color=THEME["text_main"],
                                      border_width=1, border_color=THEME["border"],
                                      font=ctk.CTkFont(size=20), hover_color=THEME["accent"], corner_radius=8,
                                      command=self.toggle_menu)
        self.btn_menu.pack(side="right")

    def create_menu_items(self):
        self.create_menu_btn("Add / Setup Board", self.open_board_wizard)
        
        sep = ctk.CTkFrame(self.overlay_frame, height=2, fg_color=THEME["border"])
        sep.pack(fill="x", padx=10, pady=5)
        
        self.create_menu_btn("Exit App", self.on_close, text_color=THEME["danger"])

    def create_menu_btn(self, text, command, text_color=None):
        if text_color is None: text_color = THEME["text_main"]
        btn = ctk.CTkButton(self.overlay_frame, text=text, fg_color="transparent", 
                            text_color=text_color, hover_color=THEME["border"], 
                            anchor="w", height=35, command=lambda: [self.toggle_menu(), command()])
        btn.pack(fill="x", padx=5, pady=2)

    def toggle_menu(self):
        if self.menu_visible:
            self.overlay_frame.place_forget()
            self.menu_shadow.place_forget()
            self.menu_visible = False
        else:
            self.menu_shadow.place(relx=1.0, x=-21, y=74, anchor="ne")
            self.overlay_frame.place(relx=1.0, x=-25, y=70, anchor="ne")
            self.overlay_frame.lift()
            self.menu_visible = True

    def check_menu_close(self, event):
        if not self.menu_visible: return
        btn_x_root = self.btn_menu.winfo_rootx()
        btn_y_root = self.btn_menu.winfo_rooty()
        if (btn_x_root <= event.x_root <= btn_x_root + self.btn_menu.winfo_width() and 
            btn_y_root <= event.y_root <= btn_y_root + self.btn_menu.winfo_height()):
            return 
        menu_x_root = self.overlay_frame.winfo_rootx()
        menu_y_root = self.overlay_frame.winfo_rooty()
        if not (menu_x_root <= event.x_root <= menu_x_root + self.overlay_frame.winfo_width() and 
                menu_y_root <= event.y_root <= menu_y_root + self.overlay_frame.winfo_height()):
            self.toggle_menu()

    def refresh_dashboard(self):
        if not hasattr(self, 'scroll_dash'): return
        
        # Clear the dashboard to prevent duplicates
        for widget in self.scroll_dash.winfo_children():
            widget.destroy()
            
        # Loop through every active board
        for b_name, b_inst in self.board_tabs.items():
            # --- HEADER FRAME ---
            header_frame = ctk.CTkFrame(self.scroll_dash, fg_color="transparent")
            header_frame.pack(fill="x", pady=(15, 2), padx=5)

            # Board Name (Left)
            lbl_b = ctk.CTkLabel(header_frame, text=b_name.upper(), font=ctk.CTkFont(size=14, weight="bold"), text_color=THEME["accent"])
            lbl_b.pack(side="left")

            # --- NEW: DASHBOARD STATUS INDICATOR ---
            start_color = THEME["success"] if b_inst.is_connected else THEME["danger"]
            start_text = "● ONLINE" if b_inst.is_connected else "● OFFLINE"
            
            b_inst.dash_status_lbl = ctk.CTkLabel(header_frame, text=start_text, font=ctk.CTkFont(size=10, weight="bold"), text_color=start_color)
            b_inst.dash_status_lbl.pack(side="left", padx=10)

            # Dashboard Delete Button (Right)
            btn_del = ctk.CTkButton(header_frame, text="Delete", width=50, height=20, 
                                    fg_color="transparent", text_color=THEME["danger"], 
                                    border_width=1, border_color=THEME["danger"],
                                    hover_color="#5c1010", font=ctk.CTkFont(size=10), corner_radius=10,
                                    command=b_inst.confirm_delete) 
            btn_del.pack(side="right")
            
            try:
                qr_icon_path = os.path.join(SCRIPT_DIR, "qr_icon.png")
                # Slightly smaller size (14x14) to fit perfectly next to the text
                qr_img = ctk.CTkImage(light_image=Image.open(qr_icon_path), dark_image=Image.open(qr_icon_path), size=(14, 14))
                qr_btn_text = " Share" # Added a space so it doesn't crowd the icon
            except Exception:
                qr_img = None
                qr_btn_text = "Share" # Fallback if the image is missing

            btn_qr = ctk.CTkButton(header_frame, text=qr_btn_text, image=qr_img, width=65, height=20, 
                                    fg_color="transparent", text_color=THEME["accent"], 
                                    border_width=1, border_color=THEME["accent"],
                                    hover_color="#4d51d0", font=ctk.CTkFont(size=10), corner_radius=10,
                                    command=b_inst.show_qr_code) 
            btn_qr.pack(side="right", padx=(0, 10))

            # Create a Card to hold its relays
            card = ctk.CTkFrame(self.scroll_dash, corner_radius=10, fg_color=THEME["bg_card"], border_width=1, border_color=THEME["border"])
            card.pack(fill="x", pady=5)
            
            # Loop through the board's 4 relays
            for r_str, r_data in b_inst.relay_controls.items():
                row = ctk.CTkFrame(card, fg_color="transparent")
                row.pack(fill="x", padx=15, pady=8)
                
                r_name = b_inst.relay_names.get(r_str, f"Relay {r_str}")
                lbl_r = ctk.CTkLabel(row, text=r_name, font=ctk.CTkFont(size=13), text_color=THEME["text_main"])
                lbl_r.pack(side="left")
                
                switch = ctk.CTkSwitch(row, text="", variable=r_data['var'], onvalue="ON", offvalue="OFF",
                                       width=50, height=25, progress_color=THEME["accent"], button_hover_color="#AAAAAA",
                                       command=lambda b=b_inst, r=r_str, v=r_data['var']: b.toggle_relay(r, v))
                switch.pack(side="right")

    # --- CONFIGURATION ---
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except: pass
        return {"boards": {}}

    def save_config(self):
        with open(CONFIG_FILE, "w") as f: 
            json.dump(self.config_data, f)

    def get_com_ports(self):
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    # --- UNIFIED BOARD SETUP WIZARD ---
    def open_board_wizard(self):
        dialog = ctk.CTkToplevel(self)
        dialog.configure(fg_color=THEME["bg_main"])
        dialog.geometry("400x480")
        dialog.title("Board Setup Wizard")
        dialog.grab_set()

        # Create Tabbed Interface
        wizard_tabs = ctk.CTkTabview(dialog, fg_color="transparent", segmented_button_selected_color=THEME["accent"])
        wizard_tabs.pack(fill="both", expand=True, padx=20, pady=10)

        tab_net = wizard_tabs.add("Network Scan")
        tab_usb = wizard_tabs.add("USB Setup")

        # ==========================
        # TAB 1: NETWORK SCANNER
        # ==========================
        ctk.CTkLabel(tab_net, text="Add an existing board on your Wi-Fi\n(You can also manually type the IP below)", 
                     text_color=THEME["text_sub"], font=ctk.CTkFont(size=11)).pack(pady=(10, 15))

        entry_name_net = ctk.CTkEntry(tab_net, placeholder_text="Board Name (e.g. Garage)", fg_color=THEME["bg_card"], border_color=THEME["border"])
        entry_name_net.pack(pady=10, fill="x", ipady=5)

        combo_ip = ctk.CTkComboBox(tab_net, values=["Scanning network..."], fg_color=THEME["bg_card"], border_color=THEME["border"])
        combo_ip.pack(pady=10, fill="x", ipady=5)
        
        # Start Auto-Discovery
        zc = Zeroconf()
        def update_combo(devices):
            def safe_update():
                if combo_ip.winfo_exists(): # Safety check in case window closed quickly
                    combo_ip.configure(values=devices)
                    if devices and combo_ip.get() == "Scanning network...":
                        combo_ip.set(devices[0])
            
            self.after(0, safe_update)

        listener = DeviceListener(update_combo)
        browser = ServiceBrowser(zc, "_ws._tcp.local.", listener)

        def add_network_board():
            name = entry_name_net.get()
            ip = combo_ip.get()
            
            # Prevent empty saves
            if not name or not ip or ip == "Scanning network...": 
                return 
            
            if name not in self.config_data["boards"]:
                new_config = {"ip": ip, "names": {}}
                self.config_data["boards"][name] = new_config
                self.save_config()
                self.add_board_tab(name, new_config)
                self.tabview.set(name) # Select the newly added tab in the main window
                
                browser.cancel()
                zc.close()
                dialog.destroy()

        ctk.CTkButton(tab_net, text="Add Board", fg_color=THEME["accent"], hover_color="#4d51d0", height=40, command=add_network_board).pack(pady=20, fill="x")

        # ==========================
        # TAB 2: USB SETUP
        # ==========================
        ctk.CTkLabel(tab_usb, text="Flash Wi-Fi credentials via USB to a new board", text_color=THEME["text_sub"], font=ctk.CTkFont(size=11)).pack(pady=(5, 10))

        ports = self.get_com_ports() or ["No Ports Found"]
        combo_ports = ctk.CTkComboBox(tab_usb, values=ports, fg_color=THEME["bg_card"], border_color=THEME["border"])
        combo_ports.pack(pady=5, fill="x")

        entry_name_usb = ctk.CTkEntry(tab_usb, placeholder_text="New Board Name", fg_color=THEME["bg_card"], border_color=THEME["border"])
        entry_name_usb.pack(pady=5, fill="x")
        
        entry_ssid = ctk.CTkEntry(tab_usb, placeholder_text="Wi-Fi Name (SSID)", fg_color=THEME["bg_card"], border_color=THEME["border"])
        entry_ssid.pack(pady=5, fill="x")
        
        entry_pass = ctk.CTkEntry(tab_usb, placeholder_text="Wi-Fi Password", show="*", fg_color=THEME["bg_card"], border_color=THEME["border"])
        entry_pass.pack(pady=5, fill="x")

        lbl_status = ctk.CTkLabel(tab_usb, text="Ready to flash", text_color=THEME["text_sub"], font=ctk.CTkFont(size=11))
        lbl_status.pack(pady=(5, 5))

        def run_serial_programming():
            port, b_name, ssid, pwd = combo_ports.get(), entry_name_usb.get(), entry_ssid.get(), entry_pass.get()
            if port == "No Ports Found" or not ssid or not b_name:
                lbl_status.configure(text="Error: Check inputs", text_color=THEME["danger"])
                return

            lbl_status.configure(text="Connecting...", text_color="orange")
            
            def process():
                try:
                    ser = serial.Serial(port, 115200, timeout=3)
                    time.sleep(2)
                    self.after(0, lambda: lbl_status.configure(text="Sending Credentials..."))
                    ser.write(f"\nSETUP\n{ssid}\n{pwd}\n".encode())
                    self.after(0, lambda: lbl_status.configure(text="Waiting for Hostname..."))
                    ser.timeout = 20 
                    found_host = None
                    start = time.time()
                    
                    while time.time() - start < 20:
                        try:
                            line = ser.readline().decode().strip()
                            if line.startswith("HOSTNAME_IS:"):
                                found_host = line.split(":")[1]
                                break
                        except: pass
                    ser.close()

                    if found_host:
                        new_ip = f"{found_host}.local"
                        self.after(0, lambda: [
                            lbl_status.configure(text="Success!", text_color=THEME["success"]),
                            self.config_data["boards"].setdefault(b_name, {"ip": new_ip, "names": {}}),
                            self.save_config(),
                            self.add_board_tab(b_name, self.config_data["boards"][b_name]),
                            self.tabview.set(b_name),
                            zc.close(),        # Clean up scanner
                            dialog.destroy()   # Close dialog
                        ])
                    else:
                        self.after(0, lambda: lbl_status.configure(text="Error: No response", text_color=THEME["danger"]))
                except Exception as e:
                    self.after(0, lambda: lbl_status.configure(text="Serial Failed", text_color=THEME["danger"]))

            threading.Thread(target=process, daemon=True).start()

        ctk.CTkButton(tab_usb, text="Configure Device", fg_color=THEME["accent"], hover_color="#4d51d0", height=40, command=run_serial_programming).pack(pady=(0, 10), fill="x")

        # ==========================
        # CLEANUP ON CLOSE
        # ==========================
        def on_dialog_close():
            browser.cancel()
            zc.close()
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)

    def on_close(self):
        for board in self.board_tabs.values():
            board.disconnect()
        self.destroy()

# --- NETWORK SCANNER ---
class DeviceListener:
    def __init__(self, update_callback):
        self.update_callback = update_callback
        self.devices = []

    def remove_service(self, zeroconf, type, name):
        pass

    def add_service(self, zeroconf, type, name):
        # Cleans up "ESP-1A2B3C._ws._tcp.local." into "ESP-1A2B3C.local"
        clean_name = name.replace("._ws._tcp.local.", ".local")
        if clean_name not in self.devices:
            self.devices.append(clean_name)
            self.update_callback(self.devices)
            
    def update_service(self, zeroconf, type, name):
        pass

if __name__ == "__main__":
    app = RelayApp()
    app.mainloop()