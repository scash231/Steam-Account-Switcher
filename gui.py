import os
import sys
import json
import time
import threading
import subprocess
import webbrowser
import customtkinter as ctk
from tkinter import filedialog, messagebox

from config import VERSION, APP_NAME, STEAM_EXE
from SAS import parse_accounts, patch_vdf, set_registry

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")

ACCOUNTS_FILE = "accounts.json"
SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    "steam_path":         r"C:\Program Files (x86)\Steam",
    "kill_wait":          4,
    "minimize_on_switch": False,
    "close_on_switch":    False,
    "launch_args":        "",
    "auto_login":         "",
    "sort_by":            "name",
    "appearance":         "system",
    "theme":              "blue",
}

# ── Persistence ───────────────────────────────────────────────────────────────

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return DEFAULT_SETTINGS.copy()
    with open(SETTINGS_FILE) as f:
        return {**DEFAULT_SETTINGS, **json.load(f)}

def save_settings(d):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(d, f, indent=2)

def load_manual():
    if not os.path.exists(ACCOUNTS_FILE):
        return {}
    with open(ACCOUNTS_FILE) as f:
        return json.load(f)

def save_manual(d):
    with open(ACCOUNTS_FILE, "w") as f:
        json.dump(d, f, indent=2)

# ── Account Row ───────────────────────────────────────────────────────────────

class AccountRow(ctk.CTkFrame):
    def __init__(self, master, username, persona, steamid,
                 is_active, is_manual, note,
                 on_switch, on_edit, on_delete, on_copy_id, on_profile,
                 **kwargs):
        super().__init__(master, height=52, corner_radius=8, **kwargs)
        self.pack_propagate(False)

        # Active dot
        ctk.CTkFrame(self, width=6, height=6, corner_radius=3,
                     fg_color="#1db954" if is_active else "#3a3a3a"
                     ).place(x=10, rely=0.5, anchor="w")

        # Avatar initials circle
        av = ctk.CTkFrame(self, width=34, height=34, corner_radius=17,
                           fg_color="#1a4a7a" if not is_manual else "#4a3a1a")
        av.place(x=22, rely=0.5, anchor="w")
        av.pack_propagate(False)
        ctk.CTkLabel(av,
                     text=(persona[:2].upper() if persona else "??"),
                     font=("Segoe UI", 12, "bold"),
                     text_color="white"
                     ).place(relx=0.5, rely=0.5, anchor="center")

        # Name + note
        ctk.CTkLabel(self,
                     text=persona,
                     font=("Segoe UI", 13, "bold" if is_active else "normal"),
                     anchor="w"
                     ).place(x=64, rely=0.28, anchor="w")

        sub = f"@{username}"
        if note:
            sub += f"  •  {note}"
        ctk.CTkLabel(self,
                     text=sub,
                     font=("Segoe UI", 10),
                     text_color="#666",
                     anchor="w"
                     ).place(x=64, rely=0.72, anchor="w")

        # Right-side buttons
        # Switch
        ctk.CTkButton(self,
                       text="↺" if is_active else "Switch",
                       width=68, height=28,
                       font=("Segoe UI", 11),
                       fg_color="#1a3d1a" if is_active else "#1f538d",
                       hover_color="#266326" if is_active else "#2a6aad",
                       command=lambda: on_switch(username)
                       ).place(relx=0.985, rely=0.5, anchor="e")

        if is_manual:
            ctk.CTkButton(self, text="✕",
                           width=26, height=26,
                           font=("Segoe UI", 12),
                           fg_color="transparent",
                           hover_color="#5a1a1a",
                           text_color="#777",
                           command=lambda: on_delete(username)
                           ).place(relx=0.845, rely=0.5, anchor="center")

            ctk.CTkButton(self, text="Edit",
                           width=42, height=26,
                           font=("Segoe UI", 10),
                           fg_color="#2a2a2a",
                           hover_color="#1f538d",
                           text_color="#aaa",
                           command=lambda: on_edit(username)
                           ).place(relx=0.765, rely=0.5, anchor="center")
        else:
            # Copy SteamID
            ctk.CTkButton(self, text="ID",
                           width=30, height=26,
                           font=("Segoe UI", 10),
                           fg_color="#2a2a2a",
                           hover_color="#333",
                           text_color="#aaa",
                           command=lambda: on_copy_id(steamid)
                           ).place(relx=0.845, rely=0.5, anchor="center")

            # Open profile
            ctk.CTkButton(self, text="↗",
                           width=30, height=26,
                           font=("Segoe UI", 12),
                           fg_color="#2a2a2a",
                           hover_color="#333",
                           text_color="#aaa",
                           command=lambda: on_profile(steamid)
                           ).place(relx=0.765, rely=0.5, anchor="center")


# ── Account Dialog (Add / Edit) ───────────────────────────────────────────────

class AccountDialog(ctk.CTkToplevel):
    def __init__(self, master, on_save, username="", password="", note=""):
        super().__init__(master)
        self.title("Edit Account" if username else "Add Account")
        self.geometry("380x340")
        self.resizable(False, False)
        self.grab_set()
        self.on_save      = on_save
        self.old_username = username
        self._build(username, password, note)

    def _build(self, username, password, note):
        ctk.CTkLabel(self,
                     text="Edit Account" if self.old_username else "Add Account",
                     font=("Segoe UI", 15, "bold")
                     ).pack(pady=(22, 4))
        ctk.CTkLabel(self,
                     text="Stored locally in accounts.json",
                     font=("Segoe UI", 10),
                     text_color="#666"
                     ).pack(pady=(0, 12))

        self.user_e = ctk.CTkEntry(self, placeholder_text="Steam username",
                                    width=300, height=36)
        self.user_e.pack(pady=5)
        if username:
            self.user_e.insert(0, username)

        self.pass_e = ctk.CTkEntry(self, placeholder_text="Password",
                                    width=300, height=36, show="●")
        self.pass_e.pack(pady=5)
        if password:
            self.pass_e.insert(0, password)

        self.note_e = ctk.CTkEntry(self, placeholder_text="Note  (optional — e.g. 'main', 'alt')",
                                    width=300, height=36)
        self.note_e.pack(pady=5)
        if note:
            self.note_e.insert(0, note)

        self.show_var = ctk.IntVar()
        ctk.CTkCheckBox(self, text="Show password",
                         font=("Segoe UI", 11),
                         variable=self.show_var,
                         command=lambda: self.pass_e.configure(
                             show="" if self.show_var.get() else "●")
                         ).pack(pady=(6, 14))

        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack()
        ctk.CTkButton(f, text="Cancel", width=130, fg_color="#2a2a2a",
                       command=self.destroy).pack(side="left", padx=6)
        ctk.CTkButton(f, text="Save", width=130,
                       command=self._save).pack(side="left", padx=6)

    def _save(self):
        u = self.user_e.get().strip()
        p = self.pass_e.get().strip()
        n = self.note_e.get().strip()
        if u and p:
            self.on_save(self.old_username, u, p, n)
            self.destroy()


# ── Settings Window ───────────────────────────────────────────────────────────

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, master, settings, steam_accounts, on_save):
        super().__init__(master)
        self.title("Settings — SAS")
        self.geometry("520x440")
        self.resizable(False, False)
        self.grab_set()
        self.settings       = settings.copy()
        self.steam_accounts = steam_accounts
        self.on_save        = on_save
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Settings",
                     font=("Segoe UI", 16, "bold")
                     ).pack(pady=(18, 8), padx=22, anchor="w")

        self.tabs = ctk.CTkTabview(self, width=480, height=320)
        self.tabs.pack(padx=20, fill="both", expand=True)
        for t in ["General", "Appearance", "Steam", "Auto Login", "About"]:
            self.tabs.add(t)

        self._tab_general()
        self._tab_appearance()
        self._tab_steam()
        self._tab_autologin()
        self._tab_about()

        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(pady=14)
        ctk.CTkButton(f, text="Cancel", width=130, fg_color="#2a2a2a",
                       command=self.destroy).pack(side="left", padx=8)
        ctk.CTkButton(f, text="Save", width=130,
                       command=self._save).pack(side="left", padx=8)

    def _lbl(self, tab, text, note=None):
        ctk.CTkLabel(self.tabs.tab(tab), text=text,
                     font=("Segoe UI", 12)).pack(anchor="w", padx=14, pady=(12, 2))
        if note:
            ctk.CTkLabel(self.tabs.tab(tab), text=note,
                         font=("Segoe UI", 10),
                         text_color="#555").pack(anchor="w", padx=14, pady=(0, 2))

    def _tab_general(self):
        t = "General"
        self.minimize_var = ctk.BooleanVar(value=self.settings["minimize_on_switch"])
        ctk.CTkSwitch(self.tabs.tab(t), text="Minimize SAS when switching",
                       variable=self.minimize_var).pack(anchor="w", padx=14, pady=(16, 6))

        self.close_var = ctk.BooleanVar(value=self.settings["close_on_switch"])
        ctk.CTkSwitch(self.tabs.tab(t), text="Close SAS after switching accounts",
                       variable=self.close_var).pack(anchor="w", padx=14, pady=6)

        self._lbl(t, "Kill wait time (seconds)",
                  "How long to wait after Steam closes before relaunching.")
        self.wait_var = ctk.StringVar(value=str(self.settings["kill_wait"]))
        ctk.CTkEntry(self.tabs.tab(t), textvariable=self.wait_var,
                     width=70, height=30).pack(anchor="w", padx=14)

    def _tab_appearance(self):
        t = "Appearance"
        self._lbl(t, "Appearance mode")
        self.appearance_var = ctk.StringVar(value=self.settings["appearance"])
        ctk.CTkSegmentedButton(self.tabs.tab(t),
                                values=["dark", "light", "system"],
                                variable=self.appearance_var,
                                width=260).pack(anchor="w", padx=14)

        self._lbl(t, "Theme color")
        self.theme_var = ctk.StringVar(value=self.settings["theme"])
        ctk.CTkSegmentedButton(self.tabs.tab(t),
                                values=["blue", "green", "dark-blue"],
                                variable=self.theme_var,
                                width=300).pack(anchor="w", padx=14)

        self._lbl(t, "Sort accounts by")
        self.sort_var = ctk.StringVar(value=self.settings["sort_by"])
        ctk.CTkSegmentedButton(self.tabs.tab(t),
                                values=["name", "username", "recent"],
                                variable=self.sort_var,
                                width=300).pack(anchor="w", padx=14)

        ctk.CTkLabel(self.tabs.tab(t),
                     text="Restart SAS to apply appearance/theme changes.",
                     font=("Segoe UI", 10), text_color="#555"
                     ).pack(anchor="w", padx=14, pady=(10, 0))

    def _tab_steam(self):
        t = "Steam"
        self._lbl(t, "Steam install path")
        self.steam_path_var = ctk.StringVar(value=self.settings["steam_path"])
        ctk.CTkEntry(self.tabs.tab(t), textvariable=self.steam_path_var,
                     width=440, height=32).pack(anchor="w", padx=14)

        self._lbl(t, "Extra launch arguments",
                  "Appended every time Steam launches.  e.g.  -silent  -noverifyfiles")
        self.args_var = ctk.StringVar(value=self.settings["launch_args"])
        ctk.CTkEntry(self.tabs.tab(t), textvariable=self.args_var,
                     width=440, height=32).pack(anchor="w", padx=14)

    def _tab_autologin(self):
        t = "Auto Login"
        ctk.CTkLabel(self.tabs.tab(t),
                     text="Automatically switch to a chosen account when SAS starts.",
                     font=("Segoe UI", 11), text_color="#888",
                     wraplength=420
                     ).pack(padx=14, pady=(16, 10), anchor="w")

        accounts = ["(disabled)"] + list(self.steam_accounts.keys())
        current  = self.settings.get("auto_login", "") or "(disabled)"
        self.autologin_var = ctk.StringVar(value=current)
        ctk.CTkOptionMenu(self.tabs.tab(t),
                           values=accounts,
                           variable=self.autologin_var,
                           width=280
                           ).pack(anchor="w", padx=14)

    def _tab_about(self):
        t = "About"
        ctk.CTkLabel(self.tabs.tab(t),
                     text="SAS — Steam Account Switcher",
                     font=("Segoe UI", 14, "bold")
                     ).pack(pady=(28, 6))
        ctk.CTkLabel(self.tabs.tab(t), text=f"Version {VERSION}",
                     font=("Segoe UI", 12), text_color="#888").pack()
        ctk.CTkLabel(self.tabs.tab(t),
                     text="Built with Python 3 + CustomTkinter\nNo data is ever sent anywhere.",
                     font=("Segoe UI", 11), text_color="#666",
                     justify="center").pack(pady=14)

    def _save(self):
        self.settings["minimize_on_switch"] = self.minimize_var.get()
        self.settings["close_on_switch"]    = self.close_var.get()
        self.settings["appearance"]         = self.appearance_var.get()
        self.settings["theme"]              = self.theme_var.get()
        self.settings["sort_by"]            = self.sort_var.get()
        self.settings["steam_path"]         = self.steam_path_var.get().strip()
        self.settings["launch_args"]        = self.args_var.get().strip()
        al = self.autologin_var.get()
        self.settings["auto_login"] = "" if al == "(disabled)" else al
        try:
            self.settings["kill_wait"] = int(self.wait_var.get())
        except ValueError:
            self.settings["kill_wait"] = 4
        self.on_save(self.settings)
        self.destroy()


# ── Main App ──────────────────────────────────────────────────────────────────

class SASApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.settings        = load_settings()
        self.steam_accounts  = {}
        self.manual_accounts = {}

        ctk.set_appearance_mode(self.settings["appearance"])
        ctk.set_default_color_theme(self.settings["theme"])

        self.title(f"SAS — Steam Account Switcher  v{VERSION}")
        self.geometry("600x620")
        self.resizable(True, True)
        self.minsize(540, 480)

        self._build_ui()
        self._load_all()

        # Auto login
        if self.settings.get("auto_login"):
            self.after(600, lambda: self._do_switch(self.settings["auto_login"]))

    def _build_ui(self):
        # ── Header
        header = ctk.CTkFrame(self, height=54, corner_radius=0, fg_color="#0d1117")
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="Steam Account Switcher",
                     font=("Segoe UI", 15, "bold")
                     ).pack(side="left", padx=18)

        ctk.CTkButton(header, text="⚙  Settings",
                       width=94, height=30,
                       font=("Segoe UI", 11),
                       fg_color="#1a1a2e",
                       hover_color="#2a2a4e",
                       command=self._open_settings
                       ).pack(side="right", padx=12)

        ctk.CTkButton(header, text="Export",
                       width=68, height=30,
                       font=("Segoe UI", 11),
                       fg_color="#1a1a2e",
                       hover_color="#2a2a4e",
                       command=self._export
                       ).pack(side="right", padx=2)

        ctk.CTkButton(header, text="Import",
                       width=68, height=30,
                       font=("Segoe UI", 11),
                       fg_color="#1a1a2e",
                       hover_color="#2a2a4e",
                       command=self._import
                       ).pack(side="right", padx=2)

        # ── Search + sort bar
        topbar = ctk.CTkFrame(self, fg_color="transparent")
        topbar.pack(fill="x", padx=14, pady=(12, 4))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._render())
        ctk.CTkEntry(topbar, textvariable=self.search_var,
                     placeholder_text="Search accounts...",
                     height=34).pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.sort_var_ui = ctk.StringVar(value=self.settings.get("sort_by", "name"))
        ctk.CTkOptionMenu(topbar,
                           values=["name", "username", "recent"],
                           variable=self.sort_var_ui,
                           width=110, height=34,
                           command=lambda _: self._render()
                           ).pack(side="right")

        # ── Steam section
        ctk.CTkLabel(self, text="STEAM ACCOUNTS",
                     font=("Segoe UI", 10), text_color="#555"
                     ).pack(anchor="w", padx=18, pady=(10, 3))

        self.steam_scroll = ctk.CTkScrollableFrame(self, height=200, corner_radius=8,
                                                    fg_color="transparent")
        self.steam_scroll.pack(fill="x", padx=14)

        ctk.CTkFrame(self, height=1, fg_color="#1e1e1e").pack(fill="x", padx=14, pady=10)

        # ── Manual section
        mh = ctk.CTkFrame(self, fg_color="transparent")
        mh.pack(fill="x", padx=18)
        ctk.CTkLabel(mh, text="MANUAL ACCOUNTS",
                     font=("Segoe UI", 10), text_color="#555"
                     ).pack(side="left")
        ctk.CTkButton(mh, text="+ Add Account",
                       width=110, height=24,
                       font=("Segoe UI", 11),
                       command=self._open_add
                       ).pack(side="right")

        self.manual_scroll = ctk.CTkScrollableFrame(self, height=160, corner_radius=8,
                                                     fg_color="transparent")
        self.manual_scroll.pack(fill="x", padx=14, pady=(6, 0))

        # ── Status bar
        bar = ctk.CTkFrame(self, height=32, corner_radius=0, fg_color="#0d1117")
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        self.status_var = ctk.StringVar(value="Ready")
        ctk.CTkLabel(bar, textvariable=self.status_var,
                     font=("Segoe UI", 10), text_color="#555"
                     ).pack(side="left", padx=14)
        ctk.CTkButton(bar, text="↻ Refresh",
                       width=72, height=22,
                       font=("Segoe UI", 10),
                       command=self._load_all
                       ).pack(side="right", padx=10, pady=4)

    # ── Data ──────────────────────────────────────────────────────────────────

    def _load_all(self):
        self.steam_accounts  = parse_accounts()
        self.manual_accounts = load_manual()
        self._render()
        total = len(self.steam_accounts) + len(self.manual_accounts)
        self.status_var.set(f"{total} account{'s' if total != 1 else ''} loaded")

    def _sorted_steam(self):
        s = self.sort_var_ui.get()
        items = list(self.steam_accounts.items())
        if s == "name":
            items.sort(key=lambda x: x[1]["persona"].lower())
        elif s == "username":
            items.sort(key=lambda x: x[0].lower())
        elif s == "recent":
            items.sort(key=lambda x: x[1]["recent"], reverse=True)
        return items

    def _render(self):
        q = self.search_var.get().lower()

        for w in self.steam_scroll.winfo_children():
            w.destroy()
        for w in self.manual_scroll.winfo_children():
            w.destroy()

        # Steam accounts
        filtered = [(u, d) for u, d in self._sorted_steam()
                    if q in u.lower() or q in d["persona"].lower()]

        if filtered:
            for u, d in filtered:
                AccountRow(self.steam_scroll, u, d["persona"], d["steamid"],
                           is_active=d["recent"] == "1",
                           is_manual=False,
                           note="",
                           on_switch=self._do_switch,
                           on_edit=None,
                           on_delete=None,
                           on_copy_id=self._copy_steamid,
                           on_profile=self._open_profile,
                           fg_color="#13171f"
                           ).pack(fill="x", pady=2)
        else:
            ctk.CTkLabel(self.steam_scroll, text="No Steam accounts found.",
                         font=("Segoe UI", 11), text_color="#555"
                         ).pack(pady=10)

        # Manual accounts
        fm = {k: v for k, v in self.manual_accounts.items() if q in k.lower()}
        if fm:
            for u, d in fm.items():
                AccountRow(self.manual_scroll, u, u, "",
                           is_active=False,
                           is_manual=True,
                           note=d.get("note", ""),
                           on_switch=self._do_switch,
                           on_edit=self._open_edit,
                           on_delete=self._delete_manual,
                           on_copy_id=None,
                           on_profile=None,
                           fg_color="#13171f"
                           ).pack(fill="x", pady=2)
        else:
            ctk.CTkLabel(self.manual_scroll, text="No manual accounts added yet.",
                         font=("Segoe UI", 11), text_color="#555"
                         ).pack(pady=10)

    # ── Manual account CRUD ───────────────────────────────────────────────────

    def _open_add(self):
        AccountDialog(self, on_save=self._save_manual)

    def _open_edit(self, username):
        d = self.manual_accounts.get(username, {})
        AccountDialog(self, on_save=self._save_manual,
                      username=username,
                      password=d.get("password", ""),
                      note=d.get("note", ""))

    def _save_manual(self, old, new, password, note):
        if old and old != new:
            self.manual_accounts.pop(old, None)
        self.manual_accounts[new] = {"password": password, "note": note}
        save_manual(self.manual_accounts)
        self._render()
        self.status_var.set(f"Account '{new}' saved.")

    def _delete_manual(self, username):
        self.manual_accounts.pop(username, None)
        save_manual(self.manual_accounts)
        self._render()
        self.status_var.set(f"Account '{username}' removed.")

    # ── Import / Export ───────────────────────────────────────────────────────

    def _export(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile="sas_accounts_backup.json"
        )
        if path:
            with open(path, "w") as f:
                json.dump(self.manual_accounts, f, indent=2)
            self.status_var.set(f"Exported to {os.path.basename(path)}")

    def _import(self):
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if path:
            with open(path) as f:
                imported = json.load(f)
            self.manual_accounts.update(imported)
            save_manual(self.manual_accounts)
            self._render()
            self.status_var.set(f"Imported {len(imported)} account(s).")

    # ── Steam profile / SteamID ───────────────────────────────────────────────

    def _copy_steamid(self, steamid):
        self.clipboard_clear()
        self.clipboard_append(steamid)
        self.status_var.set(f"SteamID copied: {steamid}")

    def _open_profile(self, steamid):
        webbrowser.open(f"https://steamcommunity.com/profiles/{steamid}")

    # ── Settings ──────────────────────────────────────────────────────────────

    def _open_settings(self):
        SettingsWindow(self, self.settings, self.steam_accounts,
                       on_save=self._apply_settings)

    def _apply_settings(self, s):
        self.settings = s
        save_settings(s)
        ctk.set_appearance_mode(s["appearance"])
        self.sort_var_ui.set(s["sort_by"])
        self._render()
        self.status_var.set("Settings saved.")

    # ── Switch ────────────────────────────────────────────────────────────────

    def _do_switch(self, username):
        if username not in self.steam_accounts and username not in self.manual_accounts:
            self.status_var.set(f"Account '{username}' not found.")
            return

        self.status_var.set(f"Switching to {username}...")

        def run():
            is_manual = username in self.manual_accounts
            steam_exe = os.path.join(self.settings["steam_path"], "steam.exe")
            extra     = self.settings["launch_args"].split() if self.settings["launch_args"] else []

            subprocess.call(["taskkill", "/F", "/IM", "steam.exe"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(self.settings["kill_wait"])

            if is_manual:
                pwd = self.manual_accounts[username]["password"]
                subprocess.Popen([steam_exe, "-login", username, pwd] + extra)
            else:
                patch_vdf(username)
                set_registry(username)
                subprocess.Popen([steam_exe] + extra)

            persona = self.steam_accounts.get(username, {}).get("persona", username)
            self.after(0, lambda: self.status_var.set(f"Steam launched as {persona}"))

            if self.settings["minimize_on_switch"]:
                self.after(0, self.iconify)
            if self.settings["close_on_switch"]:
                self.after(1500, self.destroy)

            self.after(1200, self._load_all)

        threading.Thread(target=run, daemon=True).start()


if __name__ == "__main__":
    app = SASApp()
    app.mainloop()
