# db/database_operations.py

import sqlite3

DATABASE = 'bin/BookSearch.db'

def db_create_db():
    # Connect to the SQLite database (or create one if it doesn't exist)
    conn = sqlite3.connect(DATABASE)

    # Create a cursor object to execute SQL commands
    cursor = conn.cursor()

    # Create the 'SearchList' table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS SearchList (
            id INTEGER PRIMARY KEY,
            search_string TEXT UNIQUE
        )
    ''')

    # Create the 'FoundList' table with columns from the DataFrame
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS FoundList (
            id INTEGER PRIMARY KEY,
            search_id INTEGER,
            ItemIndex INTEGER,
            Subject TEXT,
            Poster TEXT,
            ItemGroup TEXT,
            Age TEXT,
            FOREIGN KEY (search_id) REFERENCES SearchList(id)
        )
    ''')

    # Commit changes to the database
    conn.commit()
    conn.close()

def db_add_search_string(conn, search_string):
    # Example usage:
    # add_search_string(conn, "Piers Anthony epub")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO SearchList (search_string) VALUES (?)", (search_string,))
        conn.commit()
        return True  # Successfully added the search string
    except sqlite3.Error as e:
        print("Error:", e)
        conn.rollback()
        return False  # Failed to add the search string


def db_check_search_string_exists(conn, search_string):
    # Example usage:
    # exists = check_search_string_exists(conn, "Piers Anthony epub")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM SearchList WHERE search_string=?", (search_string,))
    count = cursor.fetchone()[0]
    return count > 0


def db_get_search_string_id(conn, search_string):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM SearchList WHERE search_string=?", (search_string,))
    result = cursor.fetchone()
    if result is not None:
        return result[0]  # Return the search_id if found
    else:
        return None  # Return None if search_string is not found


def db_get_all_search_strings(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT search_string FROM SearchList")
    search_strings = [row[0] for row in cursor.fetchall()]
    return search_strings

def db_remove_item_list(conn, search_id, item_ids_to_delete):
    try:
        cursor = conn.cursor()
        for item_id in item_ids_to_delete:
            cursor.execute("DELETE FROM FoundList WHERE search_id = ? AND id = ?", (search_id, item_id))
            conn.commit()
    except sqlite3.Error as e:
        print(f"Error deleting items: {e}")
        conn.rollback()  # Rollback changes in case of an error
    finally:
        cursor.close()

def db_remove_search_string(conn, search_string):
    cursor = conn.cursor()
    try:
        # First, get the search_id associated with the search_string
        cursor.execute("SELECT id FROM SearchList WHERE search_string=?", (search_string,))
        search_id = cursor.fetchone()

        if search_id is not None:
            search_id = search_id[0]
            
            # Delete the search string from SearchList
            cursor.execute("DELETE FROM SearchList WHERE search_string=?", (search_string,))
            
            # Delete associated items from FoundList
            cursor.execute("DELETE FROM FoundList WHERE search_id=?", (search_id,))
            
            conn.commit()
            return True  # Successfully removed the search string and associated items
        else:
            return False  # Search string not found
    except sqlite3.Error as e:
        print("Error:", e)
        conn.rollback()
        return False  # Failed to remove the search string


def db_get_found_items(conn, search_id):
    cursor = conn.cursor()
    query = "SELECT * FROM FoundList WHERE search_id=?"
    cursor.execute(query, (search_id,))
    return cursor.fetchall()


def db_add_found_item(conn, search_id, item_index, subject, poster, item_group, age):
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO FoundList (search_id, ItemIndex, Subject, Poster, ItemGroup, Age) VALUES (?, ?, ?, ?, ?, ?)",
            (search_id, item_index, subject, poster, item_group, age))
        conn.commit()
        return True  # Successfully added the found item
    except sqlite3.Error as e:
        print("Error:", e)
        conn.rollback()
        return False  # Failed to add the found item


def db_get_entry_count(conn, search_id):
    # Example usage:
    # entry_count = get_entry_count(conn, 1)  # Replace 1 with the actual search_id
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM FoundList WHERE search_id=?", (search_id,))
    count = cursor.fetchone()[0]
    return count




