import socket
import subprocess
from colorist import bright_magenta, bright_yellow
import datetime
import threading
from thread.threads import server_thread
import json

server_sock = None
server_handler = None
clients = {}

ascii_art = """
 SSSSS   CCCCC  H   H    A    TTTTT
S        C      H   H   A A     T  
 SSS     C      HHHHH  AAAAA    T  
    S    C      H   H  A   A    T  
 SSSSS   CCCCC  H   H  A   A    T
"""


def main():
    # print(subprocess.run("curl ifconfig.me", shell=True).returncode)
    bright_yellow(ascii_art)
    global server_sock, server_handler
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(("0.0.0.0", 5958))
    server_handler = server_thread(server_sock, "0.0.0.0", 5958)
    thread = threading.Thread(target=server_handler.handle_online_status, daemon=True)
    thread2 = threading.Thread(target=server_handler.ping, daemon=True)
    thread.start()
    thread2.start()
    # ip = subprocess.run("curl ifconfig.me", shell=True).returncode
    start()


def start():

    global server_sock, server_handler
    if server_sock is not None and server_handler is not None:
        server_sock.listen()
        bright_magenta(
            f"[LISTENING] {datetime.datetime.now()} \nServer is listening on {'0.0.0.0'} : {5958}"
        )
        # thread = threading.Thread(target=server_thread.handle_online_status)
        while True:
            conn, addr = server_sock.accept()
            # thread = threading.Thread(target=self.handle_client, args=(conn, addr))
            # thread.start():
            print("connection")
            thread = threading.Thread(
                target=server_handler.handle_client, args=(conn, addr), daemon=True
            )
            thread.start()
            # server_handler.handle_client(conn, addr)
            clients = server_handler.active_clients


if __name__ == "__main__":
    main()
