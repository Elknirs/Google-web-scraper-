# IMPORTANT DISCLAIMER:
# Scraping Google Maps is against Google's Terms of Service and may result in IP bans or legal issues.
# Consider using the official Google Places API instead, which requires an API key.
# This code is provided for educational purposes only. Use at your own risk.
#
# Features (2025 Optimized):
# - Uses async Playwright for efficient Google Maps scraping.
# - Crawls websites for emails, addresses, phones, and social media links.
# - Tkinter GUI with fields for search query, max results (1-200), crawl depth, max pages.
# - Progress bar for visual feedback (Maps: 50%, websites: 50%).
# - Non-headless mode and robots.txt checking options.
# - Save/load config.
# - Fixed syntax errors: check_robots.pack and root.after lambda.
# - Robust error handling with retries and user agent rotation.
# - Removed proxy server features as per user request.
# - Improved export: Scrape first, then prompt for save location via file dialog (defaults to output.csv if canceled).
#
# Prerequisites:
# 1. Install Python 3.8+[](https://www.python.org/downloads/)
# 2. Install packages: pip install playwright beautifulsoup4 requests
# 3. Run: playwright install # Downloads Chromium browser bundle.
#
# Outputs to a user-chosen CSV file (prompted after scraping).
import tkinter as tk
from tkinter import messagebox, Spinbox, scrolledtext, ttk, Checkbutton
import csv
import re
import time
import threading
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse
from collections import deque
import random
import json
from tkinter import filedialog
DEFAULT_RESULTS = 10 # Default number of results
DEFAULT_OUTPUT = 'output.csv' # Default output file if not chosen
DEFAULT_DEPTH = 2 # Default crawl depth
DEFAULT_MAX_PAGES = 30 # Default max pages per website
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
]
async def scrape_google_maps_async(search_query, max_results, non_headless, update_callback, progress_callback):
    data = []
    async with async_playwright() as p:
        launch_options = {'headless': not non_headless}
        browser = await p.chromium.launch(**launch_options)
        context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
        page = await context.new_page()
       
        try:
            update_callback("Loading Google Maps...")
            retries = 3
            while retries > 0:
                try:
                    await page.goto(f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}", timeout=30000)
                    await asyncio.sleep(3)
                    break
                except PlaywrightTimeoutError:
                    retries -= 1
                    print(f"Retry {4-retries} for Google Maps load")
                    await asyncio.sleep(2)
            if retries == 0:
                update_callback("Failed to load Google Maps after retries")
                return data
           
            # Accept cookies if prompted
            try:
                await page.locator('[aria-label="Accept all"]').click(timeout=3000)
                await asyncio.sleep(1)
            except PlaywrightTimeoutError:
                pass
           
            # Scroll to load more results
            scroll_pauses = max(2, max_results // 20 + 1)
            update_callback(f"Scrolling results ({scroll_pauses} times)...")
            try:
                for _ in range(scroll_pauses):
                    await page.evaluate("document.querySelector('div[role=\"feed\"]').scrollTop = document.querySelector('div[role=\"feed\"]').scrollHeight")
                    await asyncio.sleep(1.5)
            except PlaywrightTimeoutError:
                print("Results feed not found for scrolling.")
           
            # Find the list of results
            results = await page.locator('a.hfpxzc').all()
            results = results[:max_results]
           
            for i, result in enumerate(results):
                update_callback(f"Scraping result {i+1}/{len(results)}...")
                progress_callback((i + 1) / len(results) * 50) # 50% for Maps
                retries = 3
                while retries > 0:
                    try:
                        await result.click(timeout=3000)
                        await asyncio.sleep(2)
                       
                        info = {
                            'name': '',
                            'address': '',
                            'phone': '',
                            'website': '',
                            'contact_name': '',
                            'email': '',
                            'emails': '',
                            'website_addresses': '',
                            'phones': '',
                            'social_media': ''
                        }
                       
                        # Extract name
                        try:
                            info['name'] = await page.locator('h1.DUwDvf').inner_text(timeout=3000)
                            info['name'] = info['name'].strip()
                        except PlaywrightTimeoutError:
                            pass
                       
                        # Extract address
                        try:
                            address_elem = page.locator('[aria-label^="Address: "]')
                            aria_label = await address_elem.get_attribute('aria-label', timeout=3000)
                            if aria_label:
                                info['address'] = aria_label.split(':', 1)[1].strip()
                        except PlaywrightTimeoutError:
                            pass
                       
                        # Extract phone
                        try:
                            phone_elem = page.locator('[aria-label^="Phone: "]')
                            aria_label = await phone_elem.get_attribute('aria-label', timeout=3000)
                            if aria_label:
                                info['phone'] = aria_label.split(':', 1)[1].strip()
                        except PlaywrightTimeoutError:
                            pass
                       
                        # Extract website
                        try:
                            website_elem = page.locator('[aria-label^="Website: "]')
                            info['website'] = await website_elem.get_attribute('href', timeout=3000)
                        except PlaywrightTimeoutError:
                            pass
                       
                        # Attempt to find owner/contact name
                        try:
                            owner_elem = page.locator('[data-item-id="owner"]')
                            info['contact_name'] = await owner_elem.inner_text(timeout=3000)
                            info['contact_name'] = info['contact_name'].strip()
                        except PlaywrightTimeoutError:
                            pass
                       
                        data.append(info)
                       
                        # Go back to list and wait for results to reload
                        await page.go_back(timeout=5000)
                        try:
                            await page.locator('a.hfpxzc').nth(0).wait_for(state='visible', timeout=5000)
                        except PlaywrightTimeoutError:
                            pass
                        await asyncio.sleep(2)
                        break
                    except Exception as e:
                        print(f"Retry {4-retries} for result {i+1}: {e}")
                        retries -= 1
                        await asyncio.sleep(2)
                if retries == 0:
                    continue
        except Exception as e:
            print(f"Error scraping Google Maps for '{search_query}': {e}")
        finally:
            await browser.close()
   
    return data
def check_robots_txt(url):
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        response = requests.get(robots_url, timeout=5)
        if response.status_code == 200:
            if 'Disallow: /' in response.text:
                return False
        return True
    except Exception:
        return True # Assume allowed if can't check
def crawl_and_aggregate(start_url, max_depth, max_pages, check_robots, update_callback):
    if not start_url or (check_robots and not check_robots_txt(start_url)):
        return ['Robots.txt disallows scraping' if start_url else 'No website', 'Not found', 'Not found', 'Not found']
   
    parsed_start = urlparse(start_url)
    base_domain = parsed_start.netloc
    visited = set()
    queue = deque([(start_url, 0)])
   
    emails = set()
    addresses = set()
    phones = set()
    social_media = set()
   
    headers = {'User-Agent': random.choice(USER_AGENTS)}
   
    # Email regex (RFC 5322-compliant, case-insensitive)
    email_regex = re.compile(r'[a-z0-9!#$%&\'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&\'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}', re.IGNORECASE)
   
    # Address regex (international support)
    address_regex = re.compile(r'\b\d{1,5}\s+[\w\s.-]+(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Ln|Lane|Strasse|Rue|Av|Plaza)?,\s+[\w\s.-]+,\s+[A-Z]{2,}\s+[A-Z0-9- ]+\b', re.IGNORECASE)
   
    # Phone regex (US/international)
    phone_regex = re.compile(r'\b(?:\+?(\d{1,3}))?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
   
    # Social media regex
    social_regex = re.compile(r'^(https?://(?:www\.)?(facebook|x|twitter|instagram|linkedin)\.com/[\w\-/]+)', re.IGNORECASE)
   
    pages_visited = 0
   
    while queue and pages_visited < max_pages:
        url, depth = queue.popleft()
        if url in visited or depth > max_depth:
            continue
        visited.add(url)
        pages_visited += 1
       
        update_callback(f"Visiting website page: {url} ({pages_visited}/{max_pages})")
       
        try:
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
           
            soup = BeautifulSoup(response.text, 'html.parser')
            text_content = soup.get_text(separator=' ')
           
            # Extract emails
            page_emails = set(email_regex.findall(text_content))
            mailto_links = soup.find_all('a', href=re.compile(r'^mailto:', re.I))
            for link in mailto_links:
                email = link['href'][7:].split('?')[0].strip()
                if email:
                    page_emails.add(email)
           
            # Extract addresses
            page_addresses = set(m.group(0).strip() for m in address_regex.finditer(text_content))
           
            # Extract phones
            page_phones = set(m.group(0).strip() for m in phone_regex.finditer(text_content))
            tel_links = soup.find_all('a', href=re.compile(r'^tel:', re.I))
            for link in tel_links:
                phone = link['href'][4:].strip()
                if phone:
                    page_phones.add(phone)
           
            # Extract social media from hrefs
            for link in soup.find_all('a', href=True):
                href = link['href']
                if social_regex.match(href):
                    social_media.add(href)
           
            emails.update(page_emails)
            addresses.update(page_addresses)
            phones.update(page_phones)
           
            # Find links to crawl next
            for link in soup.find_all('a', href=True):
                next_url = urljoin(url, link['href'])
                parsed_next = urlparse(next_url)
                if parsed_next.netloc == base_domain and next_url not in visited:
                    queue.append((next_url, depth + 1))
       
        except Exception as e:
            print(f"Error crawling {url}: {e}")
            continue
       
        time.sleep(0.5)
   
    agg_email = '; '.join(sorted(emails)) if emails else 'Not found'
    agg_address = '; '.join(sorted(addresses)) if addresses else 'Not found'
    agg_phone = '; '.join(sorted(phones)) if phones else 'Not found'
    agg_social = '; '.join(sorted(social_media)) if social_media else 'Not found'
   
    return [agg_email, agg_address, agg_phone, agg_social]
def scrape_query():
    search_query = entry_query.get().strip()
    try:
        max_results = int(entry_results.get())
    except ValueError:
        max_results = DEFAULT_RESULTS
    try:
        max_depth = int(depth_entry.get())
    except ValueError:
        max_depth = DEFAULT_DEPTH
    try:
        max_pages = int(max_pages_entry.get())
    except ValueError:
        max_pages = DEFAULT_MAX_PAGES
    non_headless = var_non_headless.get()
    check_robots = var_check_robots.get()
   
    if not search_query:
        messagebox.showwarning("Input Error", "Please enter a search query.")
        return
   
    if max_results > 100:
        if not messagebox.askyesno("Warning", "High max_results (>100) may lead to detection. Continue?"):
            return
    if max_pages > 50 or max_depth > 5:
        if not messagebox.askyesno("Warning", "High max_pages (>50) or max_depth (>5) may lead to rate-limiting. Continue?"):
            return
   
    text_area.delete("1.0", tk.END)
    text_area.insert(tk.END, "Scraping started...\n")
    button.config(state='disabled')
    progress['value'] = 0
    root.update()
   
    def update_text_area(message):
        text_area.insert(tk.END, message + "\n")
        text_area.see(tk.END)
        root.update()
    def update_progress(value):
        progress['value'] = value
        root.update()
    def run_scraping():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            maps_data = loop.run_until_complete(scrape_google_maps_async(search_query, max_results, non_headless, update_text_area, update_progress))
           
            # Parallel website crawling
            update_text_area("Crawling websites...")
            websites = [info.get('website', '') for info in maps_data]
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_index = {executor.submit(crawl_and_aggregate, ws, max_depth, max_pages, check_robots, update_text_area): i for i, ws in enumerate(websites)}
                for i, future in enumerate(as_completed(future_to_index)):
                    index = future_to_index[future]
                    try:
                        emails, website_addresses, phones, social_media = future.result()
                        maps_data[index]['emails'] = emails
                        maps_data[index]['website_addresses'] = website_addresses
                        maps_data[index]['phones'] = phones
                        maps_data[index]['social_media'] = social_media
                        update_progress(50 + (i + 1) / len(websites) * 50) # 50% for websites
                    except Exception as e:
                        print(f"Error in parallel crawling: {e}")
           
            # Prompt for save location after scraping
            output_file = filedialog.asksaveasfilename(title="Save CSV File", defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
            if not output_file:
                output_file = DEFAULT_OUTPUT
           
            # Write to CSV
            fieldnames = ['name', 'address', 'phone', 'website', 'contact_name', 'email', 'emails', 'website_addresses', 'phones', 'social_media']
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(maps_data)
           
            root.after(0, lambda: update_text_area(f"Scraping completed. Found {len(maps_data)} results. Data saved to {output_file}"))
            root.after(0, lambda: messagebox.showinfo("Success", f"Scraping completed. Check {output_file}"))
        except Exception as e:
            root.after(0, lambda: update_text_area(f"Scraping failed: {str(e)}"))
            root.after(0, lambda: messagebox.showerror("Error", f"Scraping failed: {str(e)}"))
        finally:
            def finalize():
                button.config(state='normal')
                progress['value'] = 100
            root.after(0, finalize)
    # Run scraping in a separate thread
    threading.Thread(target=run_scraping, daemon=True).start()
def save_config():
    config = {
        'max_depth': depth_entry.get(),
        'max_pages': max_pages_entry.get(),
        'non_headless': var_non_headless.get(),
        'check_robots': var_check_robots.get()
    }
    file = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
    if file:
        with open(file, 'w') as f:
            json.dump(config, f)
def load_config():
    file = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
    if file:
        with open(file, 'r') as f:
            config = json.load(f)
        depth_entry.delete(0, tk.END)
        depth_entry.insert(0, config.get('max_depth', '2'))
        max_pages_entry.delete(0, tk.END)
        max_pages_entry.insert(0, config.get('max_pages', '30'))
        var_non_headless.set(config.get('non_headless', 0))
        var_check_robots.set(config.get('check_robots', 1))
# Create GUI
root = tk.Tk()
root.title("Advanced Business Scraper (2025 Edition)")
root.geometry("700x700")
root.configure(bg='#f0f0f0')
# Frame
frame = tk.Frame(root, bg="#f0f0f0", padx=20, pady=20)
frame.pack(fill=tk.BOTH, expand=True)
# Query
tk.Label(frame, text="Search Query (e.g., restaurants in New York):", bg='#f0f0f0', font=('Arial', 12)).pack(anchor="w", pady=5)
entry_query = tk.Entry(frame, width=60, font=('Arial', 11))
entry_query.pack(pady=5)
# Max Results
tk.Label(frame, text="Max Results (up to 200):", bg='#f0f0f0', font=('Arial', 12)).pack(anchor="w", pady=5)
entry_results = Spinbox(frame, from_=1, to=200, width=5, font=('Arial', 11))
entry_results.pack(anchor="w", pady=5)
# Max Depth
tk.Label(frame, text="Max Crawl Depth:", bg='#f0f0f0', font=('Arial', 12)).pack(anchor="w", pady=5)
depth_entry = tk.Entry(frame, width=5, font=('Arial', 11))
depth_entry.insert(0, str(DEFAULT_DEPTH))
depth_entry.pack(anchor="w", pady=5)
# Max Pages per Website
tk.Label(frame, text="Max Pages per Website:", bg='#f0f0f0', font=('Arial', 12)).pack(anchor="w", pady=5)
max_pages_entry = tk.Entry(frame, width=5, font=('Arial', 11))
max_pages_entry.insert(0, str(DEFAULT_MAX_PAGES))
max_pages_entry.pack(anchor="w", pady=5)
# Checkboxes
var_non_headless = tk.IntVar()
check_non_headless = Checkbutton(frame, text="Non-Headless Mode (Visible Browser)", variable=var_non_headless, bg='#f0f0f0')
check_non_headless.pack(anchor="w", pady=5)
var_check_robots = tk.IntVar(value=1)
check_robots = Checkbutton(frame, text="Check robots.txt", variable=var_check_robots, bg='#f0f0f0')
check_robots.pack(anchor="w", pady=5)
# Config Buttons
config_frame = tk.Frame(frame, bg='#f0f0f0')
config_frame.pack(pady=5)
tk.Button(config_frame, text="Save Config", command=save_config, bg='#2196F3', fg='white', font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
tk.Button(config_frame, text="Load Config", command=load_config, bg='#2196F3', fg='white', font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
# Start Button
button = tk.Button(frame, text="Start Scraping", command=scrape_query, bg='#4CAF50', fg='white', font=('Arial', 12, 'bold'))
button.pack(pady=10)
# Progress Bar
progress = ttk.Progressbar(frame, orient="horizontal", length=400, mode="determinate")
progress.pack(pady=10)
# Text Area for Logs
text_area = scrolledtext.ScrolledText(frame, height=10, width=70, font=('Arial', 10))
text_area.pack(pady=10)
root.mainloop()
