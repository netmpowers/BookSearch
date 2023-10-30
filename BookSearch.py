# 2023-09-02 Manny
# App to automate search binsearch.info for specific
# books I'm interested in.
#
# BookSearch.py

import argparse
import os

from gui.gui import main_window, retrieve_search_items
from db.database_operations import db_create_db

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Book Search Application")
    parser.add_argument("-r", "--retrieve", action="store_true", help="Retrieve search items")
    args = parser.parse_args()

    if args.retrieve:
        # Perform retrieval logic here
        db_create_db()  # Ensure the database is created before retrieval
        retrieve_search_items()
        exit()

    main_window()

