import socket
import threading
import paramiko
import os
import time
import json
import requests
import urllib3
from colorama import Fore, init, Style

# --- INITIALISIERUNG ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
init(autoreset=True)

USER_DB = "users_db.json"
BOT_FILE = "webhooks.txt"
HOST_KEY = paramiko.RSAKey.generate(2048)
USERS_ONLINE = {}

def load_db():
    if os.path.exists(USER_DB):
        try:
            with open(USER_DB, "r", encoding='utf-8') as f:
                data = json.load(f)
                return data if data else {"root": {"pw": "nevin123", "role": "admin", "conns": 10, "mtime": 3600, "cd": 0}}
        except: pass
    return {"root": {"pw": "nevin123", "role": "admin", "conns": 10, "mtime": 3600, "cd": 0}}

def save_db(db):
    try:
        with open(USER_DB, "w", encoding='utf-8') as f: json.dump(db, f, indent=4)
    except: pass

def get_bots_count():
    if os.path.exists(BOT_FILE):
        try:
            with open(BOT_FILE, "r") as f: 
                return len([l.strip() for l in f if l.strip().startswith("http")])
        except: pass
    return 0

# --- DIE BIG BIG BIG RAKETE (Original Style) ---
def mega_rocket_anim(chan):
    frames = [
        f"""{Fore.RED}
                 .
                / \\
               /   \\
              /     \\
             |       |
             |   N   |
             |   I   |
             |   G   |
             |   G   |
             |   A   |
             |       |
            /|       |\\
           / |       | \\
          |  |       |  |
           '-|       |-'
             |       |""",
        f"""{Fore.YELLOW}
                 ^
                / \\
               /   \\
              |  N  |
              |  I  |
              |  G  |
              |  G  |
              |  A  |
             /|     |\\
            | |     | |
             '-|   |-'
               |   |
              (     )
             (  V V  )
              )  ^  ( """,
        f"""{Fore.WHITE}
                 ^
                / \\
               |   |
               | N |
               | I |
              /| G |\\
             | | G | |
              '-|A|-'
               (   )
              ( V V )
             (  ^ ^  )
            (  BIG   )
           (  LAUNCH  )
          (   READY   )
         (  STRIKE!!!  )"""
    ]
    try:
        for frame in frames:
            chan.send(b"\033[H\033[2J") 
            chan.send(frame.replace('\n', '\r\n').encode())
            time.sleep(0.12)
        time.sleep(0.5)
    except: pass

def get_nigganet_header():
    return f"""{Fore.CYAN}
 ███╗   ██╗██╗ ██████╗  ██████╗  █████╗ ███╗   ██╗███████╗████████╗
 ████╗  ██║██║██╔════╝ ██╔════╝ ██╔══██╗████╗  ██║██╔════╝╚══██╔══╝
 ██╔██╗ ██║██║██║  ███╗██║  ███╗███████║██╔██╗ ██║█████╗     ██║   
 ██║╚██╗██║██║██║   ██║██║   ██║██╔══██║██║╚██╗██║██╔══╝     ██║   
 ██║ ╚████║██║╚██████╔╝╚██████╔╝██║  ██║██║ ╚████║███████╗   ██║   
 ╚═╝  ╚═══╝╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝   ╚═╝
 -------------------------------------------------------------------"""

def get_user_help():
    return f"""{Fore.BLUE}
 ┌──────────────┬────────────────────────────────────────────────┐
 │ {Fore.WHITE}C/CLS/CLEAR  {Fore.BLUE}│ {Fore.WHITE}Clear the terminal screen.                     {Fore.BLUE}│
 │ {Fore.WHITE}H/HELP       {Fore.BLUE}│ {Fore.WHITE}View the full command list.                    {Fore.BLUE}│
 │ {Fore.WHITE}M/METHODS    {Fore.BLUE}│ {Fore.WHITE}View the attack methods.                       {Fore.BLUE}│
 │ {Fore.WHITE}P/PLAN       {Fore.BLUE}│ {Fore.WHITE}View your plan details.                        {Fore.BLUE}│
 └──────────────┴────────────────────────────────────────────────┘"""

def get_methods_banner():
    return f"""
{Fore.CYAN}[L4 - TCP]
{Fore.WHITE} SSH, OVHSTOMP, HANDSHAKE, TCPMIX, FIVEM, SOCKET

{Fore.CYAN}[L4 - UDP]
{Fore.WHITE} DISCORD, DNS, UDPBYPASS, GAMEBOOM, UDP-ARTIC

{Fore.CYAN}[L7 - HTTP]
{Fore.WHITE} HTTP-BROWSER, TLS, CLOUDFLARE, HTTP-ARTIC
"""

def get_plan_banner(user, u_data):
    bots = get_bots_count()
    return f"""
 {Fore.BLUE}┌──────────────────────────────────────────────────────────────┐
 │ {Fore.CYAN}USER PLAN DETAILS{Fore.BLUE}                                            │
 ├────────────────┬─────────────────────────────────────────────┤
 │ {Fore.WHITE}Username       {Fore.BLUE}│ {Fore.YELLOW}{str(user).ljust(44)}{Fore.BLUE} │
 │ {Fore.WHITE}Rank           {Fore.BLUE}│ {Fore.YELLOW}{str(u_data.get('role', 'User')).ljust(44)}{Fore.BLUE} │
 ├────────────────┼─────────────────────────────────────────────┤
 │ {Fore.WHITE}Bots Online    {Fore.BLUE}│ {Fore.GREEN}{str(bots).ljust(44)}{Fore.BLUE} │
 │ {Fore.WHITE}Max Conns      {Fore.BLUE}│ {Fore.GREEN}{str(u_data.get('conns', 1)).ljust(44)}{Fore.BLUE} │
 │ {Fore.WHITE}Max Time       {Fore.BLUE}│ {Fore.GREEN}{str(u_data.get('mtime', 60)).ljust(44)}{Fore.BLUE} │
 │ {Fore.WHITE}Cooldown       {Fore.BLUE}│ {Fore.GREEN}{str(u_data.get('cd', 0)).ljust(44)}{Fore.BLUE} │
 └────────────────┴─────────────────────────────────────────────┘"""

def get_admin_help():
    return f"""{Fore.RED} [ ADMIN CONTROL PANEL ] {Fore.BLUE}
 ┌──────────────┬────────────────────────────────────────────────┐
 │ {Fore.WHITE}USERS ADD    {Fore.BLUE}│ {Fore.WHITE}Add user with Conns/Time/CD.                   {Fore.BLUE}│
 │ {Fore.WHITE}USERS LIST   {Fore.BLUE}│ {Fore.WHITE}List all users in database.                    {Fore.BLUE}│
 │ {Fore.WHITE}BROADCAST    {Fore.BLUE}│ {Fore.WHITE}Send alert to all online users.                {Fore.BLUE}│
 └──────────────┴────────────────────────────────────────────────┘"""

class NiggaNetSSH(paramiko.ServerInterface):
    def __init__(self): self.user = None
    def check_auth_password(self, u, p):
        db = load_db()
        if u in db and db[u]["pw"] == p: self.user = u; return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED
    def check_channel_request(self, k, c): return paramiko.OPEN_SUCCEEDED
    def check_channel_shell_request(self, c): return True
    def check_channel_pty_request(self, *a): return True

def handle_session(sock):
    user = "None"
    try:
        t = paramiko.Transport(sock); t.add_server_key(HOST_KEY)
        server = NiggaNetSSH(); t.start_server(server=server)
        chan = t.accept(30)
        if not chan: return
        user = server.user; USERS_ONLINE[user] = chan
        history = []

        def send_raw(m):
            try: chan.send(m.replace('\n', '\r\n').encode())
            except: pass
        
        def refresh():
            chan.send(b"\033[H\033[2J")
            send_raw(get_nigganet_header() + "\r\n")
            send_raw(f"{Fore.WHITE}[-] NiggaNet | Online: {len(USERS_ONLINE)} | User: {user} [-]\r\n")

        def custom_prompt(p_text):
            send_raw(p_text); buffer = ""; h_index = len(history)
            while True:
                try:
                    char = chan.recv(10)
                    if not char: return None
                    if char in [b'\r', b'\n']:
                        send_raw("\r\n"); 
                        if buffer.strip(): history.append(buffer)
                        return buffer.strip()
                    elif char in [b'\x7f', b'\x08']:
                        if len(buffer) > 0: buffer = buffer[:-1]; send_raw('\x08 \x08')
                    elif char == b'\x1b[A': # Up
                        if h_index > 0:
                            h_index -= 1; send_raw('\x08 \x08' * len(buffer))
                            buffer = history[h_index]; send_raw(buffer)
                    elif char == b'\x1b[B': # Down
                        if h_index < len(history)-1:
                            h_index += 1; send_raw('\x08 \x08' * len(buffer))
                            buffer = history[h_index]; send_raw(buffer)
                    elif len(char) == 1 and char.isascii():
                        c = char.decode(); buffer += c; send_raw(c)
                except: return None

        refresh()

        while True:
            line = custom_prompt(f"{Fore.GREEN}{user}@nigganet » {Fore.WHITE}")
            if line is None: break
            if not line: continue
            
            parts = line.split(); cmd = parts[0].upper()
            db = load_db(); u_data = db.get(user, {})
            is_admin = (u_data.get("role") == "admin" or str(user).lower() == "root")

            if cmd in ["P", "PLAN"]:
                refresh(); send_raw(get_plan_banner(user, u_data) + "\r\n")
            elif cmd in ["M", "METHODS"]:
                refresh(); send_raw(get_methods_banner() + "\r\n")
            elif cmd in ["H", "HELP"]:
                refresh(); send_raw(get_user_help() + "\r\n")
            elif cmd in ["C", "CLS", "CLEAR"]:
                refresh()
            elif cmd == "!ADMIN":
                refresh()
                if is_admin: send_raw(get_admin_help() + "\r\n")
                else: send_raw(f"{Fore.RED}No Permission.\r\n")
            elif cmd == "USERS" and is_admin:
                sub = parts[1].upper() if len(parts) > 1 else ""
                if sub == "ADD":
                    u_n = custom_prompt("User: "); p_n = custom_prompt("Pass: "); u_c = custom_prompt("Conns: "); u_t = custom_prompt("Time: "); u_cd = custom_prompt("CD: ")
                    if all([u_n, p_n, u_c, u_t, u_cd]):
                        db[u_n] = {"pw": p_n, "role": "user", "conns": int(u_c), "mtime": int(u_t), "cd": int(u_cd)}
                        save_db(db); mega_rocket_anim(chan); refresh(); send_raw(f"User {u_n} added!\r\n")
                elif sub == "LIST":
                    refresh(); send_raw(f"{Fore.CYAN}--- USERS ---\r\n")
                    for u in db: send_raw(f"{u} | {db[u].get('role')} | Conns: {db[u].get('conns')}\r\n")
            elif cmd == "BROADCAST" and is_admin:
                msg = " ".join(parts[1:])
                for u in USERS_ONLINE:
                    try: USERS_ONLINE[u].send(f"\r\n{Fore.RED}[ALERT] {msg}\r\n".encode())
                    except: pass
            elif cmd in ["SSH", "OVHSTOMP", "HANDSHAKE", "TCPMIX", "FIVEM", "SOCKET", "DISCORD", "DNS", "UDPBYPASS", "GAMEBOOM", "HTTP-BROWSER", "TLS", "CLOUDFLARE", "UDP-ARTIC", "HTTP-ARTIC"]:
                if len(parts) < 4: send_raw(f"{Fore.RED}Usage: {cmd} <IP> <PORT> <TIME>\r\n")
                else:
                    mega_rocket_anim(chan); refresh(); send_raw(f"{Fore.GREEN}ATTACK SENT SUCCESSFULLY!\r\n")
            elif cmd == "EXIT": break
            else: send_raw(f"Unknown command.\r\n")
    finally:
        if user in USERS_ONLINE: del USERS_ONLINE[user]
        try: sock.close()
        except: pass

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(('0.0.0.0', 2222)); s.listen(100)
    print("NIGGANET CORE FULL LOADED - PORT 2222")
    while True:
        try:
            c, a = s.accept()
            threading.Thread(target=handle_session, args=(c,), daemon=True).start()
        except: pass

if __name__ == "__main__": main()
