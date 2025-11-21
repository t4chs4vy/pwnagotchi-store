#!/usr/bin/env python3
'''
PwnStore - The Unofficial Pwnagotchi App Store
Author: WPA2
Donations: https://buymeacoffee.com/wpa2
'''

import requests
import json
import argparse
import os
import sys
import zipfile
import io
import shutil

# --- CONFIGURATION ---
# PASTE YOUR GITEA RAW URL HERE
REGISTRY_URL = "http://gitea.local/wpa2/pwnagotchi-store/raw/branch/main/plugins.json"

CUSTOM_PLUGIN_DIR = "/usr/local/share/pwnagotchi/custom-plugins/"
CONFIG_FILE = "/etc/pwnagotchi/config.toml"

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
RESET = "\033[0m"

def banner():
    print(f"{CYAN}")
    print(r"  ____                _____ _                  ")
    print(r" |  _ \ _      ___ __/ ____| |                 ")
    print(r" | |_) \ \ /\ / / '_ \ (___| |_ ___  _ __ ___  ")
    print(r" |  __/ \ V  V /| | | \___ \ __/ _ \| '__/ _ \ ")
    print(r" | |     \_/\_/ |_| |_|____/ || (_) | | |  __/ ")
    print(r" |_|   v1.0 by WPA2     \_____/\__\___/|_|  \___| ")
    print(f"{RESET}")
    print(f"  Support the dev: {GREEN}https://buymeacoffee.com/wpa2{RESET}\n")

def get_installed_plugins():
    if not os.path.exists(CUSTOM_PLUGIN_DIR):
        return []
    return [f.replace(".py", "") for f in os.listdir(CUSTOM_PLUGIN_DIR) if f.endswith(".py")]

def fetch_registry():
    try:
        print(f"[*] Fetching plugin list...")
        r = requests.get(REGISTRY_URL)
        if r.status_code != 200:
            print(f"{RED}[!] Could not connect to store (Status: {r.status_code}){RESET}")
            sys.exit(1)
        return r.json()
    except Exception as e:
        print(f"{RED}[!] Connection failed. Check your internet or Gitea URL.{RESET}")
        print(f"{YELLOW}Debug: {e}{RESET}")
        sys.exit(1)

def list_plugins(args):
    registry = fetch_registry()
    installed = get_installed_plugins()
    
    print(f"{'NAME':<20} | {'VERSION':<8} | {'STATUS':<10} | {'DESCRIPTION'}")
    print("-" * 85)
    
    for p in registry:
        name = p['name']
        status = f"{GREEN}INSTALLED{RESET}" if name in installed else "Available"
        desc = p['description'][:40] + "..." if len(p['description']) > 40 else p['description']
        print(f"{name:<20} | {p['version']:<8} | {status:<19} | {desc}")
    print("-" * 85)

def install_plugin(args):
    target_name = args.name
    registry = fetch_registry()
    
    plugin_data = next((p for p in registry if p['name'] == target_name), None)
    
    if not plugin_data:
        print(f"{RED}[!] Plugin '{target_name}' not found in registry.{RESET}")
        return

    print(f"[*] Installing {CYAN}{target_name}{RESET} by {plugin_data['author']}...")

    try:
        # CASE 1: Plugin is inside a ZIP (Repo Pack)
        if plugin_data.get('origin_type') == 'zip':
            print(f"[*] Downloading repository archive...")
            r = requests.get(plugin_data['download_url'])
            z = zipfile.ZipFile(io.BytesIO(r.content))
            
            target_path = plugin_data['path_inside_zip']
            print(f"[*] Extracting {target_path}...")
            
            # Ensure custom directory exists
            if not os.path.exists(CUSTOM_PLUGIN_DIR):
                os.makedirs(CUSTOM_PLUGIN_DIR)

            # Extract specific file to memory then write to destination
            with z.open(target_path) as source, open(os.path.join(CUSTOM_PLUGIN_DIR, f"{target_name}.py"), "wb") as dest:
                shutil.copyfileobj(source, dest)
                
        # CASE 2: Plugin is a single file
        else:
            print(f"[*] Downloading file...")
            r = requests.get(plugin_data['download_url'])
            if not os.path.exists(CUSTOM_PLUGIN_DIR):
                os.makedirs(CUSTOM_PLUGIN_DIR)
            with open(os.path.join(CUSTOM_PLUGIN_DIR, f"{target_name}.py"), "wb") as f:
                f.write(r.content)

        print(f"{GREEN}[+] Successfully installed to {CUSTOM_PLUGIN_DIR}{target_name}.py{RESET}")
        
        # AUTO-ENABLE in Config
        enable_in_config(target_name)

    except Exception as e:
        print(f"{RED}[!] Installation failed: {e}{RESET}")

def enable_in_config(plugin_name):
    """Quick and dirty config updater."""
    print(f"[*] Checking config.toml...")
    try:
        with open(CONFIG_FILE, "r") as f:
            config_data = f.read()
        
        if f"main.plugins.{plugin_name}.enabled" in config_data:
            print(f"[*] Plugin entry already exists in config.")
        else:
            print(f"[*] Appending enable flag to {CONFIG_FILE}")
            with open(CONFIG_FILE, "a") as f:
                f.write(f"\nmain.plugins.{plugin_name}.enabled = true\n")
            print(f"{GREEN}[+] Enabled in config! Restart pwnagotchi to apply.{RESET}")
            
    except Exception as e:
        print(f"{YELLOW}[!] Could not update config automatically: {e}{RESET}")

def main():
    banner()
    parser = argparse.ArgumentParser(description="Pwnagotchi Plugin Manager")
    subparsers = parser.add_subparsers()

    # List Command
    parser_list = subparsers.add_parser('list', help='List all available plugins')
    parser_list.set_defaults(func=list_plugins)

    # Install Command
    parser_install = subparsers.add_parser('install', help='Install a plugin')
    parser_install.add_argument('name', type=str, help='Name of the plugin')
    parser_install.set_defaults(func=install_plugin)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
