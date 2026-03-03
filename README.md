# SAS - Steam Account Switcher

A lightweight Python tool for switching between Steam accounts fast — no 
passwords, no Steam Guard codes. Just pick an account and go.

---

## Requirements

- Windows
- Python 3.8+
- Steam installed with at least one saved account
- customtkinter and Pillow installed (see below)

---

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/yourname/Steam-Account-Switcher.git
cd Steam-Account-Switcher
```

**2. Install dependencies**
```bash
pip install customtkinter pillow
```

**3. Check your Steam path**

Open `config.py` and make sure `STEAM_PATH` points to where Steam is installed.
Default is `C:\Program Files (x86)\Steam` — if yours is somewhere else, change it.

---

## Usage

**GUI version (recommended)**
```bash
python gui.py
```

**CLI version**
```bash
# Interactive menu
python SAS.py

# Direct switch
python SAS.py yourAccountName
```

---

## Important

Before using SAS, make sure you have logged into each account at least once 
with "Remember me" checked in Steam. SAS does not store or handle passwords — 
it only switches between sessions Steam has already saved.

Accounts marked with a warning in the UI have no saved session and will 
require a manual login.

---

## Project Structure

```
Steam-Account-Switcher/
├── SAS.py          # Core logic (CLI entry point)
├── gui.py          # GUI built with customtkinter
├── config.py       # Steam path and app settings
└── README.md
```

---

## Version

v0.1-beta