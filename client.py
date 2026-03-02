"""
    python client.py [server_ip] [server_port]
    Default: 156.155.224.26, port 5000
"""

import socket
import os
import threading
import hashlib
import sys
import time

# Default server details
host = sys.argv[1] if len(sys.argv) > 1 else '156.155.224.26'
port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
file_listen_port = 6000
chunk_size = 4096
presence_port = 5555

username = None
pending_files = {} # local filepath, created before server confirms

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

    print(f"[File listener running on port {file_listen_port}]")

    while True:
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

        try:
            filesize = int(filesize)
        except ValueError:
            print("Invalid file size in header.")
            return

        print(f"\n[File incoming] '{filename}' ({filesize} bytes) from {peer_addr[0]}")

        save_path = f'received_{filename}'
        received  = len(leftover)
        md5_hash  = hashlib.md5()

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
        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)

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


# Server message receiver (TCP)
def receive():
    while True:
        try:
            message = client.recv(4096).decode('ascii')
            if not message:
                print("Disconnected from server.")
                break

            # Server requests username on connect
            if message == 'NAME':
                client.send(username.encode('ascii'))

            # Server gives us peer's IP and port for file transfer
            elif message.startswith('FILEREADY'):
                parts     = message.split(' ')
                peer_ip   = parts[1]
                peer_port = parts[2]
                recipient = parts[3]
                filepath  = pending_files.pop(recipient, None)
                if filepath:
                    threading.Thread(
                        target=send_file,
                        args=(peer_ip, peer_port, filepath),
                        daemon=True
                    ).start()
                else:
                    print(f"[File error] No pending file found for '{recipient}'.")

            else:
                print(message)

        except Exception as e:
            print(f"An error occurred: {e}")
            client.close()
            break


# Sending messages to server (user command input)
def write():
    while True:
        try:
            user_input = input("")
            
            # Private message
            if user_input.startswith("/private"):
                # Send as raw command
                client.send(user_input.encode('ascii'))

            # Group message
            elif user_input.startswith("/group"):
                client.send(user_input.encode('ascii'))

            # Group membership
            elif user_input.startswith("/join"):
                client.send(user_input.encode('ascii'))

            elif user_input.startswith("/leave"):
                client.send(user_input.encode('ascii'))

            # Broadcast to all connected users
            elif user_input.startswith("/broadcast"):
                client.send(user_input.encode('ascii'))

            # Server confirms recipient is online and returns their IP
            elif user_input.startswith("/file"):
                print("File transfer command received"); # fix

                try:
                    _, recipient, filepath = user_input.split(' ', 2)
                    if not os.path.exists(filepath):
                        print(f"File not found: '{filepath}'")
                        continue

                    # Store filepath so send_file() can use it when FILEREADY arrives
                    pending_files[recipient] = filepath
                    filename = os.path.basename(filepath)
                    filesize = os.path.getsize(filepath)

                    # Tell server the recipient, filename, size and  file listen port
                    request = f'/file {recipient} {filename} {filesize} {file_listen_port}'
                    client.send(request.encode('ascii'))

                except ValueError:
                    print("Usage: /file <recipient> <filepath>")
        
            else:
                print("Unknown command. Use /private, /group, /join, /leave, /broadcast or /file.")

        except Exception as e:
            print(f"An error occurred: {e}")
            break

def presence_ping(username):
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    while True:
        message = f"ONLINE {username}"
        udp_sock.sendto(message.encode('ascii'), (host, presence_port))
        time.sleep(0,1) # 100 ms interval

# Starting threads for sending and receiving messages/files
if __name__ == "__main__":
    username = input("Enter username: ")

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
