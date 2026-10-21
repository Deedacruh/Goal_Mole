import os
import sqlite3
currentdirectory = os.path.dirname(os.path.abspath(__file__))

def get_conn():
    connection = sqlite3.connect(os.path.join(currentdirectory, "../profile.db"))
    cursor = connection.cursor()
    return (connection, cursor)