import socket
import json

HOST = "127.0.0.1"
PORT = 5958

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
        "type": "send_private_message",
        "username": "wyrm",
        "message": "hi teeheeee",
        "recipient": "wyrm",
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
