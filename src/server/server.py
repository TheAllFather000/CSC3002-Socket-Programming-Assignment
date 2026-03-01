import socket
import subprocess
from colorist import bright_magenta
import datetime

from thread.threads import server_thread

server_sock = None
server_handler = None
clients = {}


def main():
    global server_sock, server_handler
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_handler = server_thread("0.0.0.0", 5959)
    server_sock.bind(("0.0.0.0", 5959))
    # ip = subprocess.run("curl ifconfig.me", shell=True).returncode
    start()


def start():

    global server_sock, server_handler
    if server_sock is not None and server_handler is not None:
        server_sock.listen()
        bright_magenta(
            f"[LISTENING] {datetime.datetime.now()} Server is listening on {'0.0.0.0'} : {5959}"
        )
        while True:
            conn, addr = server_sock.accept()
            # thread = threading.Thread(target=self.handle_client, args=(conn, addr))
            # thread.start():
            server_handler.handle_client(conn, addr)
            clients = server_handler.active_clients


if __name__ == "__main__":
    main()
