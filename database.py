import sqlite3

class Database:
    def __init__(self, db_name="bot_database.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # Kalit so'zlar jadvali
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT UNIQUE
            )
        """)
        # Izlovchi guruhlar jadvali
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT UNIQUE,
                group_name TEXT
            )
        """)
        # Shaxsiy guruhlar jadvali
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS private_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT UNIQUE,
                group_name TEXT
            )
        """)
        self.conn.commit()

    # Kalit so'zlar uchun metodlar
    def add_keyword(self, word):
        try:
            self.cursor.execute("INSERT INTO keywords (word) VALUES (?)", (word,))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_keywords(self):
        self.cursor.execute("SELECT * FROM keywords")
        return self.cursor.fetchall()

    def delete_keyword(self, keyword_id):
        self.cursor.execute("DELETE FROM keywords WHERE id = ?", (keyword_id,))
        self.conn.commit()

    # Izlovchi guruhlar uchun metodlar
    def add_search_group(self, group_id, group_name):
        try:
            self.cursor.execute("INSERT INTO search_groups (group_id, group_name) VALUES (?, ?)", (group_id, group_name))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_search_groups(self):
        self.cursor.execute("SELECT * FROM search_groups")
        return self.cursor.fetchall()

    def delete_search_group(self, group_id):
        self.cursor.execute("DELETE FROM search_groups WHERE group_id = ?", (group_id,))
        self.conn.commit()

    # Shaxsiy guruhlar uchun metodlar
    def add_private_group(self, group_id, group_name):
        try:
            self.cursor.execute("INSERT INTO private_groups (group_id, group_name) VALUES (?, ?)", (group_id, group_name))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_private_groups(self):
        self.cursor.execute("SELECT * FROM private_groups")
        return self.cursor.fetchall()

    def delete_private_group(self, group_id):
        self.cursor.execute("DELETE FROM private_groups WHERE group_id = ?", (group_id,))
        self.conn.commit()

db = Database()
