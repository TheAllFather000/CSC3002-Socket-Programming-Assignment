from database.db import DB
import socket
import json
import datetime
import threading

# from urllib.request import urlopen
# import re as r
import subprocess
from colorist import bright_magenta


class server_thread:
    # def __init__(self):
    #     self.db = DB()
    #     self.active_clients = {}
    #     self.port = 55632
    #     self.ip = subprocess.run("curl ifconfig.me", shell=True)
    #     self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #     self.sock.bind((self.ip.returncode, self.port))
    #     # data = str(urlopen("http://checkip.dyndns.com/").read())
    #     # self.ip = r.compile(r"Address: (\d+\.\d+\.\d+\.\d+)").search(data).group(1)
    #     # print(self.ip.check_returncode())

    def __init__(self, ip, port):
        self.db = DB()
        self.active_clients = {}
        self.port = port
        self.ip = ip
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((self.ip, self.port))
        # data = str(urlopen("http://checkip.dyndns.com/").read())
        # self.ip = r.compile(r"Address: (\d+\.\d+\.\d+\.\d+)").search(data).group(1)
        # print(self.ip.check_returncode())

    def check_client_status(self, username: str):
        return username in self.active_clients

    def add_active_client(self, username):
        self.active_clients.update({username: None})

    def remove_active_client(self, username):
        self.active_clients.pop(username)

    # def
    def handle_client(self, conn, addr):
        # if data["recipient"] in self.active_clients:
        # bright_magenta(f"Sending message to client {data['recipient']}")
        message = conn.recv(3000).decode()
        data = json.loads(message)
        if data["type"] == "login":
            self.add_active_client({data["username"]: conn})
            user_info = self.db.retrieve_user(data["username"])
            if user_info is not None:
                conn.send(user_info.encode())
        elif data["type"] == "send_private_message":
            message_content = data["message"]
            success = False
            if data["recipient"] in self.active_clients:
                bright_magenta(
                    f"[{datetime.datetime.now()}] [MESSAGE] {data['username']} → {data['recipient']}: {message_content}"
                )
                payload = json.dumps(
                    {
                        "from": data["username"],
                        "to": data["recipient"],
                        "colour": data["colour"],
                        "time": datetime.datetime.now(),
                    }
                )
                self.active_clients[data["recipient"]].send(payload.encode())
                sucess = self.db.upload_message(
                    data["username"],
                    data["recipient"],
                    "read",
                    "text",
                    message_content,
                )
                f_payload = None
                if success:
                    f_payload = json.dumps(
                        {
                            "status": "success",
                            "process": "send_private_message",
                            "recipient_status": "online",
                            "date_time": datetime.datetime.now(),
                        }
                    )
                    conn.send(f_payload.encode())

                else:
                    f_payload = json.dumps(
                        {
                            "status": "fail",
                            "process": "send_private_message",
                            "date_time": datetime.datetime.now(),
                        }
                    )
                    conn.send(f_payload.encode())
            else:
                success = self.db.upload_message(
                    data["username"],
                    data["recipient"],
                    "unread",
                    "text",
                    message_content,
                )
                if success:
                    f_payload = json.dumps(
                        {
                            "status": "success",
                            "process": "send_private_message",
                            "recipient_status": "online",
                            "date_time": datetime.datetime.now(),
                        }
                    )
                    conn.send(f_payload.encode())

                else:
                    f_payload = json.dumps(
                        {
                            "status": "fail",
                            "process": "send_private_message",
                            "date_time": datetime.datetime.now(),
                        }
                    )
                    conn.send(f_payload.encode())

        elif data["type"].lower() == "logout":
            self.active_clients.pop(data["username"])
            l_payload = json.dumps(
                {
                    "status": "success",
                    "process": "logout",
                    "date_time": datetime.datetime.now(),
                }
            )
            conn.send(l_payload.encode())
            bright_magenta(f"[{datetime.datetime.now()}] [LOGOUT] {data['username']}")

        elif data["type"].lower() == "create_account":
            success = False
            try:
                success = self.db.create_user(
                    data["username"], data["password"], data["colour"]
                )
            except Exception as e:
                print("Exception: ", e)
            self.active_clients.update({data["username"]: conn})
            bright_magenta(
                f"[{datetime.datetime.now()}] [CREATE_ACCOUNT]: {data['username']}"
            )
            f_payload = None
            if success:
                f_payload = json.dumps(
                    {
                        "status": "success",
                        "process": "create_account",
                        "date_time": datetime.datetime.now(),
                    }
                )

            else:
                f_payload = json.dumps(
                    {
                        "status": "fail",
                        "process": "create_account",
                        "date_time": datetime.datetime.now(),
                    }
                )
            conn.send(f_payload.encode())

    # def start(self):
    #   self.sock.listen()
    #  bright_magenta(
    #     f"[LISTENING] {datetime.datetime.now()} Server is listening on {self.ip} : {self.port}"
    # )
    # while True:
    #   conn, addr = self.sock.accept()
    # thread = threading.Thread(target=self.handle_client, args=(conn, addr))
    # thread.start()
    #  self.handle_client(conn, addr)


def main():
    # t = server_thread()
    pass


if __name__ == "__main__":
    main()
