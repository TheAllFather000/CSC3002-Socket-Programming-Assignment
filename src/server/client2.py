import socket
import json

HOST = "127.0.0.1"
PORT = 5959

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((HOST, PORT))

# Register
# register_payload = json.dumps({"type": "LOGIN", "username": "wyrm"})
# client.send(register_payload.encode())
# while True:
#     m = client.recv(3000)
#     if not m:
#         break
#     data = json.loads(m.decode())
#     print(data)
#     break
# # send message

register_payload = json.dumps(
    {
        "command": "login",
        "username": "chi-chi",
        "password": "testp",
        "message": "hi teeheeee",
        "recipient": "chi-chi",
        "colour": "blueish",
    }
)
client.send(register_payload.encode())
while True:
    m = client.recv(3000)
    if not m:
        break
    data = json.loads(m.decode())
    print(data)
    break
register_payload = json.dumps(
    {
        "command": "exit_group",
        "username": "chi-chi",
        "password": "1333",
        "group_name": "trio",
    }
)
client.send(register_payload.encode())
while True:
    m = client.recv(3000)
    if not m:
        break
    data = json.loads(m.decode())
    print(data)
    break
while True:
    m = client.recv(3000)
    if not m:
        break
    print(m)
    data = json.loads(m.decode())
    if data["process"] == "logout":
        print("JAAAAA")
        break

# m = client.recv(3000)
# data = json.loads(m.decode())
# print(data)
# print(1)
#

# register_payload = json.dumps(
#     {
#         "type": "create_account",
#         "username": "chi-chi",
#         "password": "testp",
#         "colour": json.dumps({"r": 100, "g": 0, "b": 0}),
#     }
# )
# client.send(register_payload.encode())
# while True:
#     m = client.recv(3000)
#     if not m:
#         break
#     data = json.loads(m.decode())
#     print(data)
#     break
# register_payload = json.dumps({"type": "LOGOUT", "username": "wyrm"})
# client.send(register_payload.encode())
# while True:
#     m = client.recv(3000)
#     if not m:
#         break
#     data = json.loads(m.decode())
#     print(data)
#     break
# print("done")
#
# while True:
#     pass
