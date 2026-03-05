"""
    python client.py [server_ip] [server_port]
    Default: 156.155.224.26, port 5000
"""

import socket, os, threading, hashlib, sys, json, time
# from colorist import bright_magenta, bright_green, bright_red, bright_cyan, bright_yellow

# Default server details
#host = sys.argv[1] if len(sys.argv) > 1 else '156.155.224.26'
#port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000

host = '196.47.211.33'
port = 5958

file_listen_port = 6000
chunk_size = 4096
presence_port = 5555
udp_port = 5960

username = None
pending_files = {} # local filepath, created before server confirms
logged_in = False
running = True


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
    file_server.bind(('127.0.0.1', file_listen_port))
    file_server.listen(5)

    print(f"[File listener running on port {file_listen_port}]")

    while running:
        try:
            peer_sock, peer_addr = file_server.accept()
            threading.Thread(
                target=receive_file,
                args=(peer_sock, peer_addr),
                daemon=True
            ).start()
        except Exception as e:
            print(f"File listener error: {e}")


def receive_file(peer_sock, peer_addr):
    filename = "unknown"
    filesize = 0

    try:
        header = b''
        while b'\n' not in header:
            chunk = peer_sock.recv(1024)
            if not chunk:
                return
            header += chunk

        header_line, leftover = header.split(b'\n', 1)
        parts = header_line.decode('ascii').split('|')

        if len(parts) != 3:
            print("Invalid file header received.")
            return

        filename, filesize, expected_md5 = parts
        filesize = int(filesize)

        print(f"\n[File incoming] '{filename}' ({filesize} bytes) from {peer_addr[0]}")

        save_path = f'received_{filename}'
        received = len(leftover)
        md5_hash = hashlib.md5()

        # Write chunks directly to file
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

        # MD5 integrity check which confirms no corruption during transfer
        if md5_hash.hexdigest() == expected_md5:
            print(f"[File received] Saved as '{save_path}' — MD5 verified.")
        else:
            os.remove(save_path)
            print(f"[File error] MD5 mismatch — file corrupted, transfer failed.")

    except Exception as e:
        print(f"File receive error: {e}")
    finally:
        peer_sock.close()


# File sender
def send_file(peer_ip, peer_port, filepath):
    peer_sock = None

    try:

        # Compute MD5 before transfer so receiver can verify integrity
        md5_hash = hashlib.md5()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(chunk_size), b''):
                md5_hash.update(chunk)
        file_md5 = md5_hash.hexdigest()

        # Direct P2P TCP connection to receiver
        peer_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_sock.connect((peer_ip, int(peer_port)))

        # Send header
        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)
        header = f'{filename}|{filesize}|{file_md5}\n'.encode('ascii')
        peer_sock.sendall(header)

        # Send file in chunks
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                peer_sock.sendall(chunk)

        print(f"[File sent] '{filename}' -> {peer_ip}:{peer_port}")

    except Exception as e:
        print(f"File send error: {e}")
    finally:
        if peer_sock:
            peer_sock.close()


# Server message receiver
def receive():
    global logged_in

    while running:
        try:
            message = client.recv(4096).decode('ascii')
            if not message:
                print("Disconnected from server.")
                break

            try:
                data = json.loads(message)
                msg_type = data.get("command", "")

                if msg_type == "login_success":
                    logged_in = True
                    print(f"[Auth] Login successful! Welcome, {data.get('username', '')}.")

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
                            daemon=True
                        ).start()
                    else:
                        print(f"[File error] No pending file for '{data['receiver']}'.")

                else:
                    print(message)

            except json.JSONDecodeError:
                print(message)

        except Exception as e:
            print(f"An error occurred: {e}")
            client.close()
            break


def presence_ping(username):
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    while running:
        payload = json.dumps({"type": "ping", "user": username})
        udp_sock.sendto(payload.encode('ascii'), (host, udp_port))
        time.sleep(2)


if __name__ == "__main__":
    threading.Thread(target=receive, daemon=True).start()

    while True:
        user_input = input("")

        if user_input.startswith("login"):
            username = input("Username: ")
            password = input("Password: ")
            payload = json.dumps({"command": "login", "username": username, "password": password})
            client.send(payload.encode())

            #time.sleep(0.5)
            if logged_in:
                threading.Thread(target=file_listener, daemon=True).start()
                threading.Thread(target=presence_ping, args=(username,), daemon=True).start()

        elif user_input.startswith("create_account"):
            username = input("Username: ")
            password = input("Password: ")
            payload = json.dumps({"command": "create_account", "username": username, "password": password})
            # print("Created")
            client.send(payload.encode())

        elif user_input.startswith("private"):
            
            username = input("Username: ")
            recipient = input("Recipient: ")
            msg = input("Message: ")
            payload = json.dumps({"command": "private", "username": username,
                                  "recipient": recipient, "message": msg})
            client.send(payload.encode())

        elif user_input.startswith("send_message"):
            _, receiver, *msg = user_input.split(" ")
            payload = json.dumps({"command": "private", "sender": username,
                                  "receiver": receiver, "body": " ".join(msg)})
            client.send(payload.encode())

        elif user_input.startswith("create_group"):
            username = input("Your username: ")
            password = input("Group password: ")
            group_name = input("Group name: ")

            members = []
            print("Add members one at a time. Press Enter with no name to finish.")
            while True:
                member = input("Add member:")
                if not member:
                    if not members:
                        print("Please enter at least one member.")
                        continue
                    break
                members.append(member)
            
            print(members)
            payload = json.dumps({"command": "create_group", "username": username, "password": password, "group_name": group_name,
                                  "members": ",".join(members)})
            client.send(payload.encode())

        elif user_input.startswith("join_group"):
                    uname      = input("Your username: ")
                    group_name = input("Group name: ")
                    password   = input("Group password: ")
                    payload = json.dumps({"command":    "join_group", "username": username, "group_name": group_name, "password":   password
                    })
                    client.send(payload.encode())

        elif user_input.startswith("message_group"):
            username = input("Your username: ")
            group_name = input("Group name: ")
            msg = input("Message: ")
            payload = json.dumps({"command": "message_group", "sender": username,
                                  "group_name": group_name, "body": msg})
            client.send(payload.encode())


        elif user_input.startswith("file"):
            filepath = input("Filepath")
            receiver = input("Receiver: ")

            if not os.path.exists(filepath):
                print(f"File not found: '{filepath}'")
                continue

            pending_files[receiver] = filepath
            payload = json.dumps({
                "command": "file_request", "sender": username, "receiver": receiver,
                "filename": os.path.basename(filepath),
                "filesize": os.path.getsize(filepath),
                "file_listen_port": file_listen_port
            })
            client.send(payload.encode())
            print(f"[File] Requesting transfer of '{os.path.basename(filepath)}' to {receiver}...")

        elif user_input.startswith("ping"):
            payload = json.dumps({"command": "ping", "username": username})
            client.send(payload.encode())

        elif user_input == "logout":
            username = username
            payload = json.dumps({"command": "logout", "username": username})
            client.send(payload.encode())

            # time.sleep(0.5)
            running = False
            client.close()
            break

        else:
            print("Commands: login | create_account | create_group | private | message_group | add_member | file | ping | logout")