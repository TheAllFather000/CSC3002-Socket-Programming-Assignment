"""
    python client.py [server_ip] [server_port]
    Default: 156.155.224.26, port 5000
"""

import socket
import threading
import sys

host = '156.155.224.26'
port = 5000

# Create TCP socket
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Connect to the server
try:
    client.connect((host, port))
except Exception as e:
    print(f"Unable to connect to server: {e}")
    sys.exit()

# Listening for messages from the server
def receive():
    while True:
        try:
            message = client.recv(1024).decode('ascii')
            if message == 'NAME':
                client.send(username.encode('ascii'))
            else:
                print(message)

        except Exception as e:
            print(f"An error occurred: {e}")
            client.close()
            break


# Sending messages to server
def write():
    while True:
        try:
            user_input = input("")
            
            # Private message
            # Format: /pm recipient message
            if user_input.startswith("/private"):
                # Send as raw command
                client.send(user_input.encode('ascii'))

            # Group message
            # Format: /group group_id message
            elif user_input.startswith("/group"):
                client.send(user_input.encode('ascii'))

            # send to all users connected to the server?


        except Exception as e:
            print(f"An error occurred: {e}")
            break


# Starting threads for listening and sending messages
if __name__ == "__main__":
    username = input("Enter username: ")

    receive_thread = threading.Thread(target=receive)
    receive_thread.daemon = True
    receive_thread.start()

    write_thread = threading.Thread(target=write)
    write_thread.start()