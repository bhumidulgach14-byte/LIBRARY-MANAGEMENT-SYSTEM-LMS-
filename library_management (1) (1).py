import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
import tkinter as tk
from tkinter import messagebox
import warnings

warnings.filterwarnings('ignore', category=DeprecationWarning)

class LibraryManagementSystem:
    def __init__(self, db_name: str = "library.db"):
        self.conn = sqlite3.connect(db_name, detect_types=sqlite3.PARSE_DECLTYPES)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS books (
                book_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                isbn TEXT UNIQUE NOT NULL,
                category TEXT,
                total_copies INTEGER NOT NULL,
                available_copies INTEGER NOT NULL,
                publication_year INTEGER,
                added_date TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS members (
                member_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT,
                address TEXT,
                membership_date TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                borrow_date TEXT DEFAULT CURRENT_TIMESTAMP,
                due_date TEXT NOT NULL,
                return_date TEXT,
                fine_amount REAL DEFAULT 0,
                status TEXT DEFAULT 'borrowed',
                FOREIGN KEY (book_id) REFERENCES books(book_id),
                FOREIGN KEY (member_id) REFERENCES members(member_id)
            )
        ''')
        
        self.conn.commit()
    
    def add_book(self, title: str, author: str, isbn: str, category: str, 
                 total_copies: int, publication_year: int) -> Tuple[bool, str]:
        try:
            self.cursor.execute('''
                INSERT INTO books (title, author, isbn, category, total_copies, 
                                 available_copies, publication_year)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (title, author, isbn, category, total_copies, total_copies, publication_year))
            self.conn.commit()
            return True, f"Book '{title}' added successfully!"
        except sqlite3.IntegrityError:
            return False, f"Error: Book with ISBN {isbn} already exists!"
    
    def search_books(self, search_term: str, search_by: str = "title") -> List[Tuple]:
        search_term = f"%{search_term}%"
        
        if search_by == "title":
            query = "SELECT * FROM books WHERE title LIKE ?"
        elif search_by == "author":
            query = "SELECT * FROM books WHERE author LIKE ?"
        elif search_by == "isbn":
            query = "SELECT * FROM books WHERE isbn LIKE ?"
        else:
            return []
        
        self.cursor.execute(query, (search_term,))
        return self.cursor.fetchall()
    
    def get_all_books(self) -> List[Tuple]:
        self.cursor.execute("SELECT * FROM books ORDER BY title")
        return self.cursor.fetchall()
    
    def delete_book(self, book_id: int) -> Tuple[bool, str]:
        try:
            self.cursor.execute('''
                SELECT COUNT(*) FROM transactions 
                WHERE book_id = ? AND status = 'borrowed'
            ''', (book_id,))
            
            if self.cursor.fetchone()[0] > 0:
                return False, "Cannot delete book - it is currently borrowed!"
            
            self.cursor.execute("DELETE FROM books WHERE book_id = ?", (book_id,))
            self.conn.commit()
            return True, "Book deleted successfully!"
        except Exception as e:
            return False, f"Error deleting book: {e}"
    
    def add_member(self, name: str, email: str, phone: str, address: str) -> Tuple[bool, str]:
        try:
            self.cursor.execute('''
                INSERT INTO members (name, email, phone, address)
                VALUES (?, ?, ?, ?)
            ''', (name, email, phone, address))
            self.conn.commit()
            return True, f"Member '{name}' added successfully!"
        except sqlite3.IntegrityError:
            return False, f"Error: Member with email {email} already exists!"
    
    def get_all_members(self) -> List[Tuple]:
        self.cursor.execute("SELECT * FROM members ORDER BY name")
        return self.cursor.fetchall()
    
    def search_members(self, search_term: str) -> List[Tuple]:
        search_term = f"%{search_term}%"
        self.cursor.execute('''
            SELECT * FROM members 
            WHERE name LIKE ? OR email LIKE ?
        ''', (search_term, search_term))
        return self.cursor.fetchall()
    
    def borrow_book(self, book_id: int, member_id: int, days: int = 14) -> Tuple[bool, str]:
        try:
            self.cursor.execute('''
                SELECT available_copies, title FROM books WHERE book_id = ?
            ''', (book_id,))
            book_result = self.cursor.fetchone()
            
            if not book_result:
                return False, "Book not found!"
            
            available_copies, title = book_result
            
            if available_copies <= 0:
                return False, f"Sorry, '{title}' is currently not available!"
            
            self.cursor.execute('''
                SELECT status, name FROM members WHERE member_id = ?
            ''', (member_id,))
            member_result = self.cursor.fetchone()
            
            if not member_result:
                return False, "Member not found!"
            
            status, name = member_result
            
            if status != 'active':
                return False, f"Member '{name}' account is not active!"
            
            due_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
            self.cursor.execute('''
                INSERT INTO transactions (book_id, member_id, due_date)
                VALUES (?, ?, ?)
            ''', (book_id, member_id, due_date))
            
            self.cursor.execute('''
                UPDATE books SET available_copies = available_copies - 1
                WHERE book_id = ?
            ''', (book_id,))
            
            self.conn.commit()
            return True, f"Book '{title}' borrowed successfully by {name}!\nDue date: {due_date}"
            
        except Exception as e:
            self.conn.rollback()
            return False, f"Error processing transaction: {e}"
    
    def return_book(self, transaction_id: int) -> Tuple[bool, str]:
        try:
            self.cursor.execute('''
                SELECT t.book_id, t.due_date, t.status, b.title, m.name
                FROM transactions t
                JOIN books b ON t.book_id = b.book_id
                JOIN members m ON t.member_id = m.member_id
                WHERE t.transaction_id = ?
            ''', (transaction_id,))
            
            result = self.cursor.fetchone()
            
            if not result:
                return False, "Transaction not found!"
            
            book_id, due_date, status, title, member_name = result
            
            if status == 'returned':
                return False, "This book has already been returned!"
            
            return_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            due_date_obj = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
            fine = 0
            
            if datetime.now() > due_date_obj:
                days_late = (datetime.now() - due_date_obj).days
                fine = days_late * 5
            
            self.cursor.execute('''
                UPDATE transactions 
                SET return_date = ?, fine_amount = ?, status = 'returned'
                WHERE transaction_id = ?
            ''', (return_date, fine, transaction_id))
            
            self.cursor.execute('''
                UPDATE books SET available_copies = available_copies + 1
                WHERE book_id = ?
            ''', (book_id,))
            
            self.conn.commit()
            
            msg = f"Book '{title}' returned successfully by {member_name}!"
            if fine > 0:
                msg += f"\nLate return fine: ${fine}"
            else:
                msg += "\nNo fine applied."
            
            return True, msg
            
        except Exception as e:
            self.conn.rollback()
            return False, f"Error processing return: {e}"
    
    def get_borrowed_books(self, member_id: int = None) -> List[Tuple]:
        if member_id:
            self.cursor.execute('''
                SELECT t.transaction_id, b.title, b.author, m.name, t.borrow_date, t.due_date
                FROM transactions t
                JOIN books b ON t.book_id = b.book_id
                JOIN members m ON t.member_id = m.member_id
                WHERE t.member_id = ? AND t.status = 'borrowed'
                ORDER BY t.due_date
            ''', (member_id,))
        else:
            self.cursor.execute('''
                SELECT t.transaction_id, b.title, b.author, m.name, t.borrow_date, t.due_date
                FROM transactions t
                JOIN books b ON t.book_id = b.book_id
                JOIN members m ON t.member_id = m.member_id
                WHERE t.status = 'borrowed'
                ORDER BY t.due_date
            ''')
        
        return self.cursor.fetchall()
    
    def get_summary_stats(self) -> dict:
        stats = {}
        
        self.cursor.execute("SELECT COUNT(*), SUM(total_copies) FROM books")
        result = self.cursor.fetchone()
        stats['total_titles'] = result[0] or 0
        stats['total_copies'] = result[1] or 0
        
        self.cursor.execute("SELECT SUM(available_copies) FROM books")
        stats['available_copies'] = self.cursor.fetchone()[0] or 0
        
        self.cursor.execute("SELECT COUNT(*) FROM members WHERE status = 'active'")
        stats['active_members'] = self.cursor.fetchone()[0] or 0
        
        self.cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'borrowed'")
        stats['borrowed_books'] = self.cursor.fetchone()[0] or 0
        
        current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.cursor.execute('''
            SELECT COUNT(*) FROM transactions 
            WHERE status = 'borrowed' AND due_date < ?
        ''', (current_date,))
        stats['overdue_books'] = self.cursor.fetchone()[0] or 0
        
        return stats
    
    def close(self):
        self.conn.close()


class LibraryGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Library Management System")
        self.root.geometry("1200x700")
        self.root.configure(bg='#2c3e50')
        
        self.library = LibraryManagementSystem()
        self.create_widgets()
        self.show_dashboard()
    
    def create_widgets(self):
        title_frame = tk.Frame(self.root, bg='#34495e', height=80)
        title_frame.pack(fill='x')
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(title_frame, text="📚 LIBRARY MANAGEMENT SYSTEM", 
                              font=('Arial', 24, 'bold'), bg='#34495e', fg='white')
        title_label.pack(pady=20)
        
        main_container = tk.Frame(self.root, bg='#2c3e50')
        main_container.pack(fill='both', expand=True, padx=10, pady=10)
        
        sidebar = tk.Frame(main_container, bg='#34495e', width=200)
        sidebar.pack(side='left', fill='y', padx=(0, 10))
        sidebar.pack_propagate(False)
        
        buttons = [
            ("🏠 Dashboard", self.show_dashboard),
            ("📚 Manage Books", self.show_books),
            ("👥 Manage Members", self.show_members),
            ("🔄 Borrow Book", self.show_borrow),
            ("↩️  Return Book", self.show_return),
            ("📊 View Borrowed", self.show_borrowed),
        ]
        
        for text, command in buttons:
            btn = tk.Button(sidebar, text=text, command=command, 
                          font=('Arial', 12), bg='#3498db', fg='white',
                          relief='flat', padx=20, pady=15, anchor='w')
            btn.pack(fill='x', padx=10, pady=5)
            btn.bind('<Enter>', lambda e, b=btn: b.config(bg='#2980b9'))
            btn.bind('<Leave>', lambda e, b=btn: b.config(bg='#3498db'))
        
        self.content_frame = tk.Frame(main_container, bg='#ecf0f1')
        self.content_frame.pack(side='right', fill='both', expand=True)
    
    def clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()
    
    def show_dashboard(self):
        self.clear_content()
        
        stats = self.library.get_summary_stats()
        
        title = tk.Label(self.content_frame, text="Dashboard", 
                        font=('Arial', 20, 'bold'), bg='#ecf0f1')
        title.pack(pady=20)
        
        stats_frame = tk.Frame(self.content_frame, bg='#ecf0f1')
        stats_frame.pack(pady=20, padx=40, fill='both', expand=True)
        
        stats_data = [
            ("Total Book Titles", stats['total_titles'], '#3498db'),
            ("Total Copies", stats['total_copies'], '#2ecc71'),
            ("Available Copies", stats['available_copies'], '#f39c12'),
            ("Active Members", stats['active_members'], '#9b59b6'),
            ("Borrowed Books", stats['borrowed_books'], '#e74c3c'),
            ("Overdue Books", stats['overdue_books'], '#c0392b'),
        ]
        
        for i, (label, value, color) in enumerate(stats_data):
            row = i // 3
            col = i % 3
            
            card = tk.Frame(stats_frame, bg=color, relief='raised', bd=2)
            card.grid(row=row, column=col, padx=15, pady=15, sticky='nsew')
            
            value_label = tk.Label(card, text=str(value), 
                                  font=('Arial', 32, 'bold'), bg=color, fg='white')
            value_label.pack(pady=(20, 5))
            
            text_label = tk.Label(card, text=label, 
                                 font=('Arial', 12), bg=color, fg='white')
            text_label.pack(pady=(0, 20))
        
        for i in range(3):
            stats_frame.columnconfigure(i, weight=1)
        for i in range(2):
            stats_frame.rowconfigure(i, weight=1)
    
    def show_books(self):
        self.clear_content()
        
        title = tk.Label(self.content_frame, text="Manage Books", 
                        font=('Arial', 20, 'bold'), bg='#ecf0f1')
        title.pack(pady=20)
        
        form_frame = tk.LabelFrame(self.content_frame, text="Add New Book", 
                                   font=('Arial', 12, 'bold'), bg='white', padx=20, pady=20)
        form_frame.pack(padx=20, pady=10, fill='x')
        
        fields = ['Title', 'Author', 'ISBN', 'Category', 'Total Copies', 'Publication Year']
        entries = {}
        
        for i, field in enumerate(fields):
            tk.Label(form_frame, text=field + ":", font=('Arial', 10), bg='white').grid(
                row=i//2, column=(i%2)*2, sticky='w', padx=5, pady=5)
            entry = tk.Entry(form_frame, font=('Arial', 10), width=25)
            entry.grid(row=i//2, column=(i%2)*2+1, padx=5, pady=5)
            entries[field] = entry
        
        def add_book():
            try:
                success, msg = self.library.add_book(
                    entries['Title'].get(),
                    entries['Author'].get(),
                    entries['ISBN'].get(),
                    entries['Category'].get(),
                    int(entries['Total Copies'].get()),
                    int(entries['Publication Year'].get())
                )
                if success:
                    messagebox.showinfo("Success", msg)
                    for entry in entries.values():
                        entry.delete(0, tk.END)
                    refresh_books()
                else:
                    messagebox.showerror("Error", msg)
            except ValueError:
                messagebox.showerror("Error", "Please enter valid numbers for copies and year")
        
        tk.Button(form_frame, text="Add Book", command=add_book, 
                 bg='#2ecc71', fg='white', font=('Arial', 10, 'bold'), 
                 padx=20, pady=5).grid(row=3, column=0, columnspan=4, pady=10)
        
        search_frame = tk.Frame(self.content_frame, bg='#ecf0f1')
        search_frame.pack(padx=20, pady=10, fill='x')
        
        tk.Label(search_frame, text="Search:", font=('Arial', 10), bg='#ecf0f1').pack(side='left', padx=5)
        search_entry = tk.Entry(search_frame, font=('Arial', 10), width=30)
        search_entry.pack(side='left', padx=5)
        
        search_by = ttk.Combobox(search_frame, values=['title', 'author', 'isbn'], 
                                state='readonly', width=10)
        search_by.set('title')
        search_by.pack(side='left', padx=5)
        
        def search_books():
            results = self.library.search_books(search_entry.get(), search_by.get())
            update_tree(results)
        
        tk.Button(search_frame, text="Search", command=search_books, 
                 bg='#3498db', fg='white', font=('Arial', 10), 
                 padx=15, pady=3).pack(side='left', padx=5)
        
        tk.Button(search_frame, text="Show All", command=lambda: update_tree(self.library.get_all_books()), 
                 bg='#95a5a6', fg='white', font=('Arial', 10), 
                 padx=15, pady=3).pack(side='left', padx=5)
        
        list_frame = tk.Frame(self.content_frame, bg='white')
        list_frame.pack(padx=20, pady=10, fill='both', expand=True)
        
        columns = ('ID', 'Title', 'Author', 'ISBN', 'Category', 'Available/Total')
        tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100)
        
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        def update_tree(books):
            tree.delete(*tree.get_children())
            for book in books:
                tree.insert('', 'end', values=(
                    book[0], book[1], book[2], book[3], book[4], 
                    f"{book[6]}/{book[5]}"
                ))
        
        def refresh_books():
            update_tree(self.library.get_all_books())
        
        def delete_book():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a book to delete")
                return
            
            book_id = tree.item(selected[0])['values'][0]
            if messagebox.askyesno("Confirm", "Are you sure you want to delete this book?"):
                success, msg = self.library.delete_book(book_id)
                if success:
                    messagebox.showinfo("Success", msg)
                    refresh_books()
                else:
                    messagebox.showerror("Error", msg)
        
        btn_frame = tk.Frame(self.content_frame, bg='#ecf0f1')
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="Delete Selected", command=delete_book, 
                 bg='#e74c3c', fg='white', font=('Arial', 10), 
                 padx=15, pady=5).pack(side='left', padx=5)
        
        refresh_books()
    
    def show_members(self):
        self.clear_content()
        
        title = tk.Label(self.content_frame, text="Manage Members", 
                        font=('Arial', 20, 'bold'), bg='#ecf0f1')
        title.pack(pady=20)
        
        form_frame = tk.LabelFrame(self.content_frame, text="Add New Member", 
                                   font=('Arial', 12, 'bold'), bg='white', padx=20, pady=20)
        form_frame.pack(padx=20, pady=10, fill='x')
        
        fields = ['Name', 'Email', 'Phone', 'Address']
        entries = {}
        
        for i, field in enumerate(fields):
            tk.Label(form_frame, text=field + ":", font=('Arial', 10), bg='white').grid(
                row=i//2, column=(i%2)*2, sticky='w', padx=5, pady=5)
            entry = tk.Entry(form_frame, font=('Arial', 10), width=30)
            entry.grid(row=i//2, column=(i%2)*2+1, padx=5, pady=5)
            entries[field] = entry
        
        def add_member():
            success, msg = self.library.add_member(
                entries['Name'].get(),
                entries['Email'].get(),
                entries['Phone'].get(),
                entries['Address'].get()
            )
            if success:
                messagebox.showinfo("Success", msg)
                for entry in entries.values():
                    entry.delete(0, tk.END)
                refresh_members()
            else:
                messagebox.showerror("Error", msg)
        
        tk.Button(form_frame, text="Add Member", command=add_member, 
                 bg='#2ecc71', fg='white', font=('Arial', 10, 'bold'), 
                 padx=20, pady=5).grid(row=2, column=0, columnspan=4, pady=10)
        
        search_frame = tk.Frame(self.content_frame, bg='#ecf0f1')
        search_frame.pack(padx=20, pady=10, fill='x')
        
        tk.Label(search_frame, text="Search:", font=('Arial', 10), bg='#ecf0f1').pack(side='left', padx=5)
        search_entry = tk.Entry(search_frame, font=('Arial', 10), width=30)
        search_entry.pack(side='left', padx=5)
        
        def search_members():
            results = self.library.search_members(search_entry.get())
            update_tree(results)
        
        tk.Button(search_frame, text="Search", command=search_members, 
                 bg='#3498db', fg='white', font=('Arial', 10), 
                 padx=15, pady=3).pack(side='left', padx=5)
        
        tk.Button(search_frame, text="Show All", command=lambda: update_tree(self.library.get_all_members()), 
                 bg='#95a5a6', fg='white', font=('Arial', 10), 
                 padx=15, pady=3).pack(side='left', padx=5)
        
        list_frame = tk.Frame(self.content_frame, bg='white')
        list_frame.pack(padx=20, pady=10, fill='both', expand=True)
        
        columns = ('ID', 'Name', 'Email', 'Phone', 'Status')
        tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)
        
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        def update_tree(members):
            tree.delete(*tree.get_children())
            for member in members:
                tree.insert('', 'end', values=(
                    member[0], member[1], member[2], member[3], member[6]
                ))
        
        def refresh_members():
            update_tree(self.library.get_all_members())
        
        refresh_members()
    
    def show_borrow(self):
        self.clear_content()
        
        title = tk.Label(self.content_frame, text="Borrow Book", 
                        font=('Arial', 20, 'bold'), bg='#ecf0f1')
        title.pack(pady=20)
        
        form_frame = tk.LabelFrame(self.content_frame, text="Borrow Details", 
                                   font=('Arial', 12, 'bold'), bg='white', padx=40, pady=30)
        form_frame.pack(padx=20, pady=20)
        
        tk.Label(form_frame, text="Book ID:", font=('Arial', 12), bg='white').grid(
            row=0, column=0, sticky='w', padx=10, pady=10)
        book_id_entry = tk.Entry(form_frame, font=('Arial', 12), width=25)
        book_id_entry.grid(row=0, column=1, padx=10, pady=10)
        
        tk.Label(form_frame, text="Member ID:", font=('Arial', 12), bg='white').grid(
            row=1, column=0, sticky='w', padx=10, pady=10)
        member_id_entry = tk.Entry(form_frame, font=('Arial', 12), width=25)
        member_id_entry.grid(row=1, column=1, padx=10, pady=10)
        
        tk.Label(form_frame, text="Borrow Days:", font=('Arial', 12), bg='white').grid(
            row=2, column=0, sticky='w', padx=10, pady=10)
        days_entry = tk.Entry(form_frame, font=('Arial', 12), width=25)
        days_entry.insert(0, "14")
        days_entry.grid(row=2, column=1, padx=10, pady=10)
        
        def process_borrow():
            try:
                book_id = int(book_id_entry.get())
                member_id = int(member_id_entry.get())
                days = int(days_entry.get())
                
                success, msg = self.library.borrow_book(book_id, member_id, days)
                if success:
                    messagebox.showinfo("Success", msg)
                    book_id_entry.delete(0, tk.END)
                    member_id_entry.delete(0, tk.END)
                    days_entry.delete(0, tk.END)
                    days_entry.insert(0, "14")
                else:
                    messagebox.showerror("Error", msg)
            except ValueError:
                messagebox.showerror("Error", "Please enter valid numbers")
        
        tk.Button(form_frame, text="Borrow Book", command=process_borrow, 
                 bg='#3498db', fg='white', font=('Arial', 12, 'bold'), 
                 padx=30, pady=10).grid(row=3, column=0, columnspan=2, pady=20)
    
    def show_return(self):
        self.clear_content()
        
        title = tk.Label(self.content_frame, text="Return Book", 
                        font=('Arial', 20, 'bold'), bg='#ecf0f1')
        title.pack(pady=20)
        
        form_frame = tk.LabelFrame(self.content_frame, text="Return Details", 
                                   font=('Arial', 12, 'bold'), bg='white', padx=40, pady=30)
        form_frame.pack(padx=20, pady=20)
        
        tk.Label(form_frame, text="Transaction ID:", font=('Arial', 12), bg='white').grid(
            row=0, column=0, sticky='w', padx=10, pady=10)
        trans_id_entry = tk.Entry(form_frame, font=('Arial', 12), width=25)
        trans_id_entry.grid(row=0, column=1, padx=10, pady=10)
        
        def process_return():
            try:
                transaction_id = int(trans_id_entry.get())
                success, msg = self.library.return_book(transaction_id)
                if success:
                    messagebox.showinfo("Success", msg)
                    trans_id_entry.delete(0, tk.END)
                else:
                    messagebox.showerror("Error", msg)
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid transaction ID")
        
        tk.Button(form_frame, text="Return Book", command=process_return, 
                 bg='#e74c3c', fg='white', font=('Arial', 12, 'bold'), 
                 padx=30, pady=10).grid(row=1, column=0, columnspan=2, pady=20)
    
    def show_borrowed(self):
        self.clear_content()
        
        title = tk.Label(self.content_frame, text="Borrowed Books", 
                        font=('Arial', 20, 'bold'), bg='#ecf0f1')
        title.pack(pady=20)
        
        list_frame = tk.Frame(self.content_frame, bg='white')
        list_frame.pack(padx=20, pady=10, fill='both', expand=True)
        
        columns = ('Trans ID', 'Title', 'Author', 'Member', 'Borrow Date', 'Due Date')
        tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            tree.heading(col, text=col)
            if col == 'Title':
                tree.column(col, width=200)
            elif col == 'Author':
                tree.column(col, width=150)
            elif col == 'Member':
                tree.column(col, width=150)
            else:
                tree.column(col, width=100)
        
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        def refresh_borrowed():
            books = self.library.get_borrowed_books()
            tree.delete(*tree.get_children())
            for book in books:
                tree.insert('', 'end', values=book)
        
        btn_frame = tk.Frame(self.content_frame, bg='#ecf0f1')
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="Refresh", command=refresh_borrowed, 
                 bg='#3498db', fg='white', font=('Arial', 10), 
                 padx=20, pady=5).pack(side='left', padx=5)
        
        refresh_borrowed()


def main():
    root = tk.Tk()
    app = LibraryGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()