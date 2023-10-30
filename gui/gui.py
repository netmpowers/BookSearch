# gui/gui.py

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from datetime import datetime
from bs4 import BeautifulSoup
from io import StringIO
import pandas as pd
import requests
import time
import keyring
import webbrowser
import smtplib
import sqlite3
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# My own defined db operations file.
from db.database_operations import *

DATABASE = 'bin/BookSearch.db'
ERROR_LOG_FILE = 'error_log.txt'
OUTPUT_LOG_FILE = 'output_log.txt'

def add_search_string(conn, entry_add, search_listbox):
    search_string = entry_add.get().strip()
    if search_string and not db_check_search_string_exists(conn, search_string):
        db_add_search_string(conn, search_string)
        refresh_search_listbox(conn, search_listbox)
    entry_add.delete(0, tk.END)

def import_csv(conn, search_listbox):
    # Open a file dialog to select a CSV file
    file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])

    if file_path:
        # Read the CSV file
        try:
            with open(file_path, 'r') as csv_file:
                lines = csv_file.readlines()
                for line in lines:
                    # Strip leading and trailing whitespace from the line
                    search_string = line.strip()
                    if search_string and not db_check_search_string_exists(conn, search_string):
                        db_add_search_string(conn, search_string)
                refresh_search_listbox(conn, search_listbox)
        except Exception as e:
            print("Error:", e)

def delete_search_string(conn, search_listbox):
    selected_index = search_listbox.curselection()
    if selected_index:
        search_string = search_listbox.get(selected_index)
        db_remove_search_string(conn, search_string)
        refresh_search_listbox(conn, search_listbox)

def refresh_search_listbox(conn, search_listbox):
    search_listbox.delete(0, tk.END)
    search_strings = db_get_all_search_strings(conn)
    for search_string in search_strings:
        search_listbox.insert(tk.END, search_string)

def retrieve_single_item(conn, search_listbox, found_treeview):
    selected_index = search_listbox.curselection()
    if selected_index:
        search_string = search_listbox.get(selected_index)
        
        # Retrieve the search_id associated with the search_string
        search_id = db_get_search_string_id(conn, search_string)
        
        # Perform the search and populate the FoundList
        refresh_found_treeview(conn, search_id, found_treeview)

def refresh_found_treeview(conn, search_id, found_treeview):
    found_treeview.delete(*found_treeview.get_children())
    found_items = db_get_found_items(conn, search_id)
    
    for item in found_items:
        # Extract item data
        item_id, _, item_index, subject, poster, item_group, age = item
        
        # Insert data into the Treeview
        found_treeview.insert("", "end", values=(item_index, subject, poster, item_group, age))

def get_url_data(conn, url, search_id, search_string):
    # Compare the website data to the database
    delta_list = []
    items_to_delete = []
    response = requests.get(url)
    html = response.text
    soup = BeautifulSoup(html, 'html.parser')
    search_table = soup.find("table", class_="xMenuT")
    if search_table:
        # Wrap the HTML string in a StringIO object
        html_string = str(search_table)

        try:
            df = pd.read_html(html_string, header=0, flavor='lxml')[0]
            df = df.drop(columns=['Unnamed: 1'])  # Drop the check box
            df = df.rename(columns={'Unnamed: 0': 'ItemIndex'})
            df = df.rename(columns={'Group': 'ItemGroup'})
            df['Subject'] = df['Subject'].str.strip()
        except Exception as e:
            print("Error reading HTML:", e)

        # Now iterate through db and list any items that are in the database
        # but not in the dataframe
        db_items = db_get_found_items(conn, search_id)
        for db_item in db_items:
            db_subject, db_poster, db_item_group = db_item[3], db_item[4], db_item[5]
            item_exists_in_website = any(
                (db_subject == row['Subject'] and
                 db_poster == row['Poster'] and
                 db_item_group == row['ItemGroup'])
                for _, row in df.iterrows()
            )

            if not item_exists_in_website:
                # Item exists in the database but not in the website, so add its id to the items_to_delete list
                items_to_delete.append(db_item[0])  # item[0] is the primary key

        # Iterate through the DataFrame and compare with items in the database
        for _, row in df.iterrows():
            item_exists_in_db = any(
                item[3] == row['Subject'] and
                item[4] == row['Poster'] and
                item[5] == row['ItemGroup']
                for item in db_items
            )

            if not item_exists_in_db:
                # Add the item to the database
                db_add_found_item(conn, search_id,
                                  row['ItemIndex'],
                                  row['Subject'],
                                  row['Poster'],
                                  row['ItemGroup'],
                                  row['Age'])

                # Add the item to the delta_list
                delta_list.append({
                    'ItemIndex': row['ItemIndex'],
                    'Subject': row['Subject'],
                    'Poster': row['Poster'],
                    'ItemGroup': row['ItemGroup'],
                    'Age': row['Age']
                })

    # Return both delta_list and items_to_delete
    return delta_list, items_to_delete

def get_url(search_string):
    # Converts 'Piers Anthony epub' to
    # 'https://binsearch.info/?q=Piers+Anthony+epub&max=100&adv_age=1100&server='

    # Split the search string into individual words and join them with '+'
    search_query = "+".join(search_string.split())

    # Construct the URL
    url = f"https://binsearch.info/?q={search_query}&max=100&adv_age=1100&server="
    return url

# Create a function to launch the search URL in a web browser
def launch_url(search_string):
    url = get_url(search_string)
    webbrowser.open(url)  # Open the URL in the default web browser


def retrieve_search_items():
    master_dict = {}
    error_log = []

    # Iterate through all the SearchList items and
    # go to binsearch.info to get the latest
    conn = sqlite3.connect(DATABASE)
    search_strings = db_get_all_search_strings(conn)
    for search_string in search_strings:
        url = get_url(search_string)
        search_id = db_get_search_string_id(conn, search_string)

        try:
            # Return a list of additions and deletions for this item
            search_delta, items_to_delete = get_url_data(conn, url, search_id, search_string)
            # Remove items from the database no longer on the website
            db_remove_item_list(conn, search_id, items_to_delete)

            if search_delta:
                master_dict[search_string] = search_delta
            # Don't scrape too fast
            time.sleep(5)
        except Exception as e:
            error_log.append(f"Error for '{search_string}': {str(e)}")

    # Close the database connection
    conn.close()

    # Create a timestamp
    timestamp = datetime.now().strftime('%Y-%m-%d %I:%M:%S %p PST')

    # Create the delta text for both the log file and email body
    delta_text = []
    with open(OUTPUT_LOG_FILE, 'a', encoding='utf-8') as output_file:
        for search_string, delta_list in master_dict.items():
            delta_text.append(f"{timestamp}")
            delta_text.append(f"{search_string}")
            delta_text.append("=" * len(search_string))
            delta_text.append("{:<5} {:<30} {:<30} {:<20} {:<15}".format("Idx", "Subject", "Poster", "ItemGroup", "Age"))
            for delta in delta_list:
                delta_text.append("{:<5} {:<30} {:<30} {:<20} {:<15}".format(delta['ItemIndex'],
                                                                              delta['Subject'],
                                                                              delta['Poster'],
                                                                              delta['ItemGroup'],
                                                                              delta['Age']))
            delta_text.append("")

            # Write the delta text to the log file
            output_file.write("\n".join(delta_text) + "\n")

    # Send an email
    subject = f"NNTP deltas {timestamp}"
    body = "\n".join(delta_text)
    EMAIL_ADDR = 'netmpowers@gmail.com' # Replace with your email address

    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDR
    msg['To']   = EMAIL_ADDR
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    try:
        smtp_server = 'smtp.gmail.com'  # Replace with your SMTP server
        smtp_port = 587                 # Replace with your SMTP port
        smtp_username = EMAIL_ADDR      # Replace with your email address
        smtp_password = keyring.get_password(smtp_server, EMAIL_ADDR)

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        text = msg.as_string()
        server.sendmail(smtp_username, EMAIL_ADDR, text)
        server.quit()
    except Exception as e:
        print("Error sending email:", e)

def save_column_widths(found_treeview):
    # After adjusting column widths
    column_widths = {
        "Indx": found_treeview.column("#1", "width"),
        "Subject": found_treeview.column("#2", "width"),
        "Poster": found_treeview.column("#3", "width"),
        "Item Group": found_treeview.column("#4", "width"),
        "Age": found_treeview.column("#5", "width"),
    }
    
    # Save the column widths to a JSON file
    with open("bin\column_widths.json", "w") as json_file:
        json.dump(column_widths, json_file)

def read_column_widths(found_treeview):
    # Load column widths from the JSON file
    try:
        with open("bin\column_widths.json", "r") as json_file:
            column_widths = json.load(json_file)
    
            # Apply column widths to the Treeview
            for column, width in column_widths.items():
                found_treeview.column(column, width=width)
    except (FileNotFoundError, json.JSONDecodeError):
        # Handle the case when the JSON file doesn't exist yet
        pass

def open_search(search_listbox):
    selected_index = search_listbox.curselection()
    if selected_index:
        search_string = search_listbox.get(selected_index)
        launch_url(search_string)

def on_closing(conn, root, found_treeview):
    conn.close()
    save_column_widths(found_treeview)

    # Save error log to a file
    with open(ERROR_LOG_FILE, 'a') as error_file:
        error_file.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S %p PST')} - Application closed\n")

    root.destroy()

def main_window():
    # Create SQLite database and establish a connection
    db_create_db()
    conn = sqlite3.connect(DATABASE)

    # Create or append the error log file
    with open(ERROR_LOG_FILE, 'a') as error_file:
        error_file.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S %p PST')} - Application started\n")

    # Create the main window
    root = tk.Tk()
    root.title("Search Application")

    # Set the window icon
    icon_path = 'bin/BookSearch.ico'
    if os.path.exists(icon_path):
        root.iconbitmap(icon_path)

    # Left side (Search Strings)
    frame_left = ttk.Frame(root)
    frame_left.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

    label_add = ttk.Label(frame_left, text="Add Search String:")
    label_add.grid(row=0, column=0, columnspan=2, sticky="w")

    entry_add = ttk.Entry(frame_left)
    entry_add.grid(row=1, column=0, columnspan=2, sticky="ew")

    button_add = ttk.Button(frame_left, text="Add", command=lambda: add_search_string(conn, entry_add, search_listbox))
    button_add.grid(row=1, column=2, sticky="w")

    # Create a Listbox widget
    search_listbox = tk.Listbox(frame_left, selectmode=tk.SINGLE)

    # Create a vertical scrollbar for the Listbox
    scrollbar_listbox = ttk.Scrollbar(frame_left, orient=tk.VERTICAL, command=search_listbox.yview)
    search_listbox.config(yscrollcommand=scrollbar_listbox.set)

    # Bind an event handler to the search_listbox selection event
    search_listbox.bind("<<ListboxSelect>>", lambda event: retrieve_single_item(conn, search_listbox, found_treeview))

    # Create the "Delete" button
    button_delete = ttk.Button(frame_left, text="Delete", command=lambda: delete_search_string(conn, search_listbox))
    button_delete.grid(row=1, column=0, columnspan=2, pady=5, sticky="w")
    
    # Create the "Open Search" button next to the "Delete" button
    button_open_search = ttk.Button(frame_left, text="Open Search", command=lambda: open_search(search_listbox))
    button_open_search.grid(row=1, column=2, pady=5, sticky="w")

    # Grid layout for Search Listbox, Scrollbar, and Delete/Open buttons
    label_add.grid(row=0, column=0, columnspan=2, sticky="w")
    entry_add.grid(row=1, column=0, columnspan=2, sticky="ew")
    button_add.grid(row=1, column=2, sticky="w")
    search_listbox.grid(row=2, column=0, columnspan=3, sticky="nsew")
    scrollbar_listbox.grid(row=2, column=3, sticky="ns")
    button_delete.grid(row=3, column=0, columnspan=2, sticky="w")  # Adjust columnspan
    button_open_search.grid(row=3, column=2, sticky="w")  # Adjust column

    # Right side (Found Items)
    frame_right = ttk.Frame(root)
    frame_right.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

    label_found = ttk.Label(frame_right, text="Found Items:")
    label_found.grid(row=0, column=0, sticky="w")

    # Create a Treeview widget with columns
    found_treeview = ttk.Treeview(frame_right,
                                  columns=("Indx", "Subject", "Poster", "Item Group", "Age"),
                                  show="headings")

    # Set column headings
    found_treeview.heading("#1", text="Indx")
    found_treeview.heading("#2", text="Subject")
    found_treeview.heading("#3", text="Poster")
    found_treeview.heading("#4", text="Item Group")
    found_treeview.heading("#5", text="Age")

    # Create a vertical scrollbar for the Treeview
    scrollbar_treeview = ttk.Scrollbar(frame_right, orient=tk.VERTICAL, command=found_treeview.yview)
    found_treeview.config(yscrollcommand=scrollbar_treeview.set)

    # New 'Import CSV' button
    button_import_csv = ttk.Button(frame_right,
                                   text="Import CSV",
                                   command=lambda: import_csv(conn, search_listbox))

    # Grid layout for Found Treeview, Scrollbar, and Import CSV button
    label_found.grid(row=0, column=0, sticky="w")
    found_treeview.grid(row=1, column=0, sticky="nsew")
    scrollbar_treeview.grid(row=1, column=1, sticky="ns")
    button_import_csv.grid(row=2, column=0, columnspan=2, sticky="w")

    # Initialize the Search Listbox
    refresh_search_listbox(conn, search_listbox)

    # Configure the main window to close the connection when closed
    root.protocol("WM_DELETE_WINDOW", lambda: on_closing(conn, root, found_treeview))

    # Grid row and column weights to make the widgets expand properly
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    root.grid_columnconfigure(1, weight=1)
    frame_left.grid_rowconfigure(2, weight=1)
    frame_left.grid_columnconfigure(0, weight=1)
    frame_left.grid_columnconfigure(1, weight=1)
    frame_left.grid_columnconfigure(2, weight=1)

    # Read any saved widths
    read_column_widths(found_treeview)

    root.mainloop()

