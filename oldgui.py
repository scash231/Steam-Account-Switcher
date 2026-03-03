#Old Gui

import os
import sys
import threading
import customtkinter as ctk
from PIL import Image, ImageTk

from config import VERSION, APP_NAME
from SAS import parse_accounts, patch_vdf, set_registry, kill_steam, launch_steam

# ── Theme ─────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Account Card ──────────────────────────────────────────────────────────────

class AccountCard(ctk.CTkFrame):
    def __init__(self, master, username, account_data, on_switch, **kwargs):
        super().__init__(master, corner_radius=10, **kwargs)

        self.username     = username
        self.account_data = account_data
        self.on_switch    = on_switch

        is_active = account_data["recent"] == "1"
        no_session = account_data["remember"] == "0"

        # Left color bar for active account
        bar_color = "#1db954" if is_active else "#2b2b2b"
        bar = ctk.CTkFrame(self, width=6, corner_radius=0, fg_color=bar_color)
        bar.pack(side="left", fill="y", padx=(0, 10))

        # Avatar placeholder
        avatar_frame = ctk.CTkFrame(self, width=48, height=48, corner_radius=24,
                                     fg_color="#1a6496")
        avatar_frame.pack(side="left", padx=(0, 12), pady=10)
        avatar_frame.pack_propagate(False)
        initials = account_data["persona"][:2].upper()
        ctk.CTkLabel(avatar_frame, text=initials, font=ctk.CTkFont(size=16, weight="bold"),
                     text_color="white").place(relx=0.5, rely=0.5, anchor="center")

        # Name info
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, pady=10)

        ctk.CTkLabel(info_frame, text=account_data["persona"],
                     font=ctk.CTkFont(size=14, weight="bold"),
                     anchor="w").pack(anchor="w")

        ctk.CTkLabel(info_frame, text=f"@{username}",
                     font=ctk.CTkFont(size=11),
                     text_color="#888888", anchor="w").pack(anchor="w")

        if no_session:
            ctk.CTkLabel(info_frame, text="⚠ No saved session",
                         font=ctk.CTkFont(size=10),
                         text_color="#e08000").pack(anchor="w")

        # Right side — badge + button
        right_frame = ctk.CTkFrame(self, fg_color="transparent")
        right_frame.pack(side="right", padx=12, pady=10)

        if is_active:
            ctk.CTkLabel(right_frame, text="● Active",
                         font=ctk.CTkFont(size=11),
                         text_color="#1db954").pack(anchor="e", pady=(0, 4))

        btn_text  = "Current" if is_active else "Switch"
        btn_color = "#2a4a2a" if is_active else "#1f538d"
        btn = ctk.CTkButton(right_frame, text=btn_text, width=80,
                             fg_color=btn_color,
                             state="disabled" if is_active else "normal",
                             command=lambda: self.on_switch(username))
        btn.pack(anchor="e")


# ── Main Window ───────────────────────────────────────────────────────────────

class SASApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"{APP_NAME} — v{VERSION}")
        self.geometry("520x600")
        self.resizable(False, False)
        self._build_ui()
        self._load_accounts()

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, height=70, corner_radius=0, fg_color="#161b22")
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="🎮  Steam Account Switcher",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left", padx=20)
        ctk.CTkLabel(header, text=f"v{VERSION}",
                     font=ctk.CTkFont(size=11),
                     text_color="#888888").pack(side="right", padx=20)

        # Search bar
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", padx=20, pady=(15, 5))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._on_search)
        ctk.CTkEntry(search_frame, textvariable=self.search_var,
                     placeholder_text="🔍  Search accounts...",
                     height=36).pack(fill="x")

        # Account list (scrollable)
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Saved Accounts",
                                                    corner_radius=10)
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=(5, 10))

        # Status bar
        self.status_var = ctk.StringVar(value="Ready")
        status_bar = ctk.CTkFrame(self, height=32, corner_radius=0, fg_color="#0d1117")
        status_bar.pack(fill="x", side="bottom")
        status_bar.pack_propagate(False)
        ctk.CTkLabel(status_bar, textvariable=self.status_var,
                     font=ctk.CTkFont(size=11),
                     text_color="#888888").pack(side="left", padx=12)

        # Refresh button
        ctk.CTkButton(status_bar, text="↻ Refresh", width=70, height=22,
                       font=ctk.CTkFont(size=11),
                       command=self._load_accounts).pack(side="right", padx=8, pady=4)

    def _load_accounts(self):
        self.accounts = parse_accounts()
        self._render_accounts(self.accounts)
        count = len(self.accounts)
        self.status_var.set(f"{count} account{'s' if count != 1 else ''} found")

    def _render_accounts(self, accounts):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        if not accounts:
            ctk.CTkLabel(self.scroll_frame, text="No accounts found.",
                         text_color="#888888").pack(pady=20)
            return

        for username, data in accounts.items():
            card = AccountCard(self.scroll_frame, username, data,
                               on_switch=self._confirm_switch,
                               fg_color="#1e1e2e")
            card.pack(fill="x", pady=4)

    def _on_search(self, *args):
        query = self.search_var.get().lower()
        filtered = {
            k: v for k, v in self.accounts.items()
            if query in k.lower() or query in v["persona"].lower()
        }
        self._render_accounts(filtered)

    def _confirm_switch(self, username):
        persona = self.accounts[username]["persona"]

        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm Switch")
        dialog.geometry("320x150")
        dialog.resizable(False, False)
        dialog.grab_set()

        ctk.CTkLabel(dialog,
                     text=f"Switch to {persona}?\nSteam will be restarted.",
                     font=ctk.CTkFont(size=13), justify="center").pack(pady=25)

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack()

        ctk.CTkButton(btn_frame, text="Cancel", width=100, fg_color="#3a3a3a",
                       command=dialog.destroy).pack(side="left", padx=8)
        ctk.CTkButton(btn_frame, text="Switch ✓", width=100,
                       command=lambda: [dialog.destroy(),
                                        self._do_switch(username)]).pack(side="left", padx=8)

    def _do_switch(self, username):
        self.status_var.set(f"Switching to {username}...")

        def run():
            kill_steam()
            patch_vdf(username)
            set_registry(username)
            launch_steam()
            self.after(0, lambda: self.status_var.set(
                f"✓ Launched Steam as {self.accounts[username]['persona']}"))
            self.after(500, self._load_accounts)

        threading.Thread(target=run, daemon=True).start()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = SASApp()
    app.mainloop()
