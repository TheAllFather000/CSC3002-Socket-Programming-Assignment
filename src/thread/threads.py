import psycopg2
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
    #     server_thread.active_clients = {}
    #     self.port = 55632
    #     self.ip = subprocess.run("curl ifconfig.me", shell=True)
    #     self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #     self.sock.bind((self.ip.returncode, self.port))
    #     # data = str(urlopen("http://checkip.dyndns.com/").read())
    #     # self.ip = r.compile(r"Address: (\d+\.\d+\.\d+\.\d+)").search(data).group(1)
    #     # print(self.ip.check_returncode())
    active_clients = {}
    lock = threading.Lock()
    thread = None

    def __init__(self, sock_, ip, port):
        self.db = DB()
        self.client_access = {}
        self.port = port
        self.ip = ip
        self.sock = sock_
        # data = str(urlopen("http://checkip.dyndns.com/").read())
        # self.ip = r.compile(r"Address: (\d+\.\d+\.\d+\.\d+)").search(data).group(1)
        # print(self.ip.check_returncode())

    def check_client_status(self, username: str):
        return username in server_thread.active_clients

    def add_active_client(self, username, conn):
        with server_thread.lock:
            server_thread.active_clients.update(
                {username: {"conn": conn, "ping": time.time()}}
            )

    def remove_active_client(self, username):
        with server_thread.lock:
            server_thread.active_clients.pop(username)

    # def
    def handle_client(self, conn, addr):
        # if data["recipient"] in server_thread.active_clients:
        # bright_magenta(f"Sending message to client {data['recipient']}")
        while True:
            try:
                message = conn.recv(3000).decode()
                # print(message)
                if not message:
                    break
                data = json.loads(message)
                # print(data)
                if data["command"].lower() == "login":
                    # print(data["username"])
                    self.add_active_client(data["username"], conn)
                    try:
                        user_info = self.db.retrieve_user(data["username"])
                        if user_info is not None:
                            messages = self.db.retrieve_unread_messages(
                                data["username"]
                            )
                            if messages:
                                payload = json.dumps(
                                    {
                                        "info": user_info.__str__(),
                                        "unread": messages.__str__(),
                                    }
                                )
                                conn.send(payload.encode())
                                bright_magenta(
                                    f"[[LOGIN] {datetime.datetime.now()}]: {data['username']}"
                                )

                            else:
                                conn.send(user_info.encode())
                                bright_magenta(
                                    f"[[LOGIN] {datetime.datetime.now()}]: {data['username']}"
                                )
                        else:
                            conn.send(
                                f"No account with the name '{data['username']}' exists".encode()
                            )
                        bright_magenta(
                            f"[[LOGIN] {datetime.datetime.now()}]: {data['username']}"
                        )
                    except Exception as e:
                        print("Exception: ", e)
                elif data["command"] == "private":
                    message_content = data["message"]
                    with server_thread.lock:
                        if data["recipient"] in server_thread.active_clients:
                            bright_magenta(
                                f"[[MESSAGE] {datetime.datetime.now()}] {data['username']} → {data['recipient']}: {message_content}"
                            )
                            payload = json.dumps(
                                {
                                    "from": data["username"],
                                    "to": data["recipient"],
                                    "message": data["message"],
                                    "time": datetime.datetime.now().strftime(
                                        "%Y-%m-%d %H:%M:%S"
                                    ),
                                }
                            )
                            # send to recipient
                            server_thread.active_clients[data["recipient"]][
                                "conn"
                            ].send(payload.encode())

                            # send success or failure message
                            if self.db.upload_message(
                                data["username"],
                                data["recipient"],
                                "read",
                                "text",
                                message_content,
                            ):
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

                elif data["command"].lower() == "logout":
                    self.logout(data["username"])
                    bright_magenta(
                        f"[LOGOUT] {datetime.datetime.now()}] {data['username']}"
                    )
                elif data["command"].lower() == "join_group":
                    payload = self.add_member(
                        data.get("username"),
                        data.get("group_name"),
                        data.get("password"),
                    )
                    conn.send(payload.encode())
                    bright_magenta(
                        f"[JOIN_GROUP] User '{data['username']}' joined Group '{data.get('group_name')}'"
                    )
                    members = self.db.get_group_members(data.get("group_name"))
                    if members is not None:
                        for m in members:
                            with server_thread.lock:
                                if m in server_thread.active_clients:
                                    conn_ = server_thread.active_clients[m]["conn"]
                                    payload = json.dumps(
                                        {
                                            "from": "SERVER",
                                            "type": "group_text",
                                            "message": f"New member '{data.get('username')}' added to group '{data.get('group_name')}' by '{data.get('username')}'",
                                            "time": datetime.datetime.now().strftime(
                                                "%Y-%m-%d %H:%M:%S"
                                            ),
                                        }
                                    )
                                    conn_.send(payload.encode())
                                else:
                                    self.db.upload_message(
                                        data.get("username"),
                                        m,
                                        "unread group_text",
                                        data.get("group_name")
                                        + " {"
                                        + data.get("username")
                                        + "}",
                                        f"{message}",
                                    )

                elif data["command"].lower() == "ping":
                    self.ping(data["username"])
                    bright_magenta(
                        f"[PING] Server pinged by user: '{data['username']}'"
                    )
                    payload = json.dumps(
                        {
                            "command": "ping",
                            "status": "success",
                            "time": datetime.datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                        }
                    )
                    conn.send(payload.encode())
                elif data["command"].lower() == "create_group":
                    self.create_group(data)
                    payload = json.dumps(
                        {
                            "from": data["username"],
                            "to": data["username"],
                            "time": datetime.datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                        }
                    )
                    conn.send(payload.encode())
                elif data["command"].lower() == "create_account":
                    try:
                        success = self.db.create_user(
                            data["username"], data["password"]
                        )
                        server_thread.active_clients.update(
                            {data["username"]: {"conn": conn, "ping": time.time()}}
                        )
                        f_payload = None
                        if success:
                            f_payload = json.dumps(
                                {
                                    "status": "success",
                                    "process": "create_account",
                                    "time": datetime.datetime.now().strftime(
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
                    except Exception as e:
                        red("Exception: " + e.__str__())
                    with server_thread.lock:
                        server_thread.active_clients.update({data["username"]: conn})
                    bright_magenta(
                        f"[CREATE_ACCOUNT] {datetime.datetime.now()}] : {data['username']}"
                    )
            except psycopg2.errors.Error as e:
                red("Psycopg2 Error: " + e.__str__())
            except Exception as e:
                red("Exception: " + e.__str__())

    def create_group(self, data):
        users = data["members"].replace("[", "").replace("]", "").split(",")
        bright_magenta(f"[CREATE GROUP]: New Group Created ({data['group_name']})")
        for u in users:
            with server_thread.lock:
                if u in server_thread.active_clients:
                    conn = server_thread.active_clients[u]["conn"]
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
                    self.db.upload_group_message(
                        data["username"],
                        u,
                        "read group_text",
                        data["group_name"],
                        f"added to group {data['group_name']} by {data['username']}",
                        data["group_name"],
                    )

                else:
                    self.db.upload_group_message(
                        data["username"],
                        u,
                        "unread group_text",
                        data["group_name"],
                        f"added to group {data['username']}",
                        data["group_name"],
                    )

        if data["username"] not in users:
            users.append(data["username"])
        self.db.create_group(
            data["group_name"],
            users,
            data["password"],
        )

    def message_group(self, username, group_name, message):
        members = self.db.get_group_members(group_name)
        if members is not None:
            for m in members:
                with server_thread.lock:
                    if m in server_thread.active_clients:
                        conn = server_thread.active_clients[m]["conn"]
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
                        print(
                            self.db.upload_group_message(
                                username,
                                m,
                                "unread group_text",
                                group_name + " {" + username + "}",
                                f"{message}",
                                group_name,
                            )
                        )
            return True
        else:
            return False

    def add_member(self, user_to_add, group_name, password):
        if self.db.check_password(group_name, password) is not None:
            self.db.add_member(user_to_add, group_name)
            payload = json.dumps(
                {
                    "command": "join_group",
                    "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "success",
                }
            )
            return payload
        else:
            payload = json.dumps(
                {
                    "command": "join_group",
                    "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "success",
                    "reason": "Password or Group Name is incorrect",
                }
            )
            return payload

    def logout(self, username: str):
        payload = json.dumps(
            {
                "status": "success",
                "process": "logout",
                "date_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        with server_thread.lock:
            if server_thread.active_clients.get(username) is not None:
                try:
                    server_thread.active_clients[username]["conn"].send(
                        payload.encode()
                    )
                    bright_magenta(
                        f"[LOGOUT] User '{username}' has log out at time {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    server_thread.active_clients.pop(username)
                except Exception as e:
                    red("Exception: " + e.__str__())
        pass

    def ping(self, username):
        with server_thread.lock:
            if username in server_thread.active_clients:
                server_thread.active_clients[username]["ping"] = time.time()

    def handle_online_status(self):
        try:
            while True:
                for i in list(server_thread.active_clients.keys()):
                    current = time.time()
                    if (current - server_thread.active_clients[i].get("ping")) > 20:
                        self.logout(i)

                time.sleep(5)
        except Exception as e:
            red("Exception: " + e.__str__())

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
    t = server_thread(None, None, None)
    data = {
        "username": "wyrm",
        "members": '["wyrm", "chi-chi", "grr"]',
        "group_name": "damn",
        "password": "pass",
    }
    # print(t.message_group("wyrm", "damn", "AAAAAAAAAAAAA"))

    pass


if __name__ == "__main__":
    main()
