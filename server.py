"""
Minimal test server for P2P file transfer between two local clients.

Usage:
    python server.py

Then in two separate terminals:
    python client.py 127.0.0.1 5958
    (login as alice / bob, then use the 'file' command to transfer)

Supports:
  - create_account
  - login / logout
  - private messaging  (relays text messages with sent_at for latency tracking)
  - file_request       (broker handshake so sender gets receiver's IP+port)
  - ping / pong        (echoes sent_at back so client can measure RTT)
  - create_group / join_group / message_group
  - UDP presence pings (logged with real username)
"""

import socket
import threading
import json
import hashlib
import time
import os

HOST       = '0.0.0.0'
TCP_PORT   = 5958
UDP_PORT   = 5960
BENCH_FILE = "server_benchmark.txt"

# ── in-memory stores ──────────────────────────────────────────────────────────
accounts = {}   # username -> hashed_password
clients  = {}   # username -> {"sock": sock, "addr": str, "file_port": int}
groups   = {}   # group_name -> {"password": str, "members": [str]}

lock       = threading.Lock()
bench_lock = threading.Lock()


# ── helpers ───────────────────────────────────────────────────────────────────

def hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def send_json(sock, data: dict):
    try:
        sock.sendall(json.dumps(data).encode('ascii'))
    except Exception as e:
        print(f"[Server] send error: {e}")


def log_bench(event: str, detail: str, latency_ms: float = None,
              filesize_bytes: int = None, duration_s: float = None):
    timestamp  = time.strftime("%Y-%m-%d %H:%M:%S")
    lat_str    = f"  latency={latency_ms:.2f} ms"       if latency_ms    is not None else ""
    size_str   = f"  size={filesize_bytes} bytes"        if filesize_bytes is not None else ""
    dur_str    = f"  duration={duration_s:.4f} s"        if duration_s    is not None else ""
    throughput = ""
    if filesize_bytes and duration_s and duration_s > 0:
        mb_s       = (filesize_bytes / (1024 * 1024)) / duration_s
        throughput = f"  throughput={mb_s:.4f} MB/s"

    line = f"[{timestamp}]  event={event}  {detail}{lat_str}{size_str}{dur_str}{throughput}\n"
    with bench_lock:
        with open(BENCH_FILE, "a") as f:
            f.write(line)


# ── client handler ────────────────────────────────────────────────────────────

def handle_client(sock, addr):
    current_user = None
    print(f"[+] Connection from {addr}")

    while True:
        try:
            raw = sock.recv(8192)
            if not raw:
                break

            try:
                data = json.loads(raw.decode('ascii'))
            except json.JSONDecodeError:
                continue

            cmd    = data.get("command", "")
            t_recv = time.time()

            # ── create_account ────────────────────────────────────────────
            if cmd == "create_account":
                uname = data.get("username", "")
                pw    = data.get("password", "")
                with lock:
                    if uname in accounts:
                        send_json(sock, {"command": "system",
                                         "body": f"Username '{uname}' already exists."})
                    else:
                        accounts[uname] = hash_pw(pw)
                        send_json(sock, {"command": "account_created"})
                        print(f"[Account] created: {uname}")
                        log_bench("account_created", f"user={uname}")

            # ── login ─────────────────────────────────────────────────────
            elif cmd == "login":
                uname            = data.get("username", "")
                pw               = data.get("password", "")
                file_listen_port = data.get("file_listen_port", None)
                with lock:
                    if uname in accounts and accounts[uname] == hash_pw(pw):
                        clients[uname] = {
                            "sock":      sock,
                            "addr":      addr[0],
                            "file_port": file_listen_port,
                        }
                        current_user = uname
                        send_json(sock, {"command": "login_success", "username": uname})
                        print(f"[Login] {uname} from {addr}")
                        log_bench("login", f"user={uname}  addr={addr[0]}  status=ok")
                    else:
                        send_json(sock, {"command": "login_fail",
                                         "reason": "Invalid username or password."})
                        log_bench("login", f"user={uname}  addr={addr[0]}  status=fail")

            # ── logout ────────────────────────────────────────────────────
            elif cmd == "logout":
                uname = data.get("username", current_user)
                with lock:
                    clients.pop(uname, None)
                print(f"[Logout] {uname}")
                log_bench("logout", f"user={uname}")
                break

            # ── private message ───────────────────────────────────────────
            elif cmd == "private":
                sender    = data.get("sender") or data.get("username") or current_user
                recipient = data.get("recipient") or data.get("receiver", "")
                body      = data.get("message") or data.get("body", "")
                sent_at   = data.get("sent_at", None)

                with lock:
                    target = clients.get(recipient)

                if target:
                    payload = {"command": "text", "sender": sender, "body": body, "colour": data.get("colour", "")}
                    if sent_at:
                        payload["sent_at"] = sent_at
                    send_json(target["sock"], payload)

                    if sent_at:
                        latency = (t_recv - sent_at) * 1000
                        log_bench("private_msg",
                                  f"from={sender}  to={recipient}  size={len(body)} chars",
                                  latency_ms=latency)
                    print(f"[Message] {sender} -> {recipient}: {body[:60]}")
                else:
                    send_json(sock, {"command": "system",
                                     "body": f"User '{recipient}' is not online."})

            # ── file_request (P2P broker) ─────────────────────────────────
            elif cmd == "file_request":
                sender      = data.get("sender", current_user)
                receiver    = data.get("receiver", "")
                filename    = data.get("filename", "")
                filesize    = data.get("filesize", 0)
                listen_port = data.get("file_listen_port", 6000)

                with lock:
                    if sender in clients:
                        clients[sender]["file_port"] = listen_port
                    target             = clients.get(receiver)
                    receiver_file_port = target["file_port"] if target and target["file_port"] else 6000

                if target:
                    # Notify receiver
                    send_json(target["sock"], {
                        "command": "system",
                        "body":    f"{sender} wants to send you '{filename}' ({filesize} bytes)."
                    })
                    # Tell sender the receiver's IP + file listen port
                    send_json(sock, {
                        "command":   "file_ready",
                        "receiver":  receiver,
                        "peer_ip":   target["addr"],
                        "peer_port": receiver_file_port,
                    })
                    log_bench("file_request_brokered",
                              f"from={sender}  to={receiver}  file={filename}",
                              filesize_bytes=int(filesize))
                    print(f"[File] Brokered {sender} -> {receiver}: '{filename}' ({filesize} B)")
                else:
                    send_json(sock, {"command": "system",
                                     "body": f"User '{receiver}' is not online."})

            # ── create_group ──────────────────────────────────────────────
            elif cmd == "create_group":
                gname   = data.get("group_name", "")
                gpw     = data.get("password", "")
                raw_m   = data.get("members", "")
                creator = data.get("username", current_user)
                members = [m.strip() for m in raw_m.split(",") if m.strip()] if raw_m else []
                all_members = list(set([creator] + members))
                with lock:
                    groups[gname] = {"password": hash_pw(gpw), "members": all_members}
                send_json(sock, {"command": "system",
                                 "body": f"Group '{gname}' created with {len(all_members)} member(s)."})
                log_bench("create_group",
                          f"group={gname}  creator={creator}  members={all_members}")
                print(f"[Group] '{gname}' created by {creator}, members: {all_members}")

            # ── join_group ────────────────────────────────────────────────
            elif cmd == "join_group":
                gname = data.get("group_name", "")
                gpw   = data.get("password", "")
                uname = data.get("username", current_user)
                with lock:
                    grp = groups.get(gname)
                if grp and grp["password"] == hash_pw(gpw):
                    with lock:
                        if uname not in grp["members"]:
                            grp["members"].append(uname)
                    send_json(sock, {"command": "system",
                                     "body": f"Joined group '{gname}' successfully."})
                    log_bench("join_group", f"user={uname}  group={gname}  status=ok")
                    print(f"[Group] {uname} joined '{gname}'")
                else:
                    send_json(sock, {"command": "system",
                                     "body": "Invalid group name or password."})
                    log_bench("join_group", f"user={uname}  group={gname}  status=fail")

            # ── message_group ─────────────────────────────────────────────
            elif cmd == "message_group":
                gname   = data.get("group_name", "")
                sender  = data.get("sender", current_user)
                body    = data.get("body", "")
                sent_at = data.get("sent_at", None)
                with lock:
                    grp = groups.get(gname)
                if grp:
                    delivered = 0
                    for member in grp["members"]:
                        if member == sender:
                            continue
                        with lock:
                            target = clients.get(member)
                        if target:
                            payload = {
                                "command": "text",
                                "sender":  f"{sender}@{gname}",
                                "body":    body,
                            }
                            if sent_at:
                                payload["sent_at"] = sent_at
                            send_json(target["sock"], payload)
                            delivered += 1
                    if sent_at:
                        latency = (t_recv - sent_at) * 1000
                        log_bench("group_msg",
                                  f"from={sender}  group={gname}  delivered={delivered}  size={len(body)} chars",
                                  latency_ms=latency)
                    print(f"[Group] {sender} -> '{gname}': {body[:60]}")
                else:
                    send_json(sock, {"command": "system",
                                     "body": f"Group '{gname}' not found."})

            # ── ping ──────────────────────────────────────────────────────
            # BUG FIX: original did not echo sent_at back, so client could
            # never compute RTT. Now we echo it in the pong system message.
            elif cmd == "ping":
                sent_at = data.get("sent_at", None)
                uname   = data.get("username", current_user)
                send_json(sock, {
                    "command": "system",
                    "body":    "pong",
                    "sent_at": sent_at,   # echoed so client can compute RTT
                })
                if sent_at:
                    latency = (t_recv - sent_at) * 1000
                    log_bench("ping", f"user={uname}  addr={addr[0]}", latency_ms=latency)
                print(f"[Ping] from {uname}")

            else:
                print(f"[Unknown command] '{cmd}' from {addr}")

        except Exception as e:
            print(f"[Error] client {addr}: {e}")
            break

    # Clean up on disconnect
    if current_user:
        with lock:
            clients.pop(current_user, None)
        print(f"[-] Disconnected: {current_user} ({addr[0]}:{addr[1]})")
    else:
        print(f"[-] Disconnected: {addr} (not logged in)")
    sock.close()


# ── UDP presence listener ─────────────────────────────────────────────────────

def udp_listener():
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_sock.bind((HOST, UDP_PORT))
    print(f"[UDP] Presence listener on :{UDP_PORT}")
    while True:
        try:
            raw, addr = udp_sock.recvfrom(1024)
            payload   = json.loads(raw.decode('ascii'))
            if payload.get("type") == "ping":
                # BUG FIX: original printed hardcoded "[USER]" instead of the real username
                uname = payload.get("user", "unknown")
                print(f"[UDP] Presence ping from '{uname}' @ {addr[0]}")
                # Update last-seen time if user is in active clients
                with lock:
                    if uname in clients:
                        clients[uname]["last_seen"] = time.time()
        except Exception:
            pass


# ── TCP server ────────────────────────────────────────────────────────────────

def main():
    # Pre-seeded test accounts
    accounts["alice"] = hash_pw("alice123")
    accounts["bob"]   = hash_pw("bob123")
    print("[Server] Pre-seeded accounts: alice/alice123  bob/bob123")

    threading.Thread(target=udp_listener, daemon=True).start()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, TCP_PORT))
    server.listen(10)
    print(f"[Server] Listening on {HOST}:{TCP_PORT}")
    print(f"[Server] Benchmark log -> {BENCH_FILE}\n")

    try:
        while True:
            sock, addr = server.accept()
            threading.Thread(target=handle_client, args=(sock, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down.")
    finally:
        server.close()


if __name__ == "__main__":
    main()