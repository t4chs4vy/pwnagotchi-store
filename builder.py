import requests
import json
import re
import io
import zipfile
import os

# --- CONFIGURATION ---
INPUT_FILE = "repos.txt"
OUTPUT_FILE = "plugins.json"

# --- CATEGORY LOGIC ---
def detect_category(code, name):
    """Scans code AND filename for keywords to guess the category."""
    text = (code + " " + name).lower()
    
    # 1. CHECK GPS (High Priority)
    if any(x in text for x in ['gps', 'location', 'coordinates', 'fix', 'lat', 'lon', 'nmea', 'geo']):
        return "GPS"
    
    # 2. CHECK ATTACK / WIFI
    if any(x in text for x in ['handshake', 'deauth', 'assoc', 'crack', 'pwn', 'attack', 'sniffer', 'wpa', 'pmkid', 'pcap', 'wardriving']):
        return "Attack"

    # 3. CHECK HARDWARE / BLUETOOTH
    if any(x in text for x in ['led', 'gpio', 'light', 'button', 'ups', 'battery', 'i2c', 'spi', 'bluetooth', 'bt-', 'ble']):
        return "Hardware"

    # 4. CHECK SOCIAL / NOTIFICATIONS
    if any(x in text for x in ['discord', 'telegram', 'twitter', 'social', 'webhook', 'slack', 'ntfy', 'push', 'message']):
        return "Social"

    # 5. CHECK DISPLAY / UI
    if any(x in text for x in ['ui.set', 'display', 'font', 'screen', 'canvas', 'faces', 'render', 'draw', 'view', 'image', 'text']):
        return "Display"
        
    # 6. CHECK SYSTEM / UTILS
    if any(x in text for x in ['log', 'backup', 'ssh', 'ftp', 'system', 'update', 'cpu', 'mem', 'temp', 'disk', 'reboot', 'shutdown', 'internet', 'connection']):
        return "System"
    
    return "General"

# --- METADATA EXTRACTION ---
def parse_python_content(code, filename, origin_url, internal_path=None):
    try:
        # 1. Find Version and Author
        version = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", code)
        author = re.search(r"__author__\s*=\s*['\"]([^'\"]+)['\"]", code)
        
        # 2. Find Description (Multi-line safe)
        desc_match = re.search(r"__description__\s*=\s*(?:['\"]([^'\"]+)['\"]|\(([^)]+)\))", code, re.DOTALL)
        description = "No description provided."
        if desc_match:
            if desc_match.group(1):
                description = desc_match.group(1)
            elif desc_match.group(2):
                raw_desc = desc_match.group(2)
                description = re.sub(r"['\"\n\r]", "", raw_desc)
                description = re.sub(r"\s+", " ", description).strip()

        # 3. Detect Category (Pass Name AND Code now)
        category = detect_category(code, filename)

        if description != "No description provided." or version:
            return {
                "name": filename.replace(".py", ""),
                "version": version.group(1) if version else "0.0.1",
                "description": description,
                "author": author.group(1) if author else "Unknown",
                "category": category,
                "origin_type": "zip" if internal_path else "single",
                "download_url": origin_url,
                "path_inside_zip": internal_path
            }
    except Exception as e:
        print(f"[!] Error parsing {filename}: {e}")
    return None

def process_zip_url(url):
    found = []
    try:
        print(f"[*] Downloading ZIP: {url}...")
        r = requests.get(url)
        if r.status_code != 200:
            print(f"   [!] Failed to download (Status: {r.status_code})")
            return []
            
        z = zipfile.ZipFile(io.BytesIO(r.content))
        
        for filename in z.namelist():
            if filename.endswith(".py") and "__init__" not in filename and "/." not in filename:
                with z.open(filename) as f:
                    code = f.read().decode('utf-8', errors='ignore')
                
                plugin = parse_python_content(code, filename.split("/")[-1], url, filename)
                if plugin:
                    print(f"   [+] Found: {plugin['name']} [{plugin['category']}]")
                    found.append(plugin)
    except Exception as e:
        print(f"   [!] ZIP Error: {e}")
    return found

def main():
    master_list = []
    
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    with open(INPUT_FILE, "r") as f:
        urls = [line.strip() for line in f.readlines() if line.strip() and not line.startswith("#")]

    for url in urls:
        if url.endswith(".zip"):
            plugins = process_zip_url(url)
            master_list.extend(plugins)
        else:
            try:
                print(f"[*] Scanning file: {url}")
                code = requests.get(url).text
                plugin = parse_python_content(code, url.split("/")[-1], url, None)
                if plugin:
                    master_list.append(plugin)
            except Exception as e:
                print(f"   [!] Error: {e}")

    with open(OUTPUT_FILE, "w") as f:
        json.dump(master_list, f, indent=2)
    
    print(f"\n[SUCCESS] Generated {OUTPUT_FILE} with {len(master_list)} plugins.")

if __name__ == "__main__":
    main()
