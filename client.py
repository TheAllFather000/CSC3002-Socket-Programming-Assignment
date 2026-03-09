"""
    python client.py [server_ip] [server_port]
    Default: 196.47.211.33, port 5958
"""

import socket, os, threading, hashlib, sys, json, time
import colorist

#host = '196.47.211.33'
host = '127.0.0.1'
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
        print(*args, **kwargs)


# Colour (messages + file transfers only)

COLOURS = {
    "1": (colorist.Color.RED, "Red"),
    "2": (colorist.Color.GREEN, "Green"),
    "3": (colorist.Color.YELLOW, "Yellow"),
    "4": (colorist.Color.BLUE, "Blue"),
    "5": (colorist.Color.MAGENTA, "Magenta"),
    "6": (colorist.Color.CYAN, "Cyan"),
    "7": (colorist.Color.WHITE, "White"),
}

RESET = "\033[0m"
user_colour = ""   # set at login; empty string = no colour


def coloured(text):
    # Change text in the user's chosen colour
    if user_colour:
        return f"{user_colour}{text}{RESET}"
    return text


# Benchmarking / performance logging
BENCH_FILE = "benchmark_log.txt"
bench_lock = threading.Lock()

def log_bench(event: str, detail: str, latency_ms: float = None,
              filesize_bytes: int = None, duration_s: float = None):
    """Append one benchmark record to benchmark_log.txt."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    throughput = ""
    if filesize_bytes and duration_s and duration_s > 0:
        mb_s = (filesize_bytes / (1024 * 1024)) / duration_s
        throughput = f"  throughput={mb_s:.4f} MB/s"

    lat_str = f"  latency={latency_ms:.2f} ms" if latency_ms is not None else ""
    size_str = f"  size={filesize_bytes} bytes" if filesize_bytes is not None else ""

    line = f"[{timestamp}]  event={event}  user={username or '?'}  {detail}{lat_str}{size_str}{throughput}\n"

    with bench_lock:
        with open(BENCH_FILE, "a") as f:
            f.write(line)


# Create TCP socket
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Connect to the server
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

    safe_print(f"[File listener running on port {file_listen_port}]")

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
    t_start = time.time()

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
    t_start = time.time()

    try:

        md5_hash = hashlib.md5()

        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(chunk_size), b''):
                md5_hash.update(chunk)

        file_md5 = md5_hash.hexdigest()

        peer_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
        peer_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)

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

    except Exception as e:

        safe_print("File send error:", e)

    finally:

        if peer_sock:
            peer_sock.close()


# Server message receiver
def receive():

    global logged_in

    while running:

        try:

            message = client.recv(4096).decode()

            if not message:
                break

            try:

                data = json.loads(message)

                msg_type = data.get("command", "")

                if msg_type == "login_success":

                    if not logged_in:
                        logged_in = True
                        safe_print("[Auth] Login successful!")
                        threading.Thread(target=file_listener, daemon=True).start()
                        threading.Thread(target=presence_ping, args=(username,), daemon=True).start()

                elif msg_type == "login_fail":

                    safe_print("[Auth] Login failed.")

                elif msg_type == "account_created":

                    safe_print("[Auth] Account created successfully.")

                elif msg_type == "text":

                    safe_print(coloured(f"[{data['sender']}]: {data['body']}"))

                elif msg_type == "system":

                    safe_print(f"[SYSTEM]: {data['body']}")

                elif msg_type == "file_ready":

                    filepath = pending_files.pop(data["receiver"], None)

                    if filepath:

                        threading.Thread(
                            target=send_file,
                            args=(data["peer_ip"], data["peer_port"], filepath),
                            daemon=True
                        ).start()

            except:

                safe_print(message)

        except:

            safe_print("Disconnected from server.")
            break


# UDP presence ping
def presence_ping(uname):

    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    while running:

        payload = json.dumps({"type": "ping", "user": uname})

        udp_sock.sendto(payload.encode(), (host, udp_port))

        time.sleep(0.1) # evey 100ms


# Colour picker  (called once at login)
def pick_colour():

    global user_colour

    print("\nChoose a colour for your messages and file transfers:")

    for k, (colour_code, name) in COLOURS.items():

        print(f"  {k}) {colour_code}{name}{RESET}")

    print("  0) No colour")

    choice = input("Enter number: ").strip()

    if choice in COLOURS:

        user_colour = COLOURS[choice][0]

        print(f"Colour set to {COLOURS[choice][1]}.")

    else:

        user_colour = ""

        print("No colour selected.")


if __name__ == "__main__":

    threading.Thread(target=receive, daemon=True).start()

    print("Please enter a command (login, create_account, create_group, private, message_group, add_member, file, ping, logout)")

    while True:

        user_input = input()

        if user_input.startswith("login"):

            username = input("Username: ")
            password = input("Password: ")

            pick_colour()

            payload = json.dumps({
                "command": "login",
                "username": username,
                "password": password,
                "file_listen_port": file_listen_port
            })

            client.send(payload.encode())

        elif user_input.startswith("create_account"):

            username = input("Username: ")
            password = input("Password: ")

            payload = json.dumps({
                "command": "create_account",
                "username": username,
                "password": password
            })

            client.send(payload.encode())

        elif user_input.startswith("private"):

            recipient = input("Recipient: ")
            msg = input("Message: ")

            payload   = json.dumps({
                "command": "private", "sender": username, "username": username,
                "recipient": recipient, "receiver": recipient,
                "message": msg, "body": msg,
                "sent_at": time.time()
            })

            client.send(payload.encode())

        elif user_input.startswith("file"):

            filepath = input("Filepath: ")
            receiver = input("Receiver: ")

            if not os.path.exists(filepath):

                print("File not found.")
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

        elif user_input == "logout":

            payload = json.dumps({
                "command": "logout",
                "username": username
            })

            client.send(payload.encode())

            running = False
            client.close()
            break