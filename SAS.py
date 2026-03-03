#Terminal Version
import os
import re
import sys
import time
import subprocess
import winreg

from config import STEAM_EXE, VDF_PATH, REG_PATH, VERSION, APP_NAME

# ── ANSI colors (work in Windows Terminal / VS Code terminal) ────────────────
GREEN  = "\033[92m"
CYAN   = "\033[96m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

# ── Parse loginusers.vdf ─────────────────────────────────────────────────────

def parse_accounts():
    if not os.path.exists(VDF_PATH):
        print(f"{RED}ERROR: loginusers.vdf not found.{RESET}")
        print("Make sure Steam is installed and you have logged in at least once.")
        sys.exit(1)

    with open(VDF_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    accounts = {}
    blocks = re.findall(r'"(\d{17})"\s*\{([^}]*)\}', content, re.DOTALL)

    for steamid, block in blocks:
        name     = re.search(r'"AccountName"\s+"([^"]+)"', block)
        persona  = re.search(r'"PersonaName"\s+"([^"]+)"', block)
        remember = re.search(r'"RememberPassword"\s+"([01])"', block)
        recent   = re.search(r'"MostRecent"\s+"([01])"', block)

        if name:
            accounts[name.group(1)] = {
                "steamid":  steamid,
                "persona":  persona.group(1) if persona else name.group(1),
                "remember": remember.group(1) if remember else "0",
                "recent":   recent.group(1) if recent else "0"
            }

    return accounts

# ── Patch loginusers.vdf ─────────────────────────────────────────────────────

def patch_vdf(target_username):
    with open(VDF_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    result        = []
    inside_target = False

    for line in lines:
        match = re.search(r'"AccountName"\s+"([^"]+)"', line)
        if match:
            inside_target = (match.group(1).lower() == target_username.lower())

        if re.search(r'"MostRecent"', line):
            val  = "1" if inside_target else "0"
            line = re.sub(r'"MostRecent"\s+"[01]"', f'"MostRecent"\t\t"{val}"', line)

        if inside_target and re.search(r'"RememberPassword"', line):
            line = re.sub(r'"RememberPassword"\s+"[01]"', '"RememberPassword"\t\t"1"', line)

        if re.match(r'^\s*\}\s*$', line):
            inside_target = False

        result.append(line)

    with open(VDF_PATH, "w", encoding="utf-8") as f:
        f.writelines(result)

# ── Registry ─────────────────────────────────────────────────────────────────

def set_registry(username):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "AutoLoginUser",    0, winreg.REG_SZ,    username)
        winreg.SetValueEx(key, "RememberPassword", 0, winreg.REG_DWORD, 1)
        winreg.CloseKey(key)
    except Exception as e:
        print(f"{RED}ERROR: Could not write to registry: {e}{RESET}")
        sys.exit(1)

# ── Steam process ─────────────────────────────────────────────────────────────

def kill_steam():
    result = subprocess.call(
        ["taskkill", "/F", "/IM", "steam.exe"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    if result == 0:
        print(f"{YELLOW}Steam closed. Waiting...{RESET}")
    time.sleep(2)

def launch_steam():
    if not os.path.exists(STEAM_EXE):
        print(f"{RED}ERROR: steam.exe not found at {STEAM_EXE}{RESET}")
        print("Update STEAM_PATH in config.py")
        sys.exit(1)
    subprocess.Popen([STEAM_EXE])

# ── UI ────────────────────────────────────────────────────────────────────────

def print_header():
    print(f"\n{CYAN}{BOLD}╔══════════════════════════════════════╗{RESET}")
    print(f"{CYAN}{BOLD}║       {APP_NAME}      ║{RESET}")
    print(f"{CYAN}{BOLD}║              v{VERSION}                  ║{RESET}")
    print(f"{CYAN}{BOLD}╚══════════════════════════════════════╝{RESET}\n")

def print_accounts(accounts):
    names = list(accounts.keys())
    for i, name in enumerate(names, 1):
        acc      = accounts[name]
        persona  = acc["persona"]
        tag      = f"{GREEN}[active]{RESET}" if acc["recent"] == "1" else ""
        warning  = f" {YELLOW}⚠ no saved session{RESET}" if acc["remember"] == "0" else ""
        print(f"  {BOLD}[{i}]{RESET} {persona} {CYAN}({name}){RESET} {tag}{warning}")
    print()

def pick_account(accounts):
    names = list(accounts.keys())
    print_accounts(accounts)

    try:
        raw = input(f"{BOLD}Select account [1-{len(names)}] or Q to quit: {RESET}").strip()
        if raw.lower() == "q":
            return None
        choice = int(raw) - 1
        if 0 <= choice < len(names):
            return names[choice]
        else:
            print(f"{RED}Invalid choice.{RESET}")
            return None
    except (ValueError, KeyboardInterrupt):
        return None

# ── Main ─────────────────────────────────────────────────────────────────────

def switch_to(target, accounts):
    if target not in accounts:
        print(f"{RED}ERROR: Account '{target}' not found.{RESET}")
        sys.exit(1)

    persona = accounts[target]["persona"]

    if accounts[target]["remember"] == "0":
        print(f"{YELLOW}Warning: No saved session for {target}. You may need to enter your password.{RESET}")

    print(f"\nSwitching to {BOLD}{persona}{RESET} ({target})...")
    kill_steam()
    patch_vdf(target)
    set_registry(target)
    launch_steam()
    print(f"{GREEN}Done! Steam is launching as {persona}.{RESET}\n")

def main():
    print_header()
    accounts = parse_accounts()

    if not accounts:
        print(f"{RED}No saved accounts found. Log into Steam with 'Remember me' first.{RESET}")
        sys.exit(1)

    # Pass username directly: python steam_switcher.py myUsername
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = pick_account(accounts)

    if not target:
        print("Bye!")
        sys.exit(0)

    switch_to(target, accounts)

if __name__ == "__main__":
    main()
