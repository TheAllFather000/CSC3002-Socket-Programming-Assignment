"""
python client.py [server_ip] [server_port]
Default: 156.155.224.26, port 5000
"""

import socket, os, threading, hashlib, sys, json, time
# from colorist import bright_magenta, bright_green, bright_red, bright_cyan, bright_yellow

# Default server details
# host = sys.argv[1] if len(sys.argv) > 1 else '156.155.224.26'
# port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000

host = "156.155.224.26"
port = 5958
file_listen_port = 6000
chunk_size = 4096
presence_port = 5555
udp_port = 5960

username = None
pending_files = {}  # local filepath, created before server confirms
logged_in = False
running = True


# Benchmarking
tcp_latencies = []  # ms per send
udp_latencies = []  # ms per heartbeat RTT
file_results = []

"""
def log_result(event, value):
    with open("results_log.txt", "a") as f:
        f.write(f"{time.strftime('%H:%M:%S')} | {event} | {value}\n")

def print_benchmark():
    print("Benchmark Results")

    if tcp_latencies:
        print(f"TCP Send Latency ({len(tcp_latencies)}):")
        print(f"  Avg:   {statistics.mean(tcp_latencies):.2f} ms")
    else:
        print("TCP: no data yet.")

    if udp_latencies:
        print(f"\nUDP Presence RTT ({len(udp_latencies)}):")
        print(f"  Avg:   {statistics.mean(udp_latencies):.2f} ms")
    
    else:
        print("UDP: no data yet.")

    if file_results:
        print(f"\nFile Transfers ({len(file_results)} total):")
        for r in file_results:
            status = "OK  " if r["success"] else "FAIL"
            print(f"  [{status}] {r['filename']:20s} | {r['size_bytes']:>8} B | "
                  f"{r['duration_s']:>6.3f}s | {r['throughput_kbps']:>8.1f} KB/s | "
                  f"MD5: {'pass' if r['success'] else 'FAIL'}")
        success_rate = sum(1 for r in file_results if r["success"]) / len(file_results) * 100
        print(f"  File success rate: {success_rate:.1f}%")
    else:
        print("File transfers: no data yet.")
"""

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
    file_server.bind(("0.0.0.0", file_listen_port))
    file_server.listen(5)

    print(f"[File listener running on port {file_listen_port}]")

    while True:
        try:
            peer_sock, peer_addr = file_server.accept()
            threading.Thread(
                target=receive_file, args=(peer_sock, peer_addr), daemon=True
            ).start()
        except Exception as e:
            print(f"File listener error: {e}")


def receive_file(peer_sock, peer_addr):
    start = time.perf_counter()
    filename = "unknown"
    filesize = 0
    success = False

    try:
        header = b""
        while b"\n" not in header:
            chunk = peer_sock.recv(1024)
            if not chunk:
                return
            header += chunk

        header_line, leftover = header.split(b"\n", 1)

        parts = header_line.decode("ascii").split("|")

        if len(parts) != 3:
            print("Invalid file header received.")
            return

        filename, filesize, expected_md5 = parts

        try:
            filesize = int(filesize)
        except ValueError:
            print("Invalid file size in header.")
            return

        print(f"\n[File incoming] '{filename}' ({filesize} bytes) from {peer_addr[0]}")

        save_path = f"received_{filename}"
        received = len(leftover)
        md5_hash = hashlib.md5()

        # Write chunks directly to file
        with open(save_path, "wb") as f:
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

        # MD5 integrity check which confirms no corruption during transfer
        if md5_hash.hexdigest() == expected_md5:
            success = True
            print(f"[File received] Saved as '{save_path}' — MD5 verified.")
        else:
            os.remove(save_path)
            print(f"[File error] MD5 mismatch — file corrupted, transfer failed.")

    except Exception as e:
        print(f"File receive error: {e}")
    finally:
        peer_sock.close()
        duration = time.perf_counter() - start
        # throughput = (filesize / 1024) / duration if duration > 0 else 0
        file_results.append(
            {
                "filename": filename,
                "size_bytes": filesize,
                "duration_s": duration,
                # "throughput_kbps": throughput,
                "success": success,
            }
        )
        # log_result("FILE_RECV", f"{filename} | {filesize}B | {duration:.3f}s | {throughput:.1f}KB/s | {'OK' if success else 'FAIL'}")


# File sender
def send_file(peer_ip, peer_port, filepath):
    peer_sock = None
    start = time.perf_counter()
    filename = os.path.basename(filepath)
    filesize = os.path.getsize(filepath)
    success = False

    try:
        # Compute MD5 before transfer so receiver can verify integrity
        md5_hash = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                md5_hash.update(chunk)
        file_md5 = md5_hash.hexdigest()

        # Direct P2P TCP connection to receiver
        peer_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_sock.connect((peer_ip, int(peer_port)))

        # Send header
        header = f"{filename}|{filesize}|{file_md5}\n".encode("ascii")
        peer_sock.sendall(header)

        # Send file in chunks
        with open(filepath, "rb") as f:
            while chunk := f.read(chunk_size):
                peer_sock.sendall(chunk)

        success = True
        print(f"[File sent] '{filename}' -> {peer_ip}:{peer_port}")

    except Exception as e:
        print(f"File send error: {e}")
    finally:
        if peer_sock:
            peer_sock.close()
        duration = time.perf_counter() - start
        throughput = (filesize / 1024) / duration if duration > 0 else 0
        file_results.append(
            {
                "filename": filename,
                "size_bytes": filesize,
                "duration_s": duration,
                "throughput_kbps": throughput,
                "success": success,
            }
        )
        # log_result("FILE_SEND", f"{filename} | {filesize}B | {duration:.3f}s | {throughput:.1f}KB/s | {'OK' if success else 'FAIL'}")


# Server message receiver
def receive():
    while True:
        try:
            message = client.recv(4096).decode("ascii")
            if not message:
                print("Disconnected from server.")
                break

            try:
                data = json.loads(message)
                msg_type = data.get("type", "")

                if msg_type == "login_success":
                    logged_in = True
                    print(
                        f"[Auth] Login successful! Welcome, {data.get('username', '')}."
                    )

                elif msg_type == "login_fail":
                    print(f"[Auth] Login failed: {data.get('reason', '')}")

                elif msg_type == "account_created":
                    print("[Auth] Account created successfully.")

                elif msg_type == "text":
                    print(f"[{data['sender']}]: {data['body']}")

                elif msg_type == "presence":
                    if data["status"] == "online":
                        print(f"[ONLINE]  {data['user']}")
                    else:
                        print(f"[OFFLINE] {data['user']}")

                elif msg_type == "system":
                    print(f"[SYSTEM]: {data['body']}")

                elif msg_type == "file_ready":
                    filepath = pending_files.pop(data["receiver"], None)
                    if filepath:
                        threading.Thread(
                            target=send_file,
                            args=(data["peer_ip"], data["peer_port"], filepath),
                            daemon=True,
                        ).start()
                    else:
                        print(f"[File error] No pending file for '{data['receiver']}'.")

                else:
                    print(message)

            except json.JSONDecodeError:
                if message == "NAME":
                    if username:
                        client.send(username.encode("ascii"))
                elif message.startswith("FILEREADY"):
                    parts = message.split(" ")
                    filepath = pending_files.pop(parts[3], None)
                    if filepath:
                        threading.Thread(
                            target=send_file,
                            args=(parts[1], parts[2], filepath),
                            daemon=True,
                        ).start()
                else:
                    print(message)

        except Exception as e:
            print(f"An error occurred: {e}")
            client.close()
            break


def presence_ping(username):
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.settimeout(1.0)
    while running:
        payload = json.dumps({"type": "presence_ping", "user": username})
        t0 = time.perf_counter()
        udp_sock.sendto(payload.encode("ascii"), (host, udp_port))

        # Attempt to measure RTT if server echoes back
        try:
            udp_sock.recvfrom(1024)
            rtt_ms = (time.perf_counter() - t0) * 1000
            udp_latencies.append(rtt_ms)
            # log_result("UDP_RTT_MS", f"{rtt_ms:.2f}")
        except socket.timeout:
            pass

        except Exception as e:
            print(f"[Presence error] {e}")

        time.sleep(0.1)  # 100ms interval


if __name__ == "__main__":
    threading.Thread(target=receive, daemon=True).start()

    while True:
        user_input = input("")

        if user_input.startswith("login"):
            username = input("Username: ")
            password = input("Password: ")
            payload = json.dumps(
                {"type": "login", "username": username, "password": password}
            )
            client.send(payload.encode())

            # Wait briefly for server authorising response
            time.sleep(0.5)
            if logged_in:
                threading.Thread(target=file_listener, daemon=True).start()
                threading.Thread(
                    target=presence_ping, args=(username,), daemon=True
                ).start()

        elif user_input.startswith("create_account"):
            username = input("Username: ")
            password = input("Password: ")
            payload = json.dumps(
                {"type": "create_account", "username": username, "password": password}
            )
            client.send(payload.encode())

        elif user_input.startswith("private"):
            _, receiver, *msg = user_input.split(" ")
            payload = json.dumps(
                {
                    "type": "private",
                    "sender": username,
                    "receiver": receiver,
                    "body": " ".join(msg),
                }
            )
            t0 = time.perf_counter()
            client.send(payload.encode())
            latency_ms = (time.perf_counter() - t0) * 1000
            tcp_latencies.append(latency_ms)
            # log_result("TCP_LATENCY_MS", f"{latency_ms:.2f}")

        # Send to users who have joined a specific group
        elif user_input.startswith("group"):
            _, group, *msg = user_input.split(" ")
            payload = json.dumps(
                {
                    "type": "group",
                    "sender": username,
                    "group": group,
                    "body": " ".join(msg),
                }
            )
            t0 = time.perf_counter()
            client.send(payload.encode())
            latency_ms = (time.perf_counter() - t0) * 1000
            tcp_latencies.append(latency_ms)
            # log_result("TCP_LATENCY_MS", f"{latency_ms:.2f}")

        elif user_input.startswith("join"):
            _, group = user_input.split(" ")
            payload = json.dumps({"type": "join", "user": username, "group": group})
            client.send(payload.encode())

        elif user_input.startswith("leave"):
            _, group = user_input.split(" ")
            payload = json.dumps({"type": "leave", "user": username, "group": group})
            client.send(payload.encode())

        # Send to every connected user (concurrency/scalability testing)
        elif user_input.startswith("broadcast"):
            _, *msg = user_input.split(" ")
            payload = json.dumps(
                {"type": "broadcast", "sender": username, "body": " ".join(msg)}
            )
            t0 = time.perf_counter()
            client.send(payload.encode())
            latency_ms = (time.perf_counter() - t0) * 1000
            tcp_latencies.append(latency_ms)
            # log_result("TCP_LATENCY_MS", f"{latency_ms:.2f}")

        elif user_input.startswith("file"):
            _, receiver, filepath = user_input.split(" ", 2)
            if not os.path.exists(filepath):
                print(f"File not found: '{filepath}'")
                continue
            pending_files[receiver] = filepath
            payload = json.dumps(
                {
                    "type": "file_request",
                    "sender": username,
                    "receiver": receiver,
                    "filename": os.path.basename(filepath),
                    "filesize": os.path.getsize(filepath),
                    "file_listen_port": file_listen_port,
                }
            )
            client.send(payload.encode())
            print(
                f"[File] Requesting transfer of '{os.path.basename(filepath)}' to {receiver}..."
            )

        elif user_input == "log_out":
            running = False
            # print_benchmark()
            client.close()
            break

        else:
            print(
                "Commands: login | create_account | private | group | join | leave | broadcast | file | log_out"
            )


"""
    # P2P file transfer
    threading.Thread(target=file_listener, daemon=True).start()

    # User input
    threading.Thread(target=write, daemon=True).start()

    # Server message receiver thread
    #receive()
    threading.Thread(target=receive, daemon=True).start()

    # Presence ping thread
    threading.Thread(target=presence_ping, args=(username,), daemon=True).start()

    # Keep main thread alive
    threading.Event().wait()
"""
