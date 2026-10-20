import customtkinter as ctk
import threading
import queue
from PIL import Image
import os
import time
from scraper_backend import WhatsAppScraper

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("WhatsApp Toolkit by Hive Mind")
        self.geometry("1000x700")

        # Layout configuration
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.setup_sidebar()

        # Tabs
        self.tabview = ctk.CTkTabview(self, width=750)
        self.tabview.grid(row=0, column=1, rowspan=4, sticky="nsew", padx=20, pady=20)
        
        self.tab_group_scrape = self.tabview.add("Group Scraper")
        self.tab_adder = self.tabview.add("Group Adder")
        self.tab_home_scan = self.tabview.add("Home Scanner")
        self.tab_sender = self.tabview.add("Bulk Sender")
        
        # Init Tabs
        self.init_group_scraper_tab()
        self.init_group_adder_tab()
        self.init_home_scanner_tab()
        self.init_bulk_sender_tab()

        # Backend Setup
        self.scraper = WhatsAppScraper(log_callback=self.log_message)
        self.queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._backend_worker, daemon=True)
        self.worker_thread.start()
        
        # Ensure directories exist
        os.makedirs("scraped_numbers", exist_ok=True)
        os.makedirs("processed", exist_ok=True)

    def setup_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(5, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="WhatsApp\nToolkit", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.connect_btn = ctk.CTkButton(self.sidebar_frame, text="Connect WhatsApp", command=self.on_connect_click, fg_color="#128C7E", hover_color="#075E54")
        self.connect_btn.grid(row=1, column=0, padx=20, pady=10)
        
        self.stop_btn = ctk.CTkButton(self.sidebar_frame, text="STOP TASK", fg_color="#D32F2F", hover_color="#B71C1C", command=self.on_stop_click)
        self.stop_btn.grid(row=2, column=0, padx=20, pady=10)

        # Status Label
        self.status_label = ctk.CTkLabel(self.sidebar_frame, text="Status: Idle", text_color="gray")
        self.status_label.grid(row=3, column=0, padx=20, pady=10)

        # QR Code
        self.qr_label = ctk.CTkLabel(self.sidebar_frame, text="")
        self.qr_label.grid(row=4, column=0, padx=20, pady=20)

    # --- TAB 1: GROUP SCRAPER ---
    def init_group_scraper_tab(self):
        tab = self.tab_group_scrape
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(tab, text="Scrape Members from a Specific Group", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        
        self.scrape_grp_entry = ctk.CTkEntry(tab, placeholder_text="Enter Exact Group Name", height=40)
        self.scrape_grp_entry.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        self.start_scrape_btn = ctk.CTkButton(tab, text="Start Scraping", command=self.on_scrape_click, height=40)
        self.start_scrape_btn.grid(row=2, column=0, padx=10, pady=10)
        
        self.log_scrape = ctk.CTkTextbox(tab, height=300)
        self.log_scrape.grid(row=3, column=0, padx=10, pady=10, sticky="nsew")
        self.log_scrape.configure(state="disabled")

    # --- TAB 2: GROUP ADDER ---
    def init_group_adder_tab(self):
        tab = self.tab_adder
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(tab, text="Add Members to Group in Batches", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        
        self.add_grp_entry = ctk.CTkEntry(tab, placeholder_text="Enter Target Group Name", height=40)
        self.add_grp_entry.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(tab, text="Paste Numbers (Line by line):").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        
        self.nums_textbox = ctk.CTkTextbox(tab, height=150)
        self.nums_textbox.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        
        self.start_add_btn = ctk.CTkButton(tab, text="Start Adding Members", command=self.on_add_click, height=40, fg_color="#128C7E", hover_color="#075E54")
        self.start_add_btn.grid(row=4, column=0, padx=10, pady=20, sticky="n")

    # --- TAB 3: HOME SCANNER ---
    def init_home_scanner_tab(self):
        tab = self.tab_home_scan
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(tab, text="Scan Main Chat List for Numbers", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        
        self.start_home_scan_btn = ctk.CTkButton(tab, text="Start Main Page Scan", command=self.on_home_scan_click, height=50, font=ctk.CTkFont(size=14, weight="bold"))
        self.start_home_scan_btn.grid(row=1, column=0, padx=10, pady=20)
        
        self.log_home_scan = ctk.CTkTextbox(tab, height=400)
        self.log_home_scan.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
        self.log_home_scan.configure(state="disabled")

    # --- TAB 4: BULK SENDER ---
    def init_bulk_sender_tab(self):
        tab = self.tab_sender
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(5, weight=1) # Log area

        ctk.CTkLabel(tab, text="Bulk Message Sender", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        # 1. Numbers
        self.sender_nums_text = ctk.CTkTextbox(tab, height=100)
        self.sender_nums_text.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        self.sender_nums_text.insert("0.0", "Paste numbers here (one per line)...")
        
        # 2. Message
        self.sender_msg_text = ctk.CTkTextbox(tab, height=80)
        self.sender_msg_text.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        self.sender_msg_text.insert("0.0", "Type your message here...")

        # 3. Media Select
        self.media_path = None
        self.media_btn = ctk.CTkButton(tab, text="Select Image/Video (Optional)", command=self.select_media)
        self.media_btn.grid(row=3, column=0, padx=10, pady=10)
        
        self.media_lbl = ctk.CTkLabel(tab, text="No file selected", text_color="gray")
        self.media_lbl.grid(row=4, column=0, padx=10, pady=0)

        # 4. Start
        self.start_send_btn = ctk.CTkButton(tab, text="START BULK SEND", command=self.on_bulk_send_click, height=40, fg_color="#128C7E", hover_color="#075E54", font=ctk.CTkFont(weight="bold"))
        self.start_send_btn.grid(row=5, column=0, padx=10, pady=20)

    # --- ACTION HANDLERS ---
    def log_message(self, message):
        timestamp = time.strftime("%H:%M:%S")
        full_msg = f"[{timestamp}] {message}\n"
        print(full_msg.strip())

        def _update():
            # Update all logs
            for log_widget in [self.log_scrape, self.log_home_scan]:
                try:
                    log_widget.configure(state="normal")
                    log_widget.insert("end", full_msg)
                    log_widget.see("end")
                    log_widget.configure(state="disabled")
                except: pass
        self.after(0, _update)

    def show_qr(self, qr_path):
        self.after(0, self._update_qr_ui, qr_path)

    def _update_qr_ui(self, qr_path):
        try:
            pil_image = Image.open(qr_path)
            pil_image = pil_image.resize((180, 180), Image.Resampling.LANCZOS)
            self.qr_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(180, 180))
            self.qr_label.configure(image=self.qr_image, text="") 
            self.log_message("Please scan the QR code.")
        except Exception as e:
            self.log_message(f"QR Error: {e}")

    def select_media(self):
        path = ctk.filedialog.askopenfilename(filetypes=[("Media", "*.jpg;*.jpeg;*.png;*.mp4;*.avi")])
        if path:
            self.media_path = path
            self.media_lbl.configure(text=os.path.basename(path), text_color="green")
            self.log_message(f"Media selected: {os.path.basename(path)}")

    def on_connect_click(self):
        self.queue.put(("CONNECT", None))
        self.status_label.configure(text="Status: Connecting...")

    def on_scrape_click(self):
        name = self.scrape_grp_entry.get()
        if not name: return
        self.queue.put(("SCRAPE_GROUP", name))
        self.status_label.configure(text=f"Status: Scraping {name}")

    def on_add_click(self):
        name = self.add_grp_entry.get()
        nums = self.nums_textbox.get("1.0", "end").strip().split('\n')
        nums = [n.strip() for n in nums if n.strip()]
        if not name or not nums: return
        self.queue.put(("ADD_MEMBERS", (name, nums)))
        self.status_label.configure(text="Status: Adding members...")

    def on_home_scan_click(self):
        self.queue.put(("SCAN_HOME", None))
        self.status_label.configure(text="Status: Scanning Home...")

    def on_bulk_send_click(self):
        nums = self.sender_nums_text.get("1.0", "end").strip().split('\n')
        nums = [n.strip() for n in nums if n.strip() and "Paste numbers" not in n]
        
        msg = self.sender_msg_text.get("1.0", "end").strip()
        if "Type your message" in msg: msg = ""
        
        if not nums:
            self.log_message("No numbers provided!")
            return
            
        self.queue.put(("BULK_SEND", (nums, msg, self.media_path)))
        self.status_label.configure(text="Status: Sending Bulk Messages...")

    def on_stop_click(self):
        self.scraper.stop_event.set()
        self.log_message("STOP signal sent.")
        self.status_label.configure(text="Status: Stopping...")

    def on_closing(self):
        self.scraper.stop_event.set()
        self.queue.put(("STOP", None))
        self.destroy()

    # --- WORKER ---
    def _backend_worker(self):
        while True:
            try:
                task, data = self.queue.get()
                if task == "STOP":
                    self.scraper.close()
                    break

                elif task == "CONNECT":
                    if self.scraper.setup_browser():
                        if self.scraper.check_login(self.show_qr):
                            self.after(0, lambda: self.qr_label.configure(image=None, text="Logged In"))
                            self.log_message("Login Successful!")
                
                elif task == "SCRAPE_GROUP":
                    self.scraper.stop_event.clear()
                    group_name = data
                    if self.scraper.open_group(group_name):
                        # Simple scraping loop integration
                        folder = "scraped_groups"
                        filename = f"{folder}/{group_name}_{int(time.time())}.txt"
                        res = []
                        for member in self.scraper.scrape_members():
                            res.append(member)
                            if self.scraper.stop_event.is_set(): break
                        
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write('\n'.join(res))
                        self.log_message(f"Saved {len(res)} members to {filename}")

                elif task == "ADD_MEMBERS":
                    self.scraper.stop_event.clear()
                    grp, nums = data
                    self.scraper.add_members_to_group(grp, nums)

                elif task == "SCAN_HOME":
                    self.scraper.stop_event.clear()
                    # Same pattern: iterate and save
                    folder = "processed"
                    filename = f"{folder}/home_scan_{int(time.time())}.txt"
                    res = []
                    for num in self.scraper.scan_main_page_chats():
                        res.append(num)
                        if self.scraper.stop_event.is_set(): break
                    
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(res))
                    self.log_message(f"Scanned {len(res)} numbers. Saved to {filename}")

                elif task == "BULK_SEND":
                    self.scraper.stop_event.clear()
                    nums, msg, media = data
                    self.scraper.send_bulk_messages(nums, msg, media)

                self.queue.task_done()
            except Exception as e:
                self.log_message(f"Worker Error: {e}")

if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
