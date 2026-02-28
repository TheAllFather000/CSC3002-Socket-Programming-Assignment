import socket
from database.db import DB

d = DB()
print(d.retrieve_user("wyrm"))
