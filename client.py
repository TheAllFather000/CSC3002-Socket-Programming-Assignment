"""
    python client.py [server_ip] [server_port]
    Default: 196.47.211.33, port 5958
"""

import socket, os, threading, hashlib, sys, json, time
import colorist

#host = '196.47.211.33'
host = '127.0.0.1'
#host = 'schaat.duckdns.org'
port = 5958

# So we can run on the same machine without clashing
file_listen_port = 6000

if len(sys.argv) >= 2:
    host = sys.argv[1]

if len(sys.argv) >= 3:
    port = int(sys.argv[2])

if len(sys.argv) >= 4:
    file_listen_port = int(sys.argv[3])

chunk_size = 65536
presence_port = 5555
udp_port = 5960

username = None
pending_files = {}
logged_in = False
running = True

# Thread safe printing (prevents mixed terminal output)
print_lock = threading.Lock()

def safe_print(*args, **kwargs):
    with print_lock:
        print("\r", end="")
        print(*args, **kwargs)


# ANSI helpers

RESET = "\033[0m"
BOLD  = "\033[1m"
CYAN  = "\033[96m"   # bright cyan  – input labels & swatch numbers
BLUE  = "\033[94m"   # bright blue  – box-drawing chrome & prompt arrow

def _c(text, *codes):
    """Wrap text with one or more ANSI codes then reset."""
    return "".join(codes) + text + RESET


# Colour (messages + file transfers only)

COLOURS = {
    "1": (colorist.Color.RED,     "\033[91m", "Red"),
    "2": (colorist.Color.GREEN,   "\033[92m", "Green"),
    "3": (colorist.Color.YELLOW,  "\033[93m", "Yellow"),
    "4": (colorist.Color.MAGENTA, "\033[95m", "Magenta"),
    "5": (colorist.Color.CYAN,    "\033[96m", "Cyan"),
}

user_colour = ""

def coloured(text):
    if user_colour:
        return f"{user_colour}{text}{RESET}"
    return text

def render_coloured(text, ansi_code):
    if ansi_code:
        return f"{ansi_code}{text}{RESET}"
    return text


# Dynamic prompt

def prompt():
    """Plain '> ' before login; '@username ❯ ' in cyan/blue after."""
    if username:
        return _c(f"@{username}", CYAN, BOLD) + _c(" ❯ ", BLUE, BOLD)
    return "> "


# Styled command table

def print_help():
    cmds = [
        ("login",          "Log in to the server"),
        ("create_account", "Register a new account"),
        ("create_group",   "Create a new group"),
        ("private",        "Send a private message"),
        ("message_group",  "Send a message to a group"),
        ("add_member",     "Add a member to a group"),
        ("file",           "Send a file to a user"),
        ("ping",           "Ping the server"),
        ("logout",         "Log out and exit"),
        ("help / ?",       "Show this command list"),
    ]
    print()
    print(_c("  ┌─ Commands " + "─" * 42 + "┐", BLUE))
    for cmd, desc in cmds:
        print(_c("  │  ", BLUE) + _c(f"{cmd:<18}", CYAN, BOLD) + desc)
    print(_c("  └" + "─" * 53 + "┘", BLUE))
    print()


# Benchmarking / performance logging

BENCH_FILE = "benchmark_log.txt"
bench_lock = threading.Lock()

def log_bench(event: str, detail: str, latency_ms: float = None,
              filesize_bytes: int = None, duration_s: float = None):

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    throughput = ""
    if filesize_bytes and duration_s and duration_s > 0:
        mb_s = (filesize_bytes / (1024 * 1024)) / duration_s
        throughput = f"  throughput={mb_s:.4f} MB/s"

    lat_str  = f"  latency={latency_ms:.2f} ms" if latency_ms is not None else ""
    size_str = f"  size={filesize_bytes} bytes"  if filesize_bytes is not None else ""

    line = f"[{timestamp}]  event={event}  user={username or '?'}  {detail}{lat_str}{size_str}{throughput}\n"

    with bench_lock:
        with open(BENCH_FILE, "a") as f:
            f.write(line)


# TCP socket

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    client.connect((host, port))
except Exception as e:
    print(f"Unable to connect to server: {e}")
    sys.exit()


# File listener thread for incoming P2P file transfers

def file_listener():

    file_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    file_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    file_server.bind(('0.0.0.0', file_listen_port))
    file_server.listen(5)

    while running:
        try:
            peer_sock, peer_addr = file_server.accept()
            threading.Thread(
                target=receive_file,
                args=(peer_sock, peer_addr),
                daemon=True
            ).start()
        except:
            break


def receive_file(peer_sock, peer_addr):

    filename = "unknown"
    filesize = 0
    t_start  = time.time()

    try:

        header = b''

        while b'\n' not in header:
            header += peer_sock.recv(1024)

        header_line, leftover = header.split(b'\n', 1)
        filename, filesize, expected_md5 = header_line.decode().split('|')
        filesize = int(filesize)

        safe_print(coloured(f"\n[File incoming] '{filename}' ({filesize} bytes) from {peer_addr[0]}"))

        save_path = f"received_{filename}"

        received = len(leftover)
        md5_hash = hashlib.md5()

        with open(save_path, 'wb') as f:

            if leftover:
                f.write(leftover)
                md5_hash.update(leftover)

            while received < filesize:

                chunk = peer_sock.recv(chunk_size)

                if not chunk:
                    break

                f.write(chunk)
                md5_hash.update(chunk)
                received += len(chunk)

        duration = time.time() - t_start

        if md5_hash.hexdigest() == expected_md5:

            safe_print(coloured(f"[File received] Saved as '{save_path}' — MD5 verified."))

            log_bench("file_receive",
                      f"file={filename} from={peer_addr[0]} status=ok",
                      filesize_bytes=filesize,
                      duration_s=duration)

        else:

            os.remove(save_path)
            safe_print(coloured("[File error] MD5 mismatch — file corrupted."))

    finally:
        peer_sock.close()


# File sender

def send_file(peer_ip, peer_port, filepath):

    peer_sock = None
    t_start   = time.time()

    try:

        md5_hash = hashlib.md5()

        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(chunk_size), b''):
                md5_hash.update(chunk)

        file_md5 = md5_hash.hexdigest()

        peer_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        peer_sock.connect((peer_ip, int(peer_port)))

        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)

        header = f"{filename}|{filesize}|{file_md5}\n".encode()

        peer_sock.sendall(header)

        with open(filepath, 'rb') as f:

            while chunk := f.read(chunk_size):
                peer_sock.sendall(chunk)

        duration = time.time() - t_start

        safe_print(coloured(f"[File sent] '{filename}' -> {peer_ip}:{peer_port}"))

        log_bench("file_send",
                  f"file={filename} to={peer_ip}:{peer_port} status=ok",
                  filesize_bytes=filesize,
                  duration_s=duration)

    finally:

        if peer_sock:
            peer_sock.close()


# Server message receiver

def receive():

    global logged_in

    buf = ""

    def iter_json(chunk):
        nonlocal buf
        buf += chunk
        while buf:
            buf = buf.lstrip()
            if not buf:
                break
            if buf[0] != "{":
                idx = buf.find("{")
                if idx == -1:
                    buf = ""
                else:
                    buf = buf[idx:]
                continue

            depth, in_str, escape = 0, False, False
            for i, ch in enumerate(buf):
                if escape:
                    escape = False
                    continue
                if ch == "\\" and in_str:
                    escape = True
                    continue
                if ch == '"':
                    in_str = not in_str
                    continue
                if in_str:
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        yield json.loads(buf[:i+1])
                        buf = buf[i+1:]
                        break
            else:
                break

    while running:

        try:

            raw = client.recv(4096).decode("ascii", errors="replace")

            if not raw:
                break

            for data in iter_json(raw):

                msg_type = data.get("command", "")

                if msg_type == "login_success":

                    if not logged_in:
                        logged_in = True
                        safe_print("[Auth] Login successful!")
                        safe_print(_c("  Please select a command (type 'help' or '?' to see options).", CYAN))
                        print(prompt(), end="", flush=True)
                        threading.Thread(target=file_listener, daemon=True).start()
                        threading.Thread(target=presence_ping, daemon=True).start()

                elif msg_type == "login_fail":

                    safe_print("[Auth] Login failed. Check your credentials.")

                elif msg_type == "account_created":

                    safe_print("[Auth] Account created successfully.")

                elif msg_type == "system":

                    safe_print(f"[SYSTEM]: {data.get('body', '')}")

                elif msg_type == "text":

                    sender = data.get("sender", "?")
                    body   = data.get("body", "")
                    ansi   = data.get("colour", "")

                    safe_print(render_coloured(f"[{sender}]: {body}", ansi))
                    print(prompt(), end="", flush=True)

                elif msg_type == "file_ready":

                    filepath = pending_files.pop(data["receiver"], None)

                    if filepath:

                        threading.Thread(
                            target=send_file,
                            args=(data["peer_ip"], data["peer_port"], filepath),
                            daemon=True
                        ).start()

                    print(prompt(), end="", flush=True)

        except:
            safe_print("Disconnected from server.")
            break


# UDP presence ping

def presence_ping():

    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    while running:

        payload = json.dumps({"type": "ping", "user": username})
        udp_sock.sendto(payload.encode(), (host, udp_port))
        time.sleep(5)


# Colour picker (called once at login)

def pick_colour():

    global user_colour

    print()
    print(_c("  ┌─ Choose your message colour " + "─" * 20 + "┐", BLUE))

    for k, (colour_code, ansi_code, name) in COLOURS.items():
        swatch = f"{ansi_code}■■■{RESET}"
        print(_c("  │  ", BLUE) + f"  {_c(k, CYAN, BOLD)})  {swatch}  {ansi_code}{name}{RESET}")

    print(_c("  │  ", BLUE) + f"  {_c('0', CYAN, BOLD)})  No colour")
    print(_c("  └" + "─" * 50 + "┘", BLUE))

    choice = input(_c("  Enter number: ", CYAN))

    if choice in COLOURS:
        user_colour = COLOURS[choice][1]
        print(f"  Colour set to {COLOURS[choice][2]}.")
    else:
        user_colour = ""
        print("  No colour selected.")


# ASCII banner

BANNER = r"""
  #####   #####  #     #    #    #######
 #     # #     # #     #   # #      #
 #       #       #     #  #   #     #
  #####  #       ####### #     #    #
       # #       #     # #######    #
 #     # #     # #     # #     #    #
  #####   #####  #     # #     #    #
"""

def print_banner():
    print(_c(BANNER, CYAN, BOLD))


# Main loop

if __name__ == "__main__":

    threading.Thread(target=receive, daemon=True).start()

    print_banner()
    print_help()

    while True:

        try:
            user_input = input(prompt()).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            print(_c("  Type 'help' or '?' to see available commands.", CYAN))
            continue

        # login
        if user_input.startswith("login"):

            username = input(_c("  Username: ", CYAN))
            password = input(_c("  Password: ", CYAN))

            pick_colour()

            payload = json.dumps({
                "command": "login",
                "username": username,
                "password": password,
                "file_listen_port": file_listen_port,
                "colour": user_colour
            })

            client.send(payload.encode())

        # create_account
        elif user_input.startswith("create_account"):

            username = input(_c("  Username: ", CYAN))
            password = input(_c("  Password: ", CYAN))

            pick_colour()

            payload = json.dumps({
                "command": "create_account",
                "username": username,
                "password": password
            })

            client.send(payload.encode())

        # create_group
        elif user_input.startswith("create_group"):

            group = input(_c("  Group name: ", CYAN))

            payload = json.dumps({
                "command": "create_group",
                "username": username,
                "group": group
            })

            client.send(payload.encode())

        # private message
        elif user_input.startswith("private"):

            recipient = input(_c("  Recipient: ", CYAN))
            msg       = input(_c("  Message: ", CYAN))

            payload = json.dumps({
                "command": "private",
                "sender": username,
                "recipient": recipient,
                "body": msg,
                "colour": user_colour,
                "sent_at": time.time()
            })

            client.send(payload.encode())
            safe_print(f"[{username}] -> [{recipient}]: {msg}")

        # message_group
        elif user_input.startswith("message_group"):

            group = input(_c("  Group name: ", CYAN))
            msg   = input(_c("  Message: ", CYAN))

            payload = json.dumps({
                "command": "message_group",
                "sender": username,
                "group": group,
                "body": msg,
                "colour": user_colour,
                "sent_at": time.time()
            })

            client.send(payload.encode())
            safe_print(f"[{username}] -> [{group}]: {msg}")

        # add_member
        elif user_input.startswith("add_member"):

            group  = input(_c("  Group name: ", CYAN))
            member = input(_c("  Username to add: ", CYAN))

            payload = json.dumps({
                "command": "add_member",
                "username": username,
                "group": group,
                "member": member
            })

            client.send(payload.encode())

        # file transfer
        elif user_input.startswith("file"):

            filepath = input(_c("  Filepath: ", CYAN))
            receiver = input(_c("  Receiver: ", CYAN))

            if not os.path.exists(filepath):
                print(_c("  [Error] File not found.", CYAN))
                continue

            pending_files[receiver] = filepath

            payload = json.dumps({
                "command": "file_request",
                "sender": username,
                "receiver": receiver,
                "filename": os.path.basename(filepath),
                "filesize": os.path.getsize(filepath),
                "file_listen_port": file_listen_port
            })

            client.send(payload.encode())
            print(coloured(f"[File] Requesting transfer of '{os.path.basename(filepath)}' to {receiver}..."))
            print(prompt(), end="", flush=True)

        # ping
        elif user_input.startswith("ping"):

            payload = json.dumps({
                "command": "ping",
                "username": username,
                "sent_at": time.time()
            })

            client.send(payload.encode())

        # help
        elif user_input in ("help", "?", "h"):

            print_help()

        # logout
        elif user_input == "logout":

            payload = json.dumps({
                "command": "logout",
                "username": username
            })

            client.send(payload.encode())

            running = False
            client.close()

            # Give daemon threads a moment to finish before the interpreter
            # shuts down, preventing the buffered stdout lock error.
            time.sleep(0.3)
            os._exit(0)

        # unknown command
        else:

            print(_c(f"  Unknown command '{user_input}'. Type 'help' or '?' for a list of commands.", CYAN))