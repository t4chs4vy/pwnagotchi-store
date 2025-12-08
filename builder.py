import requests
import json
import re
import io
import zipfile
import os
import logging
from collections import defaultdict

# --- CONFIGURATION ---
INPUT_FILE = "repos.txt"
OUTPUT_FILE = "plugins.json"

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# --- SMART CATEGORY DICTIONARY ---
KEYWORDS = {
    'GPS': ['gps', 'geo', 'lat', 'lon', 'location', 'map', 'coordinates', 'nmea', 'track', 'wigle', 'wardrive'],
    'Social': ['discord', 'telegram', 'twitter', 'social', 'chat', 'bot', 'webhook', 'slack', 'message', 'notify'],
    'Display': ['screen', 'display', 'ui', 'theme', 'face', 'font', 'oled', 'ink', 'led', 'view', 'clock', 'weather', 'status', 'mem', 'cpu', 'info'],
    'Attack': ['pwn', 'crack', 'handshake', 'deauth', 'assoc', 'brute', 'attack', 'wardriving', 'pmkid', 'wpa', 'eapol', 'sniff'],
    'Hardware': ['ups', 'battery', 'power', 'shutdown', 'reboot', 'button', 'switch', 'gpio', 'i2c', 'spi', 'bluetooth', 'ble', 'hw'],
    'System': ['backup', 'ssh', 'log', 'update', 'fix', 'clean', 'config', 'manage', 'util', 'internet', 'wifi', 'connection']
}

def detect_category(name, description, code):
    scores = defaultdict(int)
    name_lower = name.lower()
    desc_lower = description.lower() if description else ""
    code_lower = code.lower()

    for category, tags in KEYWORDS.items():
        for tag in tags:
            if tag in name_lower: scores[category] += 10
            if re.search(r'\b' + re.escape(tag) + r'\b', desc_lower): scores[category] += 3
            if tag in code_lower[:2000]: scores[category] += 1

    if "ui.set" in code_lower: scores["Display"] += 5
    if "gpio" in code_lower: scores["Hardware"] += 2

    if not scores: return "System"
    return max(scores, key=scores.get)

def parse_python_content(code, filename, origin_url, internal_path=None):
    data = {}
    
    # --- ROBUST REGEX FIX for Description ---
    # This pattern captures the description regardless of single (') or double (") quotes
    # and handles internal quotes by using a backreference (\1).
    desc_match = re.search(r"__description__\s*=\s*([\"'])((?:(?!\1).)*)\1", code, re.DOTALL)
    
    # Check for version and author
    version_match = re.search(r"__version__\s*=\s*['\"](.+?)['\"]", code)
    author_match = re.search(r"__author__\s*=\s*['\"](.+?)['\"]", code)

    data['version'] = version_match.group(1) if version_match else "0.0.1"
    data['author'] = author_match.group(1) if author_match else "Unknown"
    data['description'] = desc_match.group(2).strip() if desc_match else "No description provided."
    
    # Determine category
    data['category'] = detect_category(filename.replace(".py", ""), data['description'], code)

    if data['description'] != "No description provided." or data['version'] != "0.0.1":
        return {
            "name": filename.replace(".py", ""),
            "version": data['version'],
            "description": data['description'],
            "author": data['author'],
            "category": data['category'],
            "origin_type": "zip" if internal_path else "single",
            "download_url": origin_url,
            "path_inside_zip": internal_path
        }
    return None

def process_zip_url(url):
    found = []
    try:
        logging.info(f"[*] Downloading ZIP: {url}...")
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        
        z = zipfile.ZipFile(io.BytesIO(r.content))
        
        for filename in z.namelist():
            if filename.endswith(".py") and "__init__" not in filename and "/." not in filename:
                with z.open(filename) as f:
                    code = f.read().decode('utf-8', errors='ignore')
                
                # Simple check for plugin status
                if 'from pwnagotchi.plugins import Plugin' in code or 'class ' in code and '(Plugin)' in code:
                    plugin = parse_python_content(code, filename.split("/")[-1], url, filename)
                    if plugin:
                        logging.info(f"    [+] {plugin['name']:<25} -> {plugin['category']}")
                        found.append(plugin)
                
    except Exception as e:
        logging.error(f"    [!] ZIP Error for {url}: {e}")
    return found

def main():
    print("--- PwnStore Builder v1.2 Starting ---")
    master_list = []
    
    if not os.path.exists(INPUT_FILE):
        logging.error(f"Error: {INPUT_FILE} not found.")
        return

    with open(INPUT_FILE, "r") as f:
        urls = [line.strip() for line in f.readlines() if line.strip() and not line.startswith("#")]

    for url in urls:
        if url.endswith(".zip"):
            plugins = process_zip_url(url)
            master_list.extend(plugins)
        else:
            try:
                # Handle single raw file URL
                code = requests.get(url, timeout=15).text
                plugin = parse_python_content(code, url.split("/")[-1], url, None)
                if plugin:
                    logging.info(f"    [+] {plugin['name']:<25} -> {plugin['category']}")
                    master_list.append(plugin)
            except Exception as e: 
                logging.error(f"    [!] Raw File Error for {url}: {e}")

    # --- DEDUPLICATION AND SORT ---
    # Using dictionary to keep the highest version of each plugin
    final_plugins = {}
    for plugin in master_list:
        name_key = plugin['name'].lower()
        if name_key not in final_plugins or plugin['version'] > final_plugins[name_key]['version']:
            final_plugins[name_key] = plugin
            
    # Sort the final list alphabetically by name
    sorted_plugins = sorted(final_plugins.values(), key=lambda p: p['name'].lower())

    with open(OUTPUT_FILE, "w") as f:
        json.dump(sorted_plugins, f, indent=2)
    
    print(f"\n[SUCCESS] Generated sorted registry with {len(sorted_plugins)} unique plugins.")

if __name__ == "__main__":
    main()
