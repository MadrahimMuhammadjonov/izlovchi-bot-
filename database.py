import sqlite3
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_name='bot_data.db'):
        self.db_name = db_name
        self.init_db()
    
    def get_connection(self):
        return sqlite3.connect(self.db_name)
    
    def init_db(self):
        """Ma'lumotlar bazasini yaratish"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Kalit so'zlar jadvali
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT UNIQUE NOT NULL
            )
        ''')
        
        # Izlovchi guruhlar jadvali
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT UNIQUE NOT NULL,
                group_name TEXT NOT NULL
            )
        ''')
        
        # Shaxsiy guruh jadvali
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS personal_group (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT UNIQUE NOT NULL,
                group_name TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Ma'lumotlar bazasi yaratildi")
    
    # Kalit so'zlar uchun metodlar
    def add_keyword(self, keyword):
        """Kalit so'z qo'shish"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO keywords (keyword) VALUES (?)', (keyword,))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_keywords(self):
        """Barcha kalit so'zlarni olish"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, keyword FROM keywords')
        keywords = cursor.fetchall()
        conn.close()
        return keywords
    
    def delete_keyword(self, keyword_id):
        """Kalit so'zni o'chirish"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM keywords WHERE id = ?', (keyword_id,))
        conn.commit()
        conn.close()
    
    # Izlovchi guruhlar uchun metodlar
    def add_search_group(self, group_id, group_name):
        """Izlovchi guruh qo'shish"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO search_groups (group_id, group_name) VALUES (?, ?)', 
                         (str(group_id), group_name))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_search_groups(self):
        """Barcha izlovchi guruhlarni olish"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, group_id, group_name FROM search_groups')
        groups = cursor.fetchall()
        conn.close()
        return groups
    
    def delete_search_group(self, group_id):
        """Izlovchi guruhni o'chirish"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM search_groups WHERE id = ?', (group_id,))
        conn.commit()
        conn.close()
    
    # Shaxsiy guruh uchun metodlar
    def add_personal_group(self, group_id, group_name):
        """Shaxsiy guruh qo'shish"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            # Avval mavjud guruhni o'chirish
            cursor.execute('DELETE FROM personal_group')
            # Yangi guruh qo'shish
            cursor.execute('INSERT INTO personal_group (group_id, group_name) VALUES (?, ?)', 
                         (str(group_id), group_name))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Xatolik: {e}")
            return False
    
    def get_personal_group(self):
        """Shaxsiy guruhni olish"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT group_id, group_name FROM personal_group LIMIT 1')
        group = cursor.fetchone()
        conn.close()
        return group
    
    def delete_personal_group(self):
        """Shaxsiy guruhni o'chirish"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM personal_group')
        conn.commit()
        conn.close()
