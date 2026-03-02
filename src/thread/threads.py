from database.db import DB
import socket
import json
import datetime
import threading
import time

# from urllib.request import urlopen
# import re as r
import subprocess
from colorist import bright_magenta, red


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

    def __init__(self, sock_, ip, port):
        self.db = DB()
        self.active_clients = {}
        self.client_access = {}
        self.port = port
        self.ip = ip
        self.sock = sock_
        # data = str(urlopen("http://checkip.dyndns.com/").read())
        # self.ip = r.compile(r"Address: (\d+\.\d+\.\d+\.\d+)").search(data).group(1)
        # print(self.ip.check_returncode())

    def check_client_status(self, username: str):
        return username in self.active_clients

    def add_active_client(self, username, conn):
        self.active_clients.update({username: {"conn": conn, "ping": time.time()}})

    def remove_active_client(self, username):
        self.active_clients.pop(username)

    # def
    def handle_client(self, conn, addr):
        # if data["recipient"] in self.active_clients:
        # bright_magenta(f"Sending message to client {data['recipient']}")
        message = conn.recv(3000).decode()
        # print(message)
        data = json.loads(message)
        # print(data)
        if data["type"].lower() == "login":
            # print(data["username"])
            self.add_active_client(data["username"], conn)
            try:
                user_info = self.db.retrieve_user(data["username"])
                if user_info is not None:
                    conn.send(user_info.encode())

                bright_magenta(
                    f"[[LOGIN] {datetime.datetime.now()}]: {data['username']}"
                )
            except Exception as e:
                print("Exception: ", e)
        elif data["type"] == "private":
            message_content = data["message"]
            success = False
            if data["recipient"] in self.active_clients:
                bright_magenta(
                    f"[[MESSAGE] {datetime.datetime.now()}] {data['username']} → {data['recipient']}: {message_content}"
                )
                payload = json.dumps(
                    {
                        "from": data["username"],
                        "to": data["recipient"],
                        "colour": data["colour"],
                        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
                print(self.active_clients)
                # send to recipient
                self.active_clients[data["recipient"]]["conn"].send(payload.encode())

                # send success or failure message
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
                            "date_time": datetime.datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                        }
                    )
                    conn.send(f_payload.encode())

                else:
                    f_payload = json.dumps(
                        {
                            "status": "fail",
                            "process": "send_private_message",
                            "date_time": datetime.datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
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
                            "recipient_status": "offline",
                            "date_time": datetime.datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                        }
                    )
                    conn.send(f_payload.encode())

                else:
                    f_payload = json.dumps(
                        {
                            "status": "fail",
                            "process": "send_private_message",
                            "date_time": datetime.datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                        }
                    )
                    conn.send(f_payload.encode())

        elif data["type"].lower() == "logout":
            self.logout(data["username"])
            bright_magenta(f"[LOGOUT] {datetime.datetime.now()}] {data['username']}")

        elif data["type"].lower() == "create_account":
            success = False
            try:
                success = self.db.create_user(data["username"], data["password"])
            except Exception as e:
                print("Exception: ", e)
            self.active_clients.update({data["username"]: conn})
            bright_magenta(
                f"[CREATE_ACCOUNT] {datetime.datetime.now()}] : {data['username']}"
            )
            f_payload = None
            if success:
                f_payload = json.dumps(
                    {
                        "status": "success",
                        "process": "create_account",
                        "date_time": datetime.datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                    }
                )

            else:
                f_payload = json.dumps(
                    {
                        "status": "fail",
                        "process": "create_account",
                        "date_time": datetime.datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                    }
                )
            conn.send(f_payload.encode())

    def create_group(self, data):
        users = data["members"]
        bright_magenta(f"[CREATE GROUP]: New Group Created ({data['group_name']})")
        for u in users:
            if u in self.active_clients:
                conn = self.active_clients[u]["conn"]
                payload = json.dumps(
                    {
                        "notification": "added to group",
                        "from": data["username"],
                        "created_at": datetime.datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                    }
                )
                conn.send(payload.encode())
                self.db.upload_message(
                    data["username"],
                    data["recipient"],
                    "read group_text",
                    data["group_name"],
                    f"added to group {data['username']}",
                )

            else:
                self.db.upload_message(
                    data["username"],
                    u,
                    "unread group_text",
                    data["group_name"],
                    f"added to group {data['username']}",
                )
            self.db.create_group(
                data["group_name"],
                data["members"].replace("[", "").replace("]", "").split(","),
            )

    def message_group(self, username, group_name, message):
        members = self.db.get_group_members(group_name)
        if members is not None:
            for m in members:
                if m in self.active_clients:
                    conn = self.active_clients[m]["conn"]
                    payload = json.dumps(
                        {
                            "from": username,
                            "type": "group_text",
                            "message": message,
                            "sent_at": datetime.datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                        }
                    )
                    conn.send(payload.encode())
                else:
                    self.db.upload_message(
                        username,
                        m,
                        "unread group_text",
                        group_name + " {" + username + "}",
                        f"{message}",
                    )
            return True
        else:
            return False

    def logout(self, username: str):
        payload = json.dumps(
            {
                "status": "success",
                "process": "logout",
                "date_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        if self.active_clients.get(username) is not None:
            try:
                self.active_clients[username]["conn"].send(payload.encode())
                self.active_clients.pop(username)
            except Exception as e:
                red("Exception: " + e.__str__())

        pass

    def handle_online_status(self):
        while True:
            for i in self.active_clients:
                current = time.time()
                if (current - self.active_clients[i]["time"]) > 20:
                    self.logout(i)
            time.sleep(10)

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
