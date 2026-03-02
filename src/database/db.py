import psycopg2
import json

DATABASE = "socket_db"
USER = "server_socket"
PASSWORD = "Yellowbeansaregreeninpalehaven123!"
HOST = "localhost"
PORT = 5432
INSERT_QUERY_USERS = """
        INSERT INTO user_info(username, password)
        VALUES ('{user}', '{pass_}');
    """

INSERT_QUERY_MESSAGES = """
        INSERT INTO messages(sender, recipient, status, type, content)
        VALUES ('{sen}', '{rec}', '{stat}', '{type_}', '{cont}');
    """


SELECT_USERS = """
    SELECT username, colour FROM user_info 
    WHERE username = '{user}';
"""
SELECT_USERS_ALL = """
    SELECT username, colour FROM user_info;
"""

SELECT_MESSAGES = """
    SELECT * FROM messages 
    WHERE recipient = '{r}' AND sender = '{s}';
"""
SELECT_MESSAGES_UNREAD = """
    SELECT * FROM messages 
    WHERE recipient= '{r}' AND
    WHERE messages.status = 'unread';
"""

# connection object
connection_params = {
    "dbname": DATABASE,
    "user": USER,
    "password": PASSWORD,
    "host": HOST,
    "port": PORT,
}
connection = None


class DB:
    def __init__(self):
        self.connection = psycopg2.connect(**connection_params)

    def create_user(self, username: str, password: str):
        cursor = self.connection.cursor()
        try:
            cursor.execute(INSERT_QUERY_USERS.format(user=username, pass_=password))
            self.connection.commit()
            return True
        except psycopg2.errors.UniqueViolation as e:
            self.connection.rollback()
            print("UniqueViolation Error: ", e)
            return False
        except Exception as e:
            print("Error: ", e)
            return False

    def create_group(self, group_name, members: list):
        cursor = self.connection.cursor()
        m = "'{" + ",".join(members) + "}'"
        try:
            cursor.execute(
                f"INSERT INTO groups(group_name, members) VALUES({group_name},{m});"
            )
            self.connection.commit()
            return True
        except psycopg2.errors.UniqueViolation as uv:
            self.connection.rollback()
            print("UniqueViolation: ", uv)
            return False
        except psycopg2.errors.Error as pe:
            self.connection.rollback()
            print("Psycopg error: ", pe)
            return False
        except Exception as e:
            self.connection.rollback()
            print("Exception: ", e)
            return False

    def get_group_members(self, group_name):
        cursor = self.connection.cursor()

        try:
            cursor.execute(
                f"SELECT members FROM groups WHERE group_name = '{group_name}'"
            )
            return cursor.fetchone()[0]
        except psycopg2.errors.UniqueViolation as uv:
            print("UniqueViolation: ", uv)
            return None
        except psycopg2.errors.Error as pe:
            print("Psycopg error: ", pe)
            return None
        except Exception as e:
            print("Exception: ", e)
            return None

    def retrieve_user(self, username: str):
        cursor = self.connection.cursor()
        try:
            cursor.execute(SELECT_USERS.format(user=username))
            response = cursor.fetchall()
            data = json.dumps({"username": response[0][0], "colour": response[0][1]})
            print(data)
            return data
        except psycopg2.errors.Error as e:
            print("Psycopg Error: ", e)
            return None
        except Exception as e:
            print("Exception: ", e)
            return None

    def retrieve_all_users(self):
        cursor = self.connection.cursor()
        try:
            cursor.execute(SELECT_USERS_ALL)
            response = cursor.fetchall()
            data = {}
            for i in response:
                data.update({i: response[i]})

            return data
        except psycopg2.errors.Error as e:
            print("Psycopg Error", e)
            return None
        except Exception as e:
            print("Exception: ", e)
            return None

    def upload_message(
        self, sender: str, recipient: str, status: str, type: str, content: str
    ):
        cursor = self.connection.cursor()

        try:
            cursor.execute(
                INSERT_QUERY_MESSAGES.format(
                    se=sender, rec=recipient, stat=status, type_=type, cont=content
                )
            )
            self.connection.commit()
            return True
        except Exception as e:
            self.connection.rollback()
            print("Exception: ", e)
            return False

    def retrieve_unread_messages(self, username: str):
        cursor = self.connection.cursor()
        try:
            cursor.execute(SELECT_MESSAGES_UNREAD.format(r=username))
            response = cursor.fetchall()
            data = {}
            for i in response:
                data.update({i: response[i]})

            return data
        except psycopg2.errors.Error as e:
            print("Database Error: ", e)
            return None
        except Exception as e:
            print("Exception e", e)
            return None

    def retrieve_messages(self, username: str, sender: str):
        cursor = self.connection.cursor()
        try:
            cursor.execute(SELECT_MESSAGES.format(r=username, s=sender))
            response = cursor.fetchall()
            data = {}
            for i in response:
                data.update({i: response[i]})

            return data
        except psycopg2.errors.Error as e:
            print("Database Exception", e)
            return None


def main():
    d = DB()
    print(d.retrieve_all_users())


# print(__name__)
# print(__file__)
if __name__ == "__main__":
    main()
