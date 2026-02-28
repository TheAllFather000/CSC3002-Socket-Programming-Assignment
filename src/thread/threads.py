from database.db import DB


class thread:
    def __init__(self):
        self.db = DB()
        self.clients = {}

    def check_client_status(self, username: str):
        pass
