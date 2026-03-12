import psycopg2
from database.db import DB, HOST
import socket
import json
import datetime
import threading
import time
import re

# from urllib.request import urlopen
# import re as r
import subprocess
from colorist import bright_magenta, red

udp_port = 5960
host = "schaat.duckdns.org"
ping_host = "schaatping.duckdns.org"


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

    def add_active_client(self, username, conn, addr):
        with server_thread.lock:
            server_thread.active_clients.update(
                {username: {"conn": conn, "ping": time.time(), "ip": addr[0]}}
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
                    self.add_active_client(data["username"], conn, addr)
                    try:
                        user_info = self.db.retrieve_user(data["username"])
                        if user_info is not None:
                            messages = self.db.retrieve_unread_messages(
                                data["username"]
                            )
                            print(user_info)
                            if messages:
                                payload = json.dumps(
                                    {
                                        "process": "login",
                                        "status": "success",
                                        "username": user_info["username"],
                                        "password": user_info["password"],
                                        "output_path": user_info["output_path"],
                                        "unread": messages.__str__(),
                                    }
                                )
                                conn.send(payload.encode())
                                bright_magenta(
                                    f"[[LOGIN] {
                                        (
                                            datetime.datetime.now().strftime(
                                                '%Y-%m-%d %H:%M:%S'
                                            ),
                                        )
                                    }]: {data['username']}"
                                )

                            else:
                                conn.send(
                                    json.dumps(
                                        {
                                            "process": "login",
                                            "status": "success",
                                            "username": user_info["username"],
                                            "password": user_info["password"],
                                            "output_path": user_info["output_path"],
                                        }
                                    ).encode()
                                )
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
                elif data["command"] == "output_path":
                    success = self.db.update_output(
                        data["username"], data["password"], data["output_path"]
                    )
                    if success:
                        payload = json.dumps(
                            {
                                "process": "output_path",
                                "status": "success",
                                "username": data["username"],
                                "output_path": data["output_path"],
                                "time": datetime.datetime.now().strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),
                            }
                        )
                        conn.send(payload.encode())
                    else:
                        payload = json.dumps(
                            {
                                "process": "output_path",
                                "status": "fail",
                                "username": data["username"],
                                "output_path": data["output_path"],
                                "time": datetime.datetime.now().strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),
                            }
                        )
                        conn.send(payload.encode())
                elif data["command"] == "private":
                    message_content = data["message"]
                    with server_thread.lock:
                        if data["recipient"] in server_thread.active_clients:
                            print(data["recipient"])
                            bright_magenta(
                                f"[[MESSAGE] {datetime.datetime.now()}] {data['username']} → {data['recipient']}: {message_content}"
                            )
                            payload = json.dumps(
                                {
                                    "username": data["username"],
                                    "recipient": data["recipient"],
                                    "process": "private",
                                    "message": data["message"],
                                    "time": datetime.datetime.now().strftime(
                                        "%Y-%m-%d %H:%M:%S"
                                    ),
                                }
                            )
                            print(message_content)
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
                                        "process": "private",
                                        "recipient_status": "online",
                                        "time": datetime.datetime.now().strftime(
                                            "%Y-%m-%d %H:%M:%S"
                                        ),
                                    }
                                )
                                conn.send(f_payload.encode())

                            else:
                                f_payload = json.dumps(
                                    {
                                        "status": "fail",
                                        "process": "private",
                                        "time": datetime.datetime.now().strftime(
                                            "%Y-%m-%d %H:%M:%S"
                                        ),
                                    }
                                )

                                conn.send(f_payload.encode())
                        else:
                            bright_magenta(
                                f"[[MESSAGE] {datetime.datetime.now()}] {data['username']} → {data['recipient']}: {message_content}"
                            )
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
                                        "process": "private",
                                        "recipient_status": "offline",
                                        "time": datetime.datetime.now().strftime(
                                            "%Y-%m-%d %H:%M:%S"
                                        ),
                                    }
                                )
                                conn.send(f_payload.encode())

                            else:
                                f_payload = json.dumps(
                                    {
                                        "status": "fail",
                                        "process": "private",
                                        "time": datetime.datetime.now().strftime(
                                            "%Y-%m-%d %H:%M:%S"
                                        ),
                                    }
                                )
                                conn.send(f_payload.encode())
                elif data["command"].lower() == "group_message":
                    su = self.message_group(
                        data["username"], data["group_name"], data["message"]
                    )
                    if su:
                        payload = json.dumps(
                            {
                                "command": "group_message",
                                "time": datetime.datetime.now().strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),
                                "status": "success",
                            }
                        )
                        conn.send(payload.encode())
                    else:
                        payload = json.dumps(
                            {
                                "command": "group_message",
                                "time": datetime.datetime.now().strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),
                                "status": "failure",
                            }
                        )
                        conn.send(payload.encode())
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
                                if (
                                    m in server_thread.active_clients
                                    and m != data["username"]
                                ):
                                    conn_ = server_thread.active_clients[m]["conn"]
                                    payload = json.dumps(
                                        {
                                            "from": "SERVER",
                                            "type": "group_text",
                                            "process": "join_group",
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

                # elif data["command"].lower() == "ping":
                #     print("ping")
                #     self.ping()
                #     bright_magenta(
                #         f"[[PING] {
                #             datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                #         }] Server pinged by user: '{data['username']}'"
                #     )
                #     payload = json.dumps(
                #         {
                #             "process": "ping",
                #             "status": "success",
                #             "time": datetime.datetime.now().strftime(
                #                 "%Y-%m-%d %H:%M:%S"
                #             ),
                #         }
                #     )
                #     conn.send(payload.encode())
                elif data["command"].lower() == "create_group":
                    self.create_group(data)
                    payload = json.dumps(
                        {
                            "from": data["username"],
                            "to": data["username"],
                            "time": datetime.datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            "process": "create_group",
                        }
                    )
                    conn.send(payload.encode())
                elif data["command"].lower() == "create_account":
                    try:
                        success = self.db.create_user(
                            data["username"], data["password"], data["output_path"]
                        )
                        server_thread.active_clients.update(
                            {
                                data["username"]: {
                                    "conn": conn,
                                    "ping": time.time(),
                                    "ip": addr[0],
                                }
                            }
                        )
                        if success:
                            f_payload_ = json.dumps(
                                {
                                    "status": "success",
                                    "process": "create_account",
                                    "username": data["username"],
                                    "password": data["password"],
                                    "time": datetime.datetime.now().strftime(
                                        "%Y-%m-%d %H:%M:%S"
                                    ),
                                }
                            )
                            conn.send(f_payload_.encode())
                        else:
                            f_payload_ = json.dumps(
                                {
                                    "status": "fail",
                                    "process": "create_account",
                                    "time": datetime.datetime.now().strftime(
                                        "%Y-%m-%d %H:%M:%S"
                                    ),
                                }
                            )
                            conn.send(f_payload_.encode())
                    except Exception as e:
                        red("Exception: " + e.__str__())
                    with server_thread.lock:
                        server_thread.active_clients.update(
                            {data["username"]: conn, "time": time.time(), "ip": addr[0]}
                        )
                    bright_magenta(
                        f"[CREATE_ACCOUNT] {datetime.datetime.now()}] : {data['username']}"
                    )
                elif data["command"].lower() == "exit_group":
                    payload = self.remove_member(
                        data["username"], data["group_name"], data["password"]
                    )
                    conn.send(payload.encode())
                    bright_magenta(
                        f"[EXIT GROUP] {datetime.datetime.now()}] '{data['username']}' exited group '{data['group_name']}'"
                    )
                elif data["command"].lower() == "file":
                    ips = []
                    for i in server_thread.active_clients:
                        if i != data["username"]:
                            ips.append(i.get("ip"))
                    payload = json.dumps(
                        {"ip": ",".join(ips), "process": "file", "file": data["file"]}
                    )
                    conn.send(payload.encode())
                    bright_magenta(
                        f"[FILE] Client IP request from '{data.get('username')}'"
                    )
            except psycopg2.errors.Error as e:
                red("Psycopg2 Error: " + e.__str__())
            except Exception as e:
                red("Exception: " + e.__str__())

    def create_group(self, data):
        users = re.split(r"[;,\s]+", data["members"].replace("[", "").replace("]", ""))
        bright_magenta(f"[CREATE GROUP]: New Group Created ({data['group_name']})")
        for u in users:
            with server_thread.lock:
                if u in server_thread.active_clients:
                    conn = server_thread.active_clients[u]["conn"]
                    payload = json.dumps(
                        {
                            "process": "added to group",
                            "group_name": data["group_name"],
                            "username": data["username"],
                            "time": datetime.datetime.now().strftime(
                                "%Y-%m-%d %H:%M:?%S"
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
            if username in members:
                for m in members:
                    with server_thread.lock:
                        if m in server_thread.active_clients and m != username:
                            conn = server_thread.active_clients[m]["conn"]
                            payload = json.dumps(
                                {
                                    "username": username,
                                    "process": "group_message",
                                    "group_name": group_name,
                                    "message": message,
                                    "time": datetime.datetime.now().strftime(
                                        "%Y-%m-%d %H:%M:%S"
                                    ),
                                }
                            )
                            conn.send(payload.encode())
                        else:
                            self.db.upload_group_message(
                                username,
                                m,
                                "unread group_text",
                                group_name + " {" + username + "}",
                                f"{message}",
                                group_name,
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
                    "process": "add_member",
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
                    "status": "fail",
                    "reason": "Password or Group Name is incorrect",
                }
            )
            return payload

    def remove_member(self, user_to_remove, group_name, password):
        self.db.exit_group(group_name, user_to_remove)
        payload = json.dumps(
            {
                "process": "exit_group",
                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "success",
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
                        f"[[LOGOUT] {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] : '{username}'"
                    )
                    server_thread.active_clients.pop(username)
                except Exception as e:
                    red("Exception: " + e.__str__())
        pass

    def ping(self):
        global host, udp_port
        sock2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock2.bind(("0.0.0.0", udp_port))
        while True:
            conn, _ = sock2.recvfrom(1024)
            if not conn:
                continue
            data = json.loads(conn.decode())
            username = data["username"]
            with server_thread.lock:
                if username in server_thread.active_clients:
                    server_thread.active_clients[username]["ping"] = time.time()
            bright_magenta(
                f"[[PING] {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]: Server ping from '{username}'"
            )

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
