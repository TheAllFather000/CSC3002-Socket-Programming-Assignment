from enum import member
import socket
import json
import threading
import time
import re
from colorist import blue, bright_cyan, bright_magenta, green, yellow, red, Color


class Client:
    HOST = "schaat.duckdns.org"
    PORT = 5959

    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.thread = threading.Thread()
        self.username = None
        self.password = None
        self.colour = None
        self.socket.connect((Client.HOST, Client.PORT))

    def get_user_info(self, username, password):
        register_payload = json.dumps(
            {
                "command": "login",
                "username": username,
                "password": password,
            }
        )
        self.socket.send(register_payload.encode())
        message = self.socket.recv(3000)
        if message:
            data = json.loads(message.decode())
            self.username = data["username"]
            self.password = data["password"]

    def create_account(self, username, password):
        register = json.dumps(
            {"username": username, "password": password, "command": "create_account"}
        )
        self.socket.send(register.encode())
        self.username = username
        self.password = password

    def send_message(self, recipient, message):
        payload = json.dumps(
            {
                "command": "private",
                "recipient": recipient,
                "message": message,
                "username": self.username,
            }
        )
        self.socket.send(payload.encode())

    def group_message(self, group_name, message):
        payload = json.dumps(
            {
                "command": "group_message",
                "group_name": group_name,
                "username": self.username,
                "message": message,
            }
        )
        self.socket.send(payload.encode())

    def create_group(self, group_name, password, members):
        payload = json.dumps(
            {
                "command": "create_group",
                "group_name": group_name,
                "password": password,
                "members": "[" + ",".join(members) + "]",
                "username": self.username,
            }
        )
        self.socket.send(payload.encode())

    def join_group(self, group_name, password):
        payload = json.dumps(
            {
                "command": "join_group",
                "group_name": group_name,
                "username": self.username,
                "password": password,
            }
        )
        self.socket.send(payload.encode())

    def exit_group(self, group_name, password):
        payload = json.dumps(
            {
                "command": "exit_group",
                "group_name": group_name,
                "username": self.username,
                "password": password,
            }
        )
        self.socket.send(payload.encode())

    def add_member(self, group_name, password, member_to_add):
        payload = json.dumps(
            {
                "command": "add_member",
                "group_name": group_name,
                "username": member_to_add,
                "password": password,
            }
        )
        self.socket.send(payload.encode())

    def ping(self):
        payload = json.dumps(
            {
                "command": "ping",
                "username": self.username,
            }
        )
        self.socket.send(payload.encode())

    def logout(self):
        payload = json.dumps({"command": "logout", "username": self.username})
        self.socket.send(payload.encode())
        bright_cyan(">>> Logout successful")

        exit(0)

    def ping_manager(self):
        while True:
            self.ping()
            time.sleep(10)

    def incoming_manager(self):
        while True:
            message = self.socket.recv(3000)
            if message:
                message = message.decode()
                data = json.loads(message)
                if data.get("process") == "private":
                    # print(data.get("recipient"))
                    if data.get("recipient") == self.username:
                        green(
                            f"\nMessage received from '{data.get('username')}' @ {data.get('time')}: {data.get('message')}"
                        )
                    # bright_cyan(">>> Message sent successfully")
                elif data.get("process") == "added to group":
                    green(
                        f"\nMessage received from '{data.get('username')}' @ {data.get('time')}: Added to group {data.get('group_name')}"
                    )
                    print()
                elif data.get("process") == "group_text":
                    green(
                        f"\nMessage received from '{data.get('group_name')}':'{data.get('username')}' @ {data.get('time')}: {data.get('message')}"
                    )


ascii_art = """
 SSSSS   CCCCC  H   H    A    TTTTT
S        C      H   H   A A     T  
 SSS     C      HHHHH  AAAAA    T  
    S    C      H   H  A   A    T  
 SSSSS   CCCCC  H   H  A   A    T
"""


def main():
    yellow(ascii_art)
    client = Client()
    thread = threading.Thread(target=client.incoming_manager, daemon=True)
    thread2 = threading.Thread(target=client.ping_manager, daemon=True)

    while True:
        bright_cyan(
            "Commands: login | create_account | private | create_group | join_group | exit_group | broadcast | logout"
        )
        command = input(Color.YELLOW + ">>> " + Color.OFF)
        command = command.lower()
        if command == "login":
            if not client.username:
                username = input(Color.BLUE + ">Username: " + Color.BLUE).strip()
                if not username:
                    red("Please input appropriate values for Username")
                    continue
                password = input(Color.BLUE + ">Password: " + Color.BLUE).strip()
                if not password:
                    red("Please input appropriate values for Password")
                    continue
                client.get_user_info(username, password)
                thread.start()
                thread2.start()
                bright_cyan(">>> Login successful")

            else:
                red(f"Current user '{client.username}' is already logged in.")

        elif command == "private":
            if not client.username:
                red("Please login before sending commands")
                continue
            receiver = input(Color.YELLOW + ">To: " + Color.OFF).strip()
            if not receiver:
                red("Please input appropriate values for the recipient")
                continue
            message = input(Color.YELLOW + ">Message: " + Color.YELLOW).strip()
            if not message:
                red("Please input appropriate values for the message to be sent")
                continue
            client.send_message(receiver, message)
            bright_cyan(">>> Message sent successfully")

        elif command == "create_group":
            if not client.username:
                red("Please login before sending commands")
                continue
            else:
                group_name = input(Color.YELLOW + ">Group Name: " + Color.OFF).strip()
                password = input(Color.YELLOW + ">Password: " + Color.OFF).strip()
                members = input(
                    Color.YELLOW + ">Members (comma-seperated): " + Color.OFF
                ).strip()
                if not members:
                    red("Please input appropriate values for Members")
                    continue
                member_list = re.split(r"[;,\s]+", members)
                for i in range(len(member_list)):
                    member_list[i] = '"' + member_list[i] + '"'
                client.create_group(group_name, password, member_list)
                bright_cyan(f">>> Group '{group_name}' created successfully")

        elif command == "join_group":
            if not client.username:
                red("please login before sending commands")
                continue
            group_name = input(Color.YELLOW + ">group name: " + Color.OFF).strip()
            if not group_name:
                red("please input appropriate values for group name")
                continue
            password = input(Color.YELLOW + ">password: " + Color.OFF).strip()
            if not password:
                red("please input appropriate values for password")
                continue
            client.join_group(group_name, password)
            bright_cyan(f">>> Group '{group_name}' joined successfully")

        elif command == "exit_group":
            if not client.username:
                red("please login before sending commands")
                continue
            group_name = input(Color.YELLOW + ">group name: " + Color.YELLOW).strip()
            if not group_name:
                red("please input appropriate values for group name")
                continue

            client.exit_group(group_name, client.password)
            bright_cyan(f">>> Group '{group_name}' exited successfully")

        elif command == "logout":
            if not client.username:
                red("please login before sending commands")
                continue
            client.logout()

        elif command == "broadcast":
            if not client.username:
                red("please login before sending commands")
                continue
            group_name = input(Color.YELLOW + ">group name: " + Color.OFF).strip()
            if not group_name:
                red("please input appropriate values for group name")
                continue
            message = input(Color.YELLOW + ">message: " + Color.OFF).strip()
            if not message:
                red("please input appropriate values for the message to be sent")
            client.group_message(group_name, message)
            bright_cyan(f">>> Broadcast to group '{group_name}' successful")

        elif command == "create_account":
            username = input(Color.YELLOW + ">Username: " + Color.OFF).strip()
            if not username:
                red("please input appropriate values for group name")
                continue
            password = input(Color.YELLOW + ">Password: " + Color.OFF).strip()
            if not password:
                red("please input appropriate values for password")
                continue
            client.create_account(username, password)
            bright_cyan(f">>> Acccount '{username}' created successfully")
        else:
            red("[error] please input a valid command")
            continue


if __name__ == "__main__":
    main()

# client = socket.socket(socket.af_inet, socket.sock_stream)
# client.connect((host, port))
#
# # register
# # register_payload = json.dumps({"type": "login", "username": "wyrm"})
# # client.send(register_payload.encode())
# # while true:
# #     m = client.recv(3000)
# #     if not m:
# #         break
# #     data = json.loads(m.decode())
# #     print(data)
# #     break
# # # send message
#
# register_payload = json.dumps(
#     {
#         "command": "login",
#         "username": "wyrm",
#         "password": "pass",
#         "message": "hi teeheeee",
#         "recipient": "wyrm",
#         "colour": "blueish",
#     }
# )
# client.send(register_payload.encode())
# while true:
#     m = client.recv(3000)
#     if not m:
#         break
#     data = json.loads(m.decode())
#     print(data)
#     break
# m = client.recv(3000)
# data = json.loads(m.decode())
# print(data)
# print(1)
# # register_payload = json.dumps(
# #     {
# #         "type": "create_account",
# #         "username": "chi-chi",
# #         "password": "testp",
# #         "colour": json.dumps({"r": 100, "g": 0, "b": 0}),
# #     }
# # )
# # client.send(register_payload.encode())
# # while true:
# #     m = client.recv(3000)
# #     if not m:
# #         break
# #     data = json.loads(m.decode())
# #     print(data)
# #     break
# # register_payload = json.dumps({"type": "logout", "username": "wyrm"})
# # client.send(register_payload.encode())
# # while true:
# #     m = client.recv(3000)
# #     if not m:
# #         break
# #     data = json.loads(m.decode())
# #     print(data)
# #     break
# # print("done")
# #
# # while true:
# #     pass
