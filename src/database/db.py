import psycopg2
import json
import random
import traceback

DATABASE = "socket_db"
USER = "server_socket"
PASSWORD = "Yellowbeansaregreeninpalehaven123!"
HOST = "localhost"
PORT = 5432
INSERT_QUERY_USERS = """
        INSERT INTO user_info(username, password, colour, output_path)
        VALUES ('{user}', '{pass_}', '{colour_}', '{op}');
    """

INSERT_QUERY_MESSAGES = """
        INSERT INTO messages(sender, recipient, status, type, content)
        VALUES ('{sen}', '{rec}', '{stat}', '{type_}', '{cont}');
    """
INSERT_QUERY_MESSAGES_GROUP = """
        INSERT INTO messages(sender, recipient, status, type, content, group_)
        VALUES ('{sen}', '{rec}', '{stat}', '{type_}', '{cont}', '{grp}');
    """


SELECT_USERS = """
    SELECT username, password, colour, output_path FROM user_info 
    WHERE username = '{user}';
"""
SELECT_USERS_ALL = """
    SELECT username, colour, output_path FROM user_info;
"""

SELECT_MESSAGES = """
    SELECT * FROM messages 
    WHERE recipient = '{r}' AND sender = '{s}';
"""
SELECT_MESSAGES_UNREAD = """
    SELECT recipient, sender, type, content FROM messages 
    WHERE recipient= '{r}' AND
    messages.status LIKE '%unread%';
"""

UPDATE_UNREAD = """
UPDATE messages set status = 'read' WHERE recipient = '{r}' and messages.status LIKE '%unread%';
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

    def create_user(self, username: str, password: str, output: str):
        colour = {
            '"r"': random.randint(0, 255),
            '"g"': random.randint(0, 255),
            '"b"': random.randint(0, 255),
        }
        colours = json.dumps(colour)
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                INSERT_QUERY_USERS.format(
                    user=username, pass_=password, colour_=colours, op=output
                )
            )
            self.connection.commit()
            return True
        except psycopg2.errors.UniqueViolation as e:
            self.connection.rollback()
            print("UniqueViolation Error: ", e)
            return False
        except Exception as e:
            self.connection.rollback()
            print("Error: ", e)
            return False

    def create_group(self, group_name, members: list, password):
        cursor = self.connection.cursor()
        m = "'{" + ",".join(members) + "}'"
        try:
            cursor.execute(
                f"INSERT INTO groups(group_name, members, password) VALUES('{group_name}',{m}, '{password}');"
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

    def delete_group(self, group_name, password):
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                f"DELETE FROM groups where group_name = '{group_name}' AND password = '{password}'"
            )
            self.connection.commit()
            return True
        except psycopg2.errors.Error as e:
            self.connection.rollback()
            print("Psycopg error: ", e)
            return False
        except Exception as e:
            self.connection.rollback()
            print("Exception: ", e)
            return False

    def exit_group(self, group_name, member):
        cursor = self.connection.cursor()
        try:
            print(
                f"UPDATE groups set members = array_remove(members, '{member}') WHERE group_name = '{group_name}'"
            )
            cursor.execute(
                f"UPDATE groups set members = array_remove(members, '{member}') WHERE group_name = '{group_name}'"
            )
            self.connection.commit()
            return True
        except psycopg2.errors.Error as e:
            self.connection.rollback()
            print("Psycopg error: ", e)
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

    def check_password(self, group_name, password):
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                f"SELECT * FROM groups where group_name = '{group_name}' and password = '{password}'"
            )
            response = cursor.fetchall()
            if response is None or len(response) == 0:
                return None
            return response
        except psycopg2.errors.UniqueViolation as uv:
            self.connection.rollback()
            print("UniqueViolation: ", uv)
            return None
        except psycopg2.errors.Error as pe:
            self.connection.rollback()
            print("Psycopg error: ", pe)
            return None
        except Exception as e:
            print("Exception: ", e)
            return None

    def add_member(self, member, group):
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                f"UPDATE groups set members = array_append(members, '{member}') WHERE group_name = '{group}'"
            )
            self.connection.commit()
            return True
        except psycopg2.errors.UniqueViolation as uv:
            self.connection.rollback()
            print("UniqueViolation: ", uv)
            return None
        except psycopg2.errors.Error as pe:
            self.connection.rollback()
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
            if response:
                data = {
                    "username": response[0][0],
                    "colour": response[0][2],
                    "password": response[0][1],
                    "output_path": response[0][3],
                }

                return data
            return None
        except psycopg2.errors.Error as e:
            print("Psycopg Error: ", e)
            return None
        except Exception as e:
            print("Exception: ", e)
            return None

    def update_output(self, username, password, output):
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                f"UPDATE user_info SET output_path = '{output}' WHERE username = '{username}' AND password = '{password}'"
            )
            self.connection.commit()
            return True
        except psycopg2.errors.Error as e:
            self.connection.rollback()
            print("Psycopg error: ", e)
            return False
        except Exception as e:
            self.connection.rollback()
            print("Exception: ", e)
            return False

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
                    sen=sender, rec=recipient, stat=status, type_=type, cont=content
                )
            )
            self.connection.commit()
            return True
        except Exception as e:
            self.connection.rollback()
            print("Exception: ", e)
            traceback.print_exc()
            return False

    def upload_group_message(
        self,
        sender: str,
        recipient: str,
        status: str,
        type: str,
        content: str,
        group_: str,
    ):
        cursor = self.connection.cursor()
        recipient = recipient.replace('"', "")
        try:
            cursor.execute(
                INSERT_QUERY_MESSAGES.format(
                    sen=sender,
                    rec=recipient,
                    stat=status,
                    type_=type,
                    cont=content,
                    grp=group_,
                )
            )
            self.connection.commit()
            return True
        except Exception as e:
            self.connection.rollback()
            print("Exception: ", e)
            traceback.print_exc()
            return False

    def retrieve_unread_messages(self, username: str):
        cursor = self.connection.cursor()
        try:
            cursor.execute(SELECT_MESSAGES_UNREAD.format(r=username))
            response = cursor.fetchall()
            data = {}
            for i in range(len(response)):
                data.update({i: response[i]})
            self.update_unread(username)
            return data
        except psycopg2.errors.Error as e:
            print("Database Error: ", e)
            return None
        except Exception as e:
            print("Exception e", e)
            return None

    def update_unread(self, username: str):
        cursor = self.connection.cursor()
        try:
            cursor.execute(UPDATE_UNREAD.format(r=username))
            self.connection.commit()
            return True
        except psycopg2.errors.Error as e:
            self.connection.rollback()
            print("Psycopg Error", e)
        except Exception as e:
            self.connection.rollback()
            print("Exception: ", e)
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
    print(d.retrieve_unread_messages("chi-chi"))
    d.update_unread("wyrm")


# print(__name__)
# print(__file__)
if __name__ == "__main__":
    main()
