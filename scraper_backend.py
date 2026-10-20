import os
import platform
import time
from playwright.sync_api import sync_playwright, TimeoutError
import threading
os.makedirs("processed", exist_ok=True)
os.makedirs("scraped_groups", exist_ok=True)
class WhatsAppScraper:
    def __init__(self, log_callback=None):
        self.playwright = None
        self.browser = None
        self.page = None
        self.stop_event = threading.Event()
        self.log_callback = log_callback
        self.user_data_dir = os.path.join(os.getcwd(), 'whatsapp_profile')

    def log(self, message):
        if self.log_callback:
            self.log_callback(message)
        print(message)

    def setup_browser(self):
        """Initializes the browser with a persistent context."""
        try:
            self.log("Initializing Playwright...")
            self.playwright = sync_playwright().start()
            
            # Browser Setup
            real_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            options = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-zygote",
                "--disable-gpu",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding"
            ]

            self.log("Launching Browser...")
            self.browser = self.playwright.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                headless=False, # Must be False for headful debugging if needed, but we can try True if user wants background. User said "browser specefic size to avoid bot issues", implies visible.
                user_agent=real_user_agent,
                viewport={"width": 1280, "height": 720},
                args=options,
                slow_mo=50
            )
            
            self.page = self.browser.pages[0]
            self.page.goto("https://web.whatsapp.com/")
            self.log("Navigated to WhatsApp Web.")
            return True
        except Exception as e:
            self.log(f"Error setting up browser: {e}")
            return False

    def check_login(self, qr_callback):
        """
        Checks if the user is logged in.
        If not, screenshots the QR code and calls qr_callback with the path.
        Returns True if logged in, False otherwise.
        """
        try:
            self.log("Checking Login Status...")
            # Check for chat list (logged in)
            try:
                self.page.wait_for_selector("#pane-side", state="visible", timeout=15000)
                self.log("✅ Already Logged In!")
                return True
            except TimeoutError:
                pass
            try:
                self.log("Main Page not found now looking for Sync Chats")
                self.page.wait_for_selector('canvas[aria-label="Loading Chats"]',timeout=15000)
                self.log("Chats are loading so system is sleeping for 5 minutes")
                time.sleep(300)
            except TimeoutError:
                pass

            self.log("❌ Not logged in. Looking for QR Code...")
            # Check for QR code
            try:
                qr_canvas = self.page.wait_for_selector('canvas[aria-label="Scan this QR code to link a device!"]', timeout=15000)
                if qr_canvas:
                    qr_path = os.path.join(os.getcwd(), "whatsapp_qr.png")
                    self.page.screenshot(path=qr_path)
                    self.log(f"📸 QR Code saved to {qr_path}")
                    if qr_callback:
                        qr_callback(qr_path)
                    
                    # Wait for login
                    self.log("Waiting for user to scan QR code...")
                    self.page.wait_for_selector("#pane-side", timeout=0) # Wait forever until logged in
                    self.log("✅ Login Successful!")
                    return True
            except Exception as e:
                self.log(f"Error finding QR code: {e}")
                return False

        except Exception as e:
            self.log(f"Error during login check: {e}")
            return False
        return False

    def open_group(self, group_name):
        """Searches for a group and opens it."""
        try:
            self.log(f"Searching for group: {group_name}")
            
            # Search Box - Updated based on user provided HTML
            # HTML: <div ... contenteditable="true" ... data-tab="3" ...>
            search_box = self.page.locator("div[contenteditable='true'][data-tab='3']")
            
            if not search_box.is_visible():
               self.log("Search box (data-tab=3) not found, trying fallback...")
               search_box = self.page.get_by_title("Search input textbox")

            search_box.click()
            search_box.fill(group_name)
            time.sleep(2) # Wait for results
            search_box.press("Enter")
            
            # Wait for header to confirm chat is open
            try:
                self.page.wait_for_selector("#main header", timeout=10000)
                self.log(f"Opened group: {group_name}")
                return True
            except TimeoutError:
                self.log(f"Could not open group '{group_name}'. Is the name correct?")
                return False

        except Exception as e:
            self.log(f"Error opening group: {e}")
            return False

    def scrape_members(self):
        """
        Generator that yields scraped members using JS-based scrolling.
        """
        try:
            self.log("Scraping members...")
            
            # Click Group Info (Header) to open sidebar
            header = self.page.locator("#main header")
            header.click()
            time.sleep(3) 

            # Check for "View all"
            view_all_btn = self.page.get_by_text("View all", exact=False).first
            is_modal = False
            
            try:
                if view_all_btn.is_visible(timeout=3000):
                    self.log("Clicking 'View all'...")
                    view_all_btn.click()
                    is_modal = True
                    time.sleep(2)
                else:
                    self.log("Scraping from sidebar.")
            except:
                 pass

            extracted_data = set()
            no_change_count = 0
            last_count = 0
            
            # Scroll Script to find the largest scrollable div and scroll it
            scroll_script = """
                (wiggle = false) => {
                    // Find largest scrollable div
                    const divs = Array.from(document.querySelectorAll('div'));
                    let largestDiv = null;
                    let maxScroll = 0;
                    
                    divs.forEach(div => {
                        if (div.scrollHeight > div.clientHeight && div.scrollHeight > maxScroll) {
                            maxScroll = div.scrollHeight;
                            largestDiv = div;
                        }
                    });

                    if (largestDiv) {
                        if (wiggle) {
                            largestDiv.scrollTop -= 200;
                            setTimeout(() => { largestDiv.scrollTop += 600; }, 200);
                        } else {
                            largestDiv.scrollTop += 500;
                        }
                        return true;
                    }
                    return false;
                }
            """

            self.log("Starting JS-based scraping loop...")
            
            while True:
                if self.stop_event.is_set():
                    break
                
                # 1. Scrape Current View
                spans = self.page.locator("span._ao3e").all()
                for span in spans:
                    try:
                        txt = span.inner_text().strip()
                        # Strict Filter Logic
                        if "+" in txt and any(c.isdigit() for c in txt) and "," not in txt:
                            if len(txt) < 25 and len(txt) > 8:
                                if txt not in extracted_data:
                                    extracted_data.add(txt)
                                    yield txt 
                    except:
                        pass
                
                # 2. Check Progress
                current_count = len(extracted_data)
                if current_count == last_count:
                    no_change_count += 1
                else:
                    no_change_count = 0
                    last_count = current_count
                
                # 3. Scroll
                wiggle = False
                if no_change_count > 5:
                    self.log(f"Stuck ({no_change_count}). Wiggling...")
                    wiggle = True
                
                # Execute Scroll
                scrolled = self.page.evaluate(scroll_script, wiggle)
                
                if not scrolled:
                     # Fallback to mouse if no div found (rare)
                     self.page.mouse.wheel(0, 1000)
                
                time.sleep(1.0 if not wiggle else 2.0)
                
                # Stop Conditions
                if no_change_count > 5: # No new data for 15 cycles
                    self.log("No new members found. Stopping.")
                    break
                    
                if len(extracted_data) > 20000:
                    break

        except Exception as e:
            self.log(f"Error scraping members: {e}")

    def add_members_to_group(self, group_name, phone_numbers):
        import random
        """
        Adds members in batches.
        Uses the exact 'Green Check' selector provided.
        """

        

        
        BATCH_SIZE = 15
        
        try:
            self.log(f"Starting Add Workflow for {group_name} ({len(phone_numbers)} numbers)...")
            
            # 1. Open Group & Info
            if not self.open_group(group_name):
                return
            
            # Click Header to open Group Info
            self.page.locator("#main header").click()
            time.sleep(2)
            
            # 2. Process in Batches
            chunks = [phone_numbers[i:i + BATCH_SIZE] for i in range(0, len(phone_numbers), BATCH_SIZE)]
            
            for batch_idx, batch in enumerate(chunks):
                if self.stop_event.is_set(): break
                
                self.log(f"Processing Batch {batch_idx + 1}/{len(chunks)}...")
                
                # --- A. OPEN MODAL ---
                try:
                    # Click Add Icon
                    add_btn = self.page.locator("span[data-icon='person-add']")
                    if add_btn.is_visible():
                        add_btn.click()
                    else:
                        self.page.get_by_text("Add member", exact=False).first.click()
                    
                    # Wait for Search Box
                    modal_input = self.page.locator("div[role='dialog'] div[contenteditable='true'][role='textbox']")
                    modal_input.wait_for(state="visible", timeout=5000)
                    
                except Exception as e:
                    self.log(f"❌ Failed to open Add Modal: {e}")
                    continue 

                # --- B. ADD NUMBERS ---
                added_count = 0
                
                for phone in batch:
                    try:
                        # Clear & Type
                        modal_input.click()
                        modal_input.fill(phone)
                        
                        # Wait for Result Container (_ak8l) & Click
                        try:
                            result_row = self.page.locator("div._ak8l").first
                            result_row.wait_for(state="visible", timeout=2000)
                            time.sleep(1)
                            self.page.keyboard.press("Enter")
                            added_count += 1
                            time.sleep(1) 
                            
                        except TimeoutError:
                            self.log(f"Number not found/Loading stuck: {phone}")
                            modal_input.fill("") # Clear input
                            
                    except Exception as e:
                        print(f"Skipping {phone}: {e}")

                # --- C. CONFIRM BATCH ---
                if added_count > 0:
                    if added_count % 4 == 0:
                        self.log("Sleeping For 10s...")
                        time.sleep(10)


                    try:
                        # 1. CLICK GREEN CHECK (Using your provided HTML)
                        # We target the div that has the role='button' AND contains the check icon
                        green_check = self.page.locator("div[role='button']").filter(has=self.page.locator("span[data-icon='web-ic-check']"))
                        green_check.click()
                        
                        # 2. Final "Add member" Popup
                        time.sleep(3)
                        confirm_popup = self.page.locator("button").filter(has_text="Add member").last
                        
                        if confirm_popup.is_visible():
                            confirm_popup.click()
                            self.log(f"✅ Batch {batch_idx + 1} added.")
                            with open('processed/numbers.txt', 'a') as f:
                                f.write('\n'.join(batch) + '\n')
                            time.sleep(2)
                        else:
                            # Handle "Invite" case if privacy prevents adding
                            invite_btn = self.page.locator("div[role='button']").filter(has_text="Invite to group").last
                            if invite_btn.is_visible():
                                self.log("Privacy restricted. Skipping invite.")
                                self.page.keyboard.press("Escape")
                        
                        time.sleep(2.5) # Sync wait
                        
                    except Exception as e:
                        self.log(f"Error confirming batch: {e}")
                else:
                    self.page.keyboard.press("Escape")
                    time.sleep(1)

            self.log("✅ All batches processed.")

        except Exception as e:
            self.log(f"Critical Error: {e}")

    def scan_main_page_chats(self):
        """
        Scans the main chat list for phone numbers.
        Ignores contacts with names.
        """
        try:
            self.log("Starting Main Page Scan...")
            
            # Ensure we are on main page
            try:
                self.page.wait_for_selector("#pane-side", timeout=5000)
            except:
                self.log("Not on main page. Navigating...")
                self.page.goto("https://web.whatsapp.com/")
                self.page.wait_for_selector("#pane-side", timeout=30000)

            # Sidebar container
            pane_side = self.page.locator("#pane-side")
            
            extracted_numbers = set()
            no_change_count = 0
            last_count = 0
            
            # Scroll Script for the sidebar
            scroll_script = """
                (wiggle = false) => {
                    const pane = document.querySelector('#pane-side');
                    if (!pane) return false;
                    
                    if (wiggle) {
                        pane.scrollTop -= 200;
                        setTimeout(() => { pane.scrollTop += 600; }, 200);
                    } else {
                        pane.scrollTop += 500;
                    }
                    return true;
                }
            """
            
            self.log("Scanning chat list...")
            
            while True:
                if self.stop_event.is_set():
                    break
                
                # 1. Scrape visible chat titles
                # The user provided HTML suggests titles are in spans with class _ao3e or title attribute
                # We'll use a broad selector for the chat row and refine
                
                # We simply grab all heavy text elements in #pane-side
                elements = pane_side.locator("span[dir='auto']").all() # Common for titles
                
                found_in_pass = 0
                for el in elements:
                    try:
                        text = el.inner_text().strip()
                        # Strict Phone Number Filter
                        # Must contain digits, maybe +, no letters (except maybe 'You')
                        if len(text) > 8 and len(text) < 20 and any(c.isdigit() for c in text):
                            # Check if it has letters (excluding common formatting)
                            # If it has letters, it's likely a Name
                            if not any(c.isalpha() for c in text): 
                                clean_num = text.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                                if clean_num not in extracted_numbers:
                                    extracted_numbers.add(clean_num)
                                    yield text # Yield original formatted text
                                    found_in_pass += 1
                    except:
                        pass
                        
                # 2. Check Progress
                current_count = len(extracted_numbers)
                if current_count == last_count:
                    no_change_count += 1
                else:
                    no_change_count = 0
                    last_count = current_count
                    if current_count % 10 == 0:
                        self.log(f"Found {current_count} numbers so far...")
                
                # 3. Scroll
                wiggle = False
                if no_change_count > 3:
                    wiggle = True
                    self.log("Wiggling to trigger load...")
                    
                scrolled = self.page.evaluate(scroll_script, wiggle)
                time.sleep(1.5 if not wiggle else 2.5)
                
                # Stop Conditions
                if no_change_count > 8: # Stop after ~10-15 seconds of no new numbers
                    self.log("No new numbers found in chat list. Stopping.")
                    break
                    
        except Exception as e:
            self.log(f"Error scanning main page: {e}")

    def send_bulk_messages(self, numbers, message, media_path=None):
        """
        Sends messages to a list of numbers.
        Handles Invalid Numbers, Media uploads, and Random Delays.
        """
        import random
        from urllib.parse import quote

        success_count = 0
        failed_count = 0
        
        try:
            self.log(f"Starting Bulk Sender for {len(numbers)} numbers...")
            
            for index, phone in enumerate(numbers):
                if self.stop_event.is_set():
                    break
                
                self.log(f"[{index+1}/{len(numbers)}] Processing {phone}...")
                
                try:
                    # 1. Navigate to Direct Chat
                    # Using clean phone number
                    clean_phone = phone.replace(" ", "").replace("+", "").replace("-", "")
                    
                    # Encode message if no media (if media, we send as caption)
                    encoded_msg = quote(message) if message and not media_path else ""
                    
                    url = f"https://web.whatsapp.com/send?phone={clean_phone}"
                    if encoded_msg:
                        url += f"&text={encoded_msg}"
                        
                    self.page.goto(url)
                    
                    # 2. Wait for Load (Chat input OR Invalid Number popup)
                    try:
                        # Wait for either main chat input OR "Phone number shared via url is invalid" popup
                        # We wait for sidebar to exist as a baseline, then check specific states
                        self.page.wait_for_selector("#main", timeout=20000)
                    except TimeoutError:
                        # Check for Invalid Number Dialog
                        if self.page.locator("div[role='button']").filter(has_text="OK").is_visible():
                            self.log(f"❌ Invalid Number: {phone}")
                            self.page.locator("div[role='button']").filter(has_text="OK").click()
                            failed_count += 1
                            continue
                        else:
                            self.log(f"❌ Timeout loading chat: {phone}")
                            failed_count += 1
                            continue
                    
                    time.sleep(2) # Stabilize
                    
                    # 3. Handle Media (if exists)
                    if media_path and os.path.exists(media_path):
                        try:
                            # Click Plus/Attach Icon
                            # It's usually a plus icon or paperclip
                            attach_btn = self.page.locator("span[data-icon='plus'], span[data-icon='clip']").first
                            attach_btn.click()
                            time.sleep(1)
                            
                            # Input File (Hidden input)
                            # We need to find the input[type='file'] and set input
                            input_node = self.page.locator("input[type='file']").first
                            input_node.set_input_files(media_path)
                            
                            # Wait for Caption Screen
                            # Look for the caption input
                            self.page.wait_for_selector("div[contenteditable='true'][aria-label='Caption']", timeout=15000)
                            
                            # If message exists, type it as caption
                            if message:
                                caption_box = self.page.locator("div[contenteditable='true'][aria-label='Caption']")
                                caption_box.fill(message)
                                time.sleep(1)
                                
                            # Click Send (Green circle with arrow)
                            send_btn = self.page.locator("span[data-icon='send']")
                            send_btn.click()
                            self.log("Media sent.")
                            time.sleep(2) # Wait flight
                            
                        except Exception as e:
                            self.log(f"Error sending media: {e}")
                            failed_count += 1
                            continue

                    # 4. Handle Text Only (if not sent via URL param)
                    # If we used the URL param & text=..., it is pre-filled. We just need to hit enter.
                    # BUT, sometimes it doesn't auto-send.
                    elif message:
                        # Check if text field has content
                        input_box = self.page.locator("#main div[contenteditable='true'][role='textbox']")
                        
                        # Sometimes URL param fills it, sometimes we need to hit enter
                        # We just press Enter to be sure
                        input_box.focus()
                        time.sleep(0.5)
                        self.page.keyboard.press("Enter")
                        self.log("Text message sent.")

                    success_count += 1

                    # 5. RANDOM HUMAN DELAY
                    delay = random.randint(7, 15)
                    self.log(f"Sleeping for {delay}s...")
                    time.sleep(delay)

                except Exception as e:
                    self.log(f"Error processing {phone}: {e}")
                    failed_count += 1

            self.log(f"✅ Bulk Send Complete. Success: {success_count}, Failed: {failed_count}")

        except Exception as e:
            self.log(f"Critical Error in Bulk Sender: {e}")
        """
        Scans the main chat list for phone numbers.
        Ignores contacts with names.
        """
        try:
            self.log("Starting Main Page Scan...")
            
            # Ensure we are on main page
            try:
                self.page.wait_for_selector("#pane-side", timeout=5000)
            except:
                self.log("Not on main page. Navigating...")
                self.page.goto("https://web.whatsapp.com/")
                self.page.wait_for_selector("#pane-side", timeout=30000)

            # Sidebar container
            pane_side = self.page.locator("#pane-side")
            
            extracted_numbers = set()
            no_change_count = 0
            last_count = 0
            
            # Scroll Script for the sidebar
            scroll_script = """
                (wiggle = false) => {
                    const pane = document.querySelector('#pane-side');
                    if (!pane) return false;
                    
                    if (wiggle) {
                        pane.scrollTop -= 200;
                        setTimeout(() => { pane.scrollTop += 600; }, 200);
                    } else {
                        pane.scrollTop += 500;
                    }
                    return true;
                }
            """
            
            self.log("Scanning chat list...")
            
            while True:
                if self.stop_event.is_set():
                    break
                
                # 1. Scrape visible chat titles
                # The user provided HTML suggests titles are in spans with class _ao3e or title attribute
                # We'll use a broad selector for the chat row and refine
                
                # Find all chat rows (usually Role=gridcell or listitem)
                # But simpler is to find all text elements that look like numbers in the sidebar
                
                # We simply grab all heavy text elements in #pane-side
                elements = pane_side.locator("span[dir='auto']").all() # Common for titles
                
                found_in_pass = 0
                for el in elements:
                    try:
                        text = el.inner_text().strip()
                        # Strict Phone Number Filter
                        # Must contain digits, maybe +, no letters (except maybe 'You')
                        if len(text) > 8 and len(text) < 20 and any(c.isdigit() for c in text):
                            # Check if it has letters (excluding common formatting)
                            # If it has letters, it's likely a Name
                            if not any(c.isalpha() for c in text): 
                                clean_num = text.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                                if clean_num not in extracted_numbers:
                                    extracted_numbers.add(clean_num)
                                    yield text # Yield original formatted text
                                    found_in_pass += 1
                    except:
                        pass
                        
                # 2. Check Progress
                current_count = len(extracted_numbers)
                if current_count == last_count:
                    no_change_count += 1
                else:
                    no_change_count = 0
                    last_count = current_count
                    self.log(f"Found {current_count} numbers so far...")
                
                # 3. Scroll
                wiggle = False
                if no_change_count > 3:
                    wiggle = True
                    self.log("Wiggling to trigger load...")
                    
                scrolled = self.page.evaluate(scroll_script, wiggle)
                time.sleep(1.5 if not wiggle else 2.5)
                
                # Stop Conditions
                if no_change_count > 8: # Stop after ~10-15 seconds of no new numbers
                    self.log("No new numbers found in chat list. Stopping.")
                    break
                    
        except Exception as e:
            self.log(f"Error scanning main page: {e}")

    def send_bulk_messages(self, numbers, message, media_path=None):
        """
        Sends messages to a list of numbers.
        Handles Invalid Numbers, Media uploads, and Random Delays.
        """
        import random
        from urllib.parse import quote

        success_count = 0
        failed_count = 0
        
        try:
            self.log(f"Starting Bulk Sender for {len(numbers)} numbers...")
            
            for index, phone in enumerate(numbers):
                if self.stop_event.is_set():
                    break
                
                self.log(f"[{index+1}/{len(numbers)}] Processing {phone}...")
                
                try:
                    # 1. Navigate to Direct Chat
                    # Using clean phone number
                    clean_phone = phone.replace(" ", "").replace("+", "").replace("-", "")
                    
                    # Encode message if no media (if media, we send as caption)
                    encoded_msg = quote(message) if message and not media_path else ""
                    
                    url = f"https://web.whatsapp.com/send?phone={clean_phone}"
                    if encoded_msg:
                        url += f"&text={encoded_msg}"
                        
                    self.page.goto(url)
                    
                    # 2. Wait for Load (Chat input OR Invalid Number popup)
                    try:
                        # Wait for either main chat input OR "Phone number shared via url is invalid" popup
                        # We wait for sidebar to exist as a baseline, then check specific states
                        self.page.wait_for_selector("#main", timeout=20000)
                    except TimeoutError:
                        # Check for Invalid Number Dialog
                        if self.page.locator("div[role='button']").filter(has_text="OK").is_visible():
                            self.log(f"❌ Invalid Number: {phone}")
                            self.page.locator("div[role='button']").filter(has_text="OK").click()
                            failed_count += 1
                            continue
                        else:
                            self.log(f"❌ Timeout loading chat: {phone}")
                            failed_count += 1
                            continue
                    
                    time.sleep(2) # Stabilize
                    
                    # 3. Handle Media (if exists)
                    if media_path and os.path.exists(media_path):
                        try:
                            # Click Plus/Attach Icon
                            # It's usually a plus icon or paperclip
                            attach_btn = self.page.locator("span[data-icon='plus'], span[data-icon='clip']").first
                            attach_btn.click()
                            time.sleep(1)
                            
                            # Input File (Hidden input)
                            # We need to find the input[type='file'] and set input
                            input_node = self.page.locator("input[type='file']").first
                            input_node.set_input_files(media_path)
                            
                            # Wait for Caption Screen
                            # Look for the caption input
                            self.page.wait_for_selector("div[contenteditable='true'][aria-label='Caption']", timeout=15000)
                            
                            # If message exists, type it as caption
                            if message:
                                caption_box = self.page.locator("div[contenteditable='true'][aria-label='Caption']")
                                caption_box.fill(message)
                                time.sleep(1)
                                
                            # Click Send (Green circle with arrow)
                            send_btn = self.page.locator("span[data-icon='send']")
                            send_btn.click()
                            self.log("Media sent.")
                            time.sleep(2) # Wait flight
                            
                        except Exception as e:
                            self.log(f"Error sending media: {e}")
                            failed_count += 1
                            continue

                    # 4. Handle Text Only (if not sent via URL param)
                    # If we used the URL param & text=..., it is pre-filled. We just need to hit enter.
                    # BUT, sometimes it doesn't auto-send.
                    elif message:
                        # Check if text field has content
                        input_box = self.page.locator("#main div[contenteditable='true'][role='textbox']")
                        
                        # Sometimes URL param fills it, sometimes we need to hit enter
                        # We just press Enter to be sure
                        input_box.focus()
                        time.sleep(0.5)
                        self.page.keyboard.press("Enter")
                        self.log("Text message sent.")

                    success_count += 1

                    # 5. RANDOM HUMAN DELAY
                    delay = random.randint(7, 15)
                    self.log(f"Sleeping for {delay}s...")
                    time.sleep(delay)

                except Exception as e:
                    self.log(f"Error processing {phone}: {e}")
                    failed_count += 1

            self.log(f"✅ Bulk Send Complete. Success: {success_count}, Failed: {failed_count}")

        except Exception as e:
            self.log(f"Critical Error in Bulk Sender: {e}")