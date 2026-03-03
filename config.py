import os

STEAM_PATH = r"C:\Program Files (x86)\Steam"
STEAM_EXE  = os.path.join(STEAM_PATH, "steam.exe")
VDF_PATH   = os.path.join(STEAM_PATH, "config", "loginusers.vdf")
REG_PATH   = r"Software\Valve\Steam"

VERSION    = "0.1-beta"
APP_NAME   = "SAS"