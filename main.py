import sqlite3
from contextlib import contextmanager
from pathlib import Path
import re
from datetime import datetime
import pandas as pd
from tkinter import filedialog, messagebox
import tkinter as tk
from tkinter import ttk
import sqlite3 as sqlite3_reports
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

DB_FILE = Path("invoicing.db")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("""
    CREATE TABLE IF NOT EXISTS partners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        tax_id TEXT,
        email TEXT,
        phone TEXT,
        address TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT UNIQUE,
        name TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL CHECK(price >= 0),
        stock INTEGER DEFAULT 0 CHECK(stock >= 0)
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        partner_id INTEGER NOT NULL,
        invoice_date TEXT NOT NULL,
        due_date TEXT,
        status TEXT DEFAULT 'Draft',
        total_amount REAL DEFAULT 0,
        FOREIGN KEY(partner_id) REFERENCES partners(id) ON DELETE SET NULL
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS invoice_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL CHECK(quantity>0),
        unit_price REAL NOT NULL,
        line_total REAL NOT NULL,
        FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
        FOREIGN KEY(product_id) REFERENCES products(id)
    )
    """)
    conn.commit()
    conn.close()

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.commit()
        conn.close()

def fetchall(sql, params=()):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()

def fetchone(sql, params=()):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchone()

def execute(sql, params=()):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.lastrowid

EMAIL_RE = re.compile(r"^[^@]+@[^@]+\.[^@]+$")

def is_float(v):
    try:
        float(v)
        return True
    except:
        return False

def is_int(v):
    try:
        int(v)
        return True
    except:
        return False

def validate_email(email):
    if not email:
        return True
    return EMAIL_RE.match(email) is not None

def validate_date_iso(s):
    if not s:
        return True
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except:
        return False

def validate_partner_row(row):
    errors = []
    fields = ["name", "tax_id", "email", "phone", "address"]
    for field in fields:
        value = str(row.get(field) or "").strip()
        if not value:
            errors.append(f"{field} is REQUIRED - cannot be empty")
        elif field == "email" and value and not validate_email(value):
            errors.append(f"{field} format is invalid")
    return errors

def validate_product_row(row):
    errors = []
    fields = ["sku", "name", "description", "price", "stock"]
    for field in fields:
        value = str(row.get(field) or "").strip()
        if not value:
            errors.append(f"{field} is REQUIRED - cannot be empty")
    if row.get("price") and not is_float(row.get("price")):
        errors.append("price must be a valid number")
    if row.get("stock") and not is_int(row.get("stock")):
        errors.append("stock must be a valid integer")
    return errors

def validate_invoice_row(row):
    errors = []
    fields = ["partner_id", "invoice_date", "due_date", "status"]
    for field in fields:
        value = row.get(field)
        if not value:
            errors.append(f"{field} is REQUIRED - cannot be empty")
    if row.get("partner_id") and not isinstance(row.get("partner_id"), int):
        errors.append("partner_id must be a valid number")
    if row.get("invoice_date") and not validate_date_iso(row.get("invoice_date")):
        errors.append("invoice_date must be YYYY-MM-DD format")
    if row.get("due_date") and not validate_date_iso(row.get("due_date")):
        errors.append("due_date must be YYYY-MM-DD format")
    return errors

def validate_invoice_item_row(row):
    errors = []
    required_fields = ["invoice_id", "product_id", "quantity"]
    for field in required_fields:
        value = row.get(field)
        if not value:
            errors.append(f"{field} is REQUIRED - cannot be empty")
    if row.get("invoice_id") and not isinstance(row.get("invoice_id"), int):
        errors.append("invoice_id must be a valid number")
    if row.get("product_id") and not isinstance(row.get("product_id"), int):
        errors.append("product_id must be a valid number")
    if row.get("quantity") and not isinstance(row.get("quantity"), int):
        errors.append("quantity must be a positive integer")
    return errors

def export_table_to_csv(table):
    path = filedialog.asksaveasfilename(defaultextension=".csv",
                                        filetypes=[("CSV files", "*.csv")])
    if not path:
        return
    df = pd.read_sql_query(f"SELECT * FROM {table}", sqlite3.connect("invoicing.db"))
    df.to_csv(path, index=False)
    messagebox.showinfo("Export", f"{table} exported to {path}")

def import_partners_csv():
    path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
    if not path:
        return
    df = pd.read_csv(path, dtype=str).fillna("")
    expected_basic = ["name", "tax_id", "email", "phone", "address"]
    expected_with_id = ["id"] + expected_basic
    if list(df.columns) not in [expected_basic, expected_with_id]:
        messagebox.showerror("Import error", f"File columns must be exactly: {expected_basic} or {expected_with_id}")
        return
    errors = []
    added = 0
    for i, row in df.iterrows():
        data = row.to_dict()
        if "id" in data:
            del data["id"]
        err = validate_partner_row(data)
        if err:
            errors.append(f"Row {i + 1}: {err}")
            continue
        try:
            execute("INSERT INTO partners (name,tax_id,email,phone,address) VALUES (?,?,?,?,?)",
                    (data["name"], data["tax_id"] or None, data["email"] or None,
                     data["phone"] or None, data["address"] or None))
            added += 1
        except Exception as e:
            errors.append(f"Row {i + 1}: DB {e}")
    messagebox.showinfo("Import partners", f"Added {added} rows. Errors: {len(errors)}")
    if errors:
        messagebox.showwarning("Import warnings", "\n".join(errors[:20]))

def import_products_csv():
    path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
    if not path:
        return
    df = pd.read_csv(path, dtype=str).fillna("")
    expected_basic = ["sku", "name", "description", "price", "stock"]
    expected_with_id = ["id"] + expected_basic
    if list(df.columns) not in [expected_basic, expected_with_id]:
        messagebox.showerror("Import error", f"File columns must be exactly: {expected_basic} or {expected_with_id}")
        return
    errors = []
    added = 0
    for i, row in df.iterrows():
        data = row.to_dict()
        if "id" in data:
            del data["id"]
        err = validate_product_row(data)
        if err:
            errors.append(f"Row {i + 1}: {err}")
            continue
        try:
            execute("INSERT INTO products (sku,name,description,price,stock) VALUES (?,?,?,?,?)",
                    (data["sku"], data["name"], data["description"],
                     float(data["price"]), int(data["stock"] or 0)))
            added += 1
        except Exception as e:
            errors.append(f"Row {i + 1}: DB {e}")
    messagebox.showinfo("Import products", f"Added {added} rows. Errors: {len(errors)}")
    if errors:
        messagebox.showwarning("Import warnings", "\n".join(errors[:20]))

DB = "invoicing.db"

def open_reports_window(parent):
    win = tk.Toplevel(parent)
    win.title("Reports — NovaInvoice")
    win.geometry("900x650")
    toolbar = ttk.Frame(win)
    toolbar.pack(fill="x", padx=8, pady=8)
    canvas_frame = ttk.Frame(win)
    canvas_frame.pack(fill="both", expand=True, padx=8, pady=8)

    def clear_canvas():
        for w in canvas_frame.winfo_children():
            w.destroy()

    def report_products_sold():
        clear_canvas()
        conn = sqlite3_reports.connect(DB)
        df = pd.read_sql_query("""
SELECT p.name AS product, SUM(ii.quantity) AS qty_sold, SUM(ii.line_total) AS revenue
FROM invoice_items ii
JOIN products p ON p.id = ii.product_id
GROUP BY p.id
ORDER BY qty_sold DESC
""", conn)
        conn.close()
        if df.empty:
            tk.Label(canvas_frame, text="No sales data").pack()
            return
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(df['product'], df['qty_sold'])
        ax.set_title("Products sold (quantity)")
        ax.tick_params(axis='x', rotation=45)
        FigureCanvasTkAgg(fig, master=canvas_frame).get_tk_widget().pack(fill="both", expand=True)
        plt.close(fig)
        tv = ttk.Treeview(canvas_frame, columns=list(df.columns), show="headings")
        for c in df.columns:
            tv.heading(c, text=c)
            tv.column(c, width=130)
        for _, row in df.iterrows():
            tv.insert("", "end", values=list(row))
        tv.pack(fill="both", expand=True)

    def report_best_selling():
        clear_canvas()
        conn = sqlite3_reports.connect(DB)
        df = pd.read_sql_query("""
SELECT p.name AS product, SUM(ii.quantity) AS qty_sold
FROM invoice_items ii
JOIN products p ON p.id = ii.product_id
GROUP BY p.id
ORDER BY qty_sold DESC
LIMIT 10
""", conn)
        conn.close()
        if df.empty:
            tk.Label(canvas_frame, text="No sales data").pack()
            return
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(df['product'], df['qty_sold'])
        ax.set_title("Top 10 Best Selling")
        ax.tick_params(axis='x', rotation=45)
        FigureCanvasTkAgg(fig, master=canvas_frame).get_tk_widget().pack(fill="both", expand=True)
        plt.close(fig)
        tv = ttk.Treeview(canvas_frame, columns=list(df.columns), show="headings")
        for c in df.columns:
            tv.heading(c, text=c)
            tv.column(c, width=150)
        for _, row in df.iterrows():
            tv.insert("", "end", values=list(row))
        tv.pack(fill="both", expand=True)

    def report_top_invoices():
        clear_canvas()
        conn = sqlite3_reports.connect(DB)
        df = pd.read_sql_query("""
SELECT invoices.id AS invoice_id, partners.name as partner, invoices.total_amount
FROM invoices
JOIN partners ON partners.id = invoices.partner_id
ORDER BY invoices.total_amount DESC
LIMIT 15
""", conn)
        conn.close()
        if df.empty:
            tk.Label(canvas_frame, text="No invoice data").pack()
            return
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(df['invoice_id'].astype(str), df['total_amount'])
        ax.set_title("Top invoices by amount")
        ax.tick_params(axis='x', rotation=45)
        FigureCanvasTkAgg(fig, master=canvas_frame).get_tk_widget().pack(fill="both", expand=True)
        plt.close(fig)
        tv = ttk.Treeview(canvas_frame, columns=list(df.columns), show="headings")
        for c in df.columns:
            tv.heading(c, text=c)
            tv.column(c, width=150)
        for _, row in df.iterrows():
            tv.insert("", "end", values=list(row))
        tv.pack(fill="both", expand=True)

    ttk.Button(toolbar, text="Products sold summary", command=report_products_sold).pack(side="left", padx=6)
    ttk.Button(toolbar, text="Top 10 best-selling", command=report_best_selling).pack(side="left", padx=6)
    ttk.Button(toolbar, text="Top invoices", command=report_top_invoices).pack(side="left", padx=6)

APP_TITLE = "NovaInvoice"

def center_window(win, w=900, h=600):
    screen_w = win.winfo_screenwidth()
    screen_h = win.winfo_screenheight()
    x = (screen_w - w) // 2
    y = (screen_h - h) // 2
    win.geometry(f"{w}x{h}+{x}+{y}")

def open_partners_window(parent):
    win = tk.Toplevel(parent)
    win.title("Manage Partners — NovaInvoice")
    center_window(win, 900, 600)
    cols = ("id", "name", "tax_id", "email", "phone", "address")
    tree = ttk.Treeview(win, columns=cols, show="headings")
    for c in cols:
        tree.heading(c, text=c)
        tree.column(c, width=140)
    tree.pack(fill="both", expand=True, padx=10, pady=8)

    def refresh():
        tree.delete(*tree.get_children())
        for r in fetchall("SELECT id,name,tax_id,email,phone,address FROM partners"):
            tree.insert("", "end", values=r)

    form = ttk.Frame(win)
    form.pack(fill="x", padx=10, pady=6)
    labels = ["name", "tax_id", "email", "phone", "address"]
    entries = {}
    for i, lab in enumerate(labels):
        ttk.Label(form, text=lab.title() + ":").grid(row=i, column=0, sticky="e", padx=4, pady=3)
        e = ttk.Entry(form, width=60)
        e.grid(row=i, column=1, padx=6, pady=3)
        entries[lab] = e

    def add_partner():
        data = {k: entries[k].get().strip() for k in entries}
        err = validate_partner_row(data)
        if err:
            messagebox.showerror("❌ VALIDATION FAILED", 
                                "ALL FIELDS ARE REQUIRED!\n\n" + "\n".join(err))
            return
        try:
            execute("INSERT INTO partners (name,tax_id,email,phone,address) VALUES (?,?,?,?,?)",
                    (data["name"], data["tax_id"], data["email"], data["phone"], data["address"]))
            refresh()
            for e in entries.values():
                e.delete(0, 'end')
            messagebox.showinfo("✅ SUCCESS", "Partner added!")
        except Exception as e:
            messagebox.showerror("❌ DB ERROR", str(e))

    def edit_partner():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Selection Error", "Select a partner to edit")
            return
        vals = tree.item(sel[0])["values"]
        pid = vals[0]
        for i, k in enumerate(labels):
            entries[k].delete(0, 'end')
            entries[k].insert(0, vals[i + 1] or "")

        def save_update():
            data = {k: entries[k].get().strip() for k in entries}
            err = validate_partner_row(data)
            if err:
                messagebox.showerror("❌ VALIDATION FAILED", 
                                    "ALL FIELDS ARE REQUIRED!\n\n" + "\n".join(err))
                return
            try:
                execute("UPDATE partners SET name=?,tax_id=?,email=?,phone=?,address=? WHERE id=?",
                        (data["name"], data["tax_id"], data["email"], 
                         data["phone"], data["address"], pid))
                refresh()
                update_btn.destroy()
                add_btn.config(state="normal")
                messagebox.showinfo("✅ SUCCESS", "Partner updated!")
            except Exception as e:
                messagebox.showerror("❌ DB ERROR", str(e))

        add_btn.config(state="disabled")
        update_btn = ttk.Button(form, text="Save update", command=save_update)
        update_btn.grid(row=0, column=2, padx=8)

    def delete_partner():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Selection Error", "Select a partner")
            return
        pid = tree.item(sel[0])["values"][0]
        if messagebox.askyesno("Confirm Delete",
                              "Delete partner? Related invoices will be SET NULL or deleted depending on DB policy."):
            execute("DELETE FROM partners WHERE id=?", (pid,))
            refresh()

    def view_invoices_for_partner():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Selection Error", "Select a partner")
            return
        pid = tree.item(sel[0])["values"][0]
        win2 = tk.Toplevel(win)
        win2.title(f"Invoices for partner {pid}")
        cols2 = ("id", "invoice_date", "due_date", "status", "total")
        tv = ttk.Treeview(win2, columns=cols2, show="headings")
        for c in cols2:
            tv.heading(c, text=c)
        tv.pack(fill="both", expand=True, padx=8, pady=8)
        for row in fetchall(
                "SELECT id,invoice_date,due_date,status,total_amount FROM invoices WHERE partner_id=?", (pid,)):
            tv.insert("", "end", values=row)

    btn_frame = ttk.Frame(win)
    btn_frame.pack(fill="x", padx=10, pady=6)
    add_btn = ttk.Button(btn_frame, text="Add", command=add_partner)
    add_btn.pack(side="left", padx=4)
    ttk.Button(btn_frame, text="Edit", command=edit_partner).pack(side="left", padx=4)
    ttk.Button(btn_frame, text="Delete", command=delete_partner).pack(side="left", padx=4)
    ttk.Button(btn_frame, text="Export CSV", command=lambda: export_table_to_csv("partners")).pack(side="left", padx=4)
    ttk.Button(btn_frame, text="Import CSV", command=import_partners_csv).pack(side="left", padx=4)
    ttk.Button(btn_frame, text="View invoices", command=view_invoices_for_partner).pack(side="left", padx=8)
    ttk.Button(btn_frame, text="Refresh", command=refresh).pack(side="right", padx=4)
    refresh()

def open_products_window(parent):
    win = tk.Toplevel(parent)
    win.title("Manage Products — NovaInvoice")
    center_window(win, 1000, 620)
    cols = ("id", "sku", "name", "description", "price", "stock")
    tree = ttk.Treeview(win, columns=cols, show="headings")
    for c in cols:
        tree.heading(c, text=c)
        tree.column(c, width=140 if c != "description" else 240)
    tree.pack(fill="both", expand=True, padx=10, pady=8)

    def refresh():
        tree.delete(*tree.get_children())
        for r in fetchall("SELECT id,sku,name,description,price,stock FROM products"):
            tree.insert("", "end", values=r)

    form = ttk.Frame(win)
    form.pack(fill="x", padx=10, pady=6)
    labels = ["sku", "name", "description", "price", "stock"]
    entries = {}
    for i, k in enumerate(labels):
        ttk.Label(form, text=k.title() + ":").grid(row=i, column=0, sticky="e", padx=4, pady=3)
        e = ttk.Entry(form, width=60)
        e.grid(row=i, column=1, padx=6, pady=3)
        entries[k] = e

    def add_product():
        data = {k: entries[k].get().strip() for k in entries}
        err = validate_product_row(data)
        if err:
            messagebox.showerror("❌ VALIDATION FAILED", 
                                "ALL FIELDS ARE REQUIRED!\n\n" + "\n".join(err))
            return
        try:
            execute("INSERT INTO products (sku,name,description,price,stock) VALUES (?,?,?,?,?)",
                    (data["sku"], data["name"], data["description"],
                     float(data["price"]), int(data["stock"])))
            refresh()
            for e in entries.values():
                e.delete(0, 'end')
            messagebox.showinfo("✅ SUCCESS", "Product added!")
        except Exception as e:
            messagebox.showerror("❌ DB ERROR", str(e))

    def edit_product():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Selection Error", "Select a product to edit")
            return
        vals = tree.item(sel[0])["values"]
        pid = vals[0]
        for i, k in enumerate(labels):
            entries[k].delete(0, 'end')
            entries[k].insert(0, vals[i + 1] or "")

        def save_update():
            data = {k: entries[k].get().strip() for k in entries}
            err = validate_product_row(data)
            if err:
                messagebox.showerror("❌ VALIDATION FAILED", 
                                    "ALL FIELDS ARE REQUIRED!\n\n" + "\n".join(err))
                return
            try:
                execute("UPDATE products SET sku=?,name=?,description=?,price=?,stock=? WHERE id=?",
                        (data["sku"], data["name"], data["description"],
                         float(data["price"]), int(data["stock"]), pid))
                refresh()
                update_btn.destroy()
                add_btn.config(state="normal")
                messagebox.showinfo("✅ SUCCESS", "Product updated!")
            except Exception as e:
                messagebox.showerror("❌ DB ERROR", str(e))

        add_btn.config(state="disabled")
        update_btn = ttk.Button(form, text="Save update", command=save_update)
        update_btn.grid(row=0, column=2, padx=8)

    def delete_product():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Selection Error", "Select a product")
            return
        pid = tree.item(sel[0])["values"][0]
        if messagebox.askyesno("Confirm", "Delete product and related invoice_items?"):
            execute("DELETE FROM products WHERE id=?", (pid,))
            refresh()

    def view_stock_of_product():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Selection Error", "Select product")
            return
        pid = tree.item(sel[0])["values"][0]
        win2 = tk.Toplevel(win)
        win2.title(f"Invoices with product {pid}")
        tv = ttk.Treeview(win2, columns=("invoice_id", "quantity", "line_total"), show="headings")
        for h in ("invoice_id", "quantity", "line_total"):
            tv.heading(h, text=h)
        tv.pack(fill="both", expand=True, padx=6, pady=6)
        rows = fetchall("SELECT invoice_id,quantity,line_total FROM invoice_items WHERE product_id=?", (pid,))
        for r in rows:
            tv.insert("", "end", values=r)

    btn_frame = ttk.Frame(win)
    btn_frame.pack(fill="x", padx=10, pady=6)
    add_btn = ttk.Button(btn_frame, text="Add", command=add_product)
    add_btn.pack(side="left", padx=4)
    ttk.Button(btn_frame, text="Edit", command=edit_product).pack(side="left", padx=4)
    ttk.Button(btn_frame, text="Delete", command=delete_product).pack(side="left", padx=4)
    ttk.Button(btn_frame, text="Export CSV", command=lambda: export_table_to_csv("products")).pack(side="left", padx=4)
    ttk.Button(btn_frame, text="Import CSV", command=import_products_csv).pack(side="left", padx=4)
    ttk.Button(btn_frame, text="View Invoices with Product", command=view_stock_of_product).pack(side="left", padx=8)
    ttk.Button(btn_frame, text="Refresh", command=refresh).pack(side="right", padx=4)
    refresh()

def open_invoices_window(parent):
    win = tk.Toplevel(parent)
    win.title("Manage Invoices — NovaInvoice")
    center_window(win, 1100, 700)
    cols = ("id", "partner_id", "invoice_date", "due_date", "status", "total_amount")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=8)
    for c in cols:
        tree.heading(c, text=c)
        tree.column(c, width=120)
    tree.pack(fill="x", padx=10, pady=8)

    def refresh_invoices():
        tree.delete(*tree.get_children())
        for r in fetchall("SELECT id,partner_id,invoice_date,due_date,status,total_amount FROM invoices"):
            tree.insert("", "end", values=r)

    form = ttk.Frame(win)
    form.pack(fill="x", padx=10, pady=6)
    ttk.Label(form, text="Partner (id - name):").grid(row=0, column=0, sticky="e")
    partner_cb = ttk.Combobox(form, width=60)

    def load_partners():
        partner_cb['values'] = [f"{r[0]} - {r[1]}" for r in fetchall("SELECT id,name FROM partners")]
        if partner_cb.get() == "" and partner_cb['values']:
            partner_cb.set(partner_cb['values'][0])

    load_partners()
    partner_cb.grid(row=0, column=1, padx=6, pady=3)
    ttk.Label(form, text="Invoice Date (YYYY-MM-DD):").grid(row=1, column=0, sticky="e")
    date_e = ttk.Entry(form, width=30)
    date_e.grid(row=1, column=1, padx=6, pady=3)
    ttk.Label(form, text="Due Date (YYYY-MM-DD):").grid(row=2, column=0, sticky="e")
    due_e = ttk.Entry(form, width=30)
    due_e.grid(row=2, column=1, padx=6, pady=3)
    ttk.Label(form, text="Status:").grid(row=3, column=0, sticky="e")
    status_cb = ttk.Combobox(form, values=["Draft", "Sent", "Paid", "Cancelled"], width=20)
    status_cb.grid(row=3, column=1, padx=6, pady=3)

    def add_invoice():
        partner_val = partner_cb.get().strip()
        invoice_date = date_e.get().strip()
        due_date = due_e.get().strip()
        status_val = status_cb.get().strip()
        try:
            pid = int(partner_val.split(" - ")[0])
        except (ValueError, IndexError):
            messagebox.showerror("❌ INVALID PARTNER", "Please select a valid partner.")
            return

        data = {
            "partner_id": pid,
            "invoice_date": invoice_date,
            "due_date": due_date,
            "status": status_val
        }
        err = validate_invoice_row(data)
        if err:
            messagebox.showerror("❌ VALIDATION FAILED", 
                                "ALL FIELDS ARE REQUIRED!\n\n" + "\n".join(err))
            return
        try:
            execute("INSERT INTO invoices (partner_id,invoice_date,due_date,status,total_amount) VALUES (?,?,?,?,0)",
                    (pid, invoice_date, due_date if due_date else None, status_val))
            refresh_invoices()
            messagebox.showinfo("✅ SUCCESS", "Invoice created!")
        except Exception as e:
            messagebox.showerror("❌ DB ERROR", str(e))

    def show_items_for_invoice(inv_id):
        items_tv.delete(*items_tv.get_children())
        for r in fetchall(
                "SELECT id,invoice_id,product_id,quantity,unit_price,line_total FROM invoice_items WHERE invoice_id=?",
                (inv_id,)):
            items_tv.insert("", "end", values=r)

    def load_invoice_for_edit():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Selection Error", "Select invoice")
            return
        vals = tree.item(sel[0])["values"]
        inv_id = vals[0]
        partner_row = fetchone("SELECT id,name FROM partners WHERE id=?", (vals[1],))
        partner_cb.set(f"{partner_row[0]} - {partner_row[1]}")
        date_e.delete(0, 'end')
        date_e.insert(0, vals[2])
        due_e.delete(0, 'end')
        due_e.insert(0, vals[3] or "")
        status_cb.set(vals[4])
        show_items_for_invoice(inv_id)

    def update_invoice():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Selection Error", "Select invoice")
            return
        partner_val = partner_cb.get().strip()
        invoice_date = date_e.get().strip()
        due_date = due_e.get().strip()
        status_val = status_cb.get().strip()
        try:
            pid = int(partner_val.split(" - ")[0])
        except (ValueError, IndexError):
            messagebox.showerror("❌ INVALID PARTNER", "Please select a valid partner.")
            return

        data = {
            "partner_id": pid,
            "invoice_date": invoice_date,
            "due_date": due_date,
            "status": status_val
        }
        err = validate_invoice_row(data)
        if err:
            messagebox.showerror("❌ VALIDATION FAILED", 
                                "ALL FIELDS ARE REQUIRED!\n\n" + "\n".join(err))
            return
        inv_id = tree.item(sel[0])["values"][0]
        try:
            execute("UPDATE invoices SET partner_id=?,invoice_date=?,due_date=?,status=? WHERE id=?",
                    (pid, invoice_date, due_date if due_date else None, status_val, inv_id))
            refresh_invoices()
            messagebox.showinfo("✅ SUCCESS", "Invoice updated!")
        except Exception as e:
            messagebox.showerror("❌ DB ERROR", str(e))

    def delete_invoice():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Selection Error", "Select invoice")
            return
        inv_id = tree.item(sel[0])["values"][0]
        if messagebox.askyesno("Confirm", "Delete invoice and its items?"):
            execute("DELETE FROM invoices WHERE id=?", (inv_id,))
            refresh_invoices()
            items_tv.delete(*items_tv.get_children())

    items_frame = ttk.LabelFrame(win, text="Invoice Items")
    items_frame.pack(fill="both", expand=True, padx=10, pady=8)
    item_cols = ("id", "invoice_id", "product_id", "quantity", "unit_price", "line_total")
    items_tv = ttk.Treeview(items_frame, columns=item_cols, show="headings")
    for c in item_cols:
        items_tv.heading(c, text=c)
        items_tv.column(c, width=110)
    items_tv.pack(fill="both", expand=True, padx=6, pady=6)
    item_ctrl = ttk.Frame(win)
    item_ctrl.pack(fill="x", padx=10, pady=6)
    ttk.Label(item_ctrl, text="Product (id - name):").grid(row=0, column=0, sticky="e")
    product_cb = ttk.Combobox(item_ctrl, width=50)
    product_cb.grid(row=0, column=1, padx=6)

    def load_products():
        product_cb['values'] = [f"{r[0]} - {r[1]} (price:{r[2]})"
                               for r in fetchall("SELECT id,name,price FROM products")]

    load_products()
    ttk.Label(item_ctrl, text="Qty:").grid(row=0, column=2, sticky="e")
    qty_e = ttk.Entry(item_ctrl, width=8)
    qty_e.grid(row=0, column=3, padx=6)
    ttk.Label(item_ctrl, text="Unit price (optional):").grid(row=0, column=4, sticky="e")
    unit_e = ttk.Entry(item_ctrl, width=12)
    unit_e.grid(row=0, column=5, padx=6)

    def add_item_to_invoice():
        prod_val = product_cb.get().strip()
        qty_val = qty_e.get().strip()
        try:
            pid = int(prod_val.split(" - ")[0])
        except (ValueError, IndexError):
            messagebox.showerror("❌ INVALID PRODUCT", "Please select a valid product.")
            return
        try:
            qty = int(qty_val)
        except (ValueError, IndexError):
            messagebox.showerror("❌ INVALID QUANTITY", "Please enter a valid quantity.")
            return

        sel = tree.selection()
        if not sel:
            messagebox.showerror("❌ NO INVOICE", "Select an invoice first!")
            return
        inv_id = int(tree.item(sel[0])["values"][0])  # Extract invoice ID as integer

        data = {
            "invoice_id": inv_id,
            "product_id": pid,
            "quantity": qty
        }
        err = validate_invoice_item_row(data)
        if err:
            messagebox.showerror("❌ VALIDATION FAILED", 
                                "ALL REQUIRED FIELDS MUST BE FILLED!\n\n" + "\n".join(err))
            return

        unit = unit_e.get().strip()
        if not unit or not is_float(unit):
            pr = fetchone("SELECT price FROM products WHERE id=?", (pid,))
            if not pr:
                messagebox.showerror("❌ ERROR", "Product price missing")
                return
            unit = float(pr[0])
        else:
            unit = float(unit)
        line_total = qty * unit
        try:
            execute("INSERT INTO invoice_items (invoice_id,product_id,quantity,unit_price,line_total) VALUES (?,?,?,?,?)",
                    (inv_id, pid, qty, unit, line_total))
            tot = fetchone("SELECT SUM(line_total) FROM invoice_items WHERE invoice_id=?", (inv_id,))[0] or 0.0
            execute("UPDATE invoices SET total_amount=? WHERE id=?", (tot, inv_id))
            show_items_for_invoice(inv_id)
            refresh_invoices()
            product_cb.set("")
            qty_e.delete(0, 'end')
            unit_e.delete(0, 'end')
            messagebox.showinfo("✅ SUCCESS", "Item added!")
        except Exception as e:
            messagebox.showerror("❌ DB ERROR", str(e))


    def delete_item():
        sel = items_tv.selection()
        if not sel:
            messagebox.showwarning("Selection Error", "Select item")
            return
        item_id = items_tv.item(sel[0])["values"][0]
        inv_id = items_tv.item(sel[0])["values"][1]
        if messagebox.askyesno("Confirm", "Delete item?"):
            execute("DELETE FROM invoice_items WHERE id=?", (item_id,))
            tot = fetchone("SELECT SUM(line_total) FROM invoice_items WHERE invoice_id=?", (inv_id,))[0] or 0.0
            execute("UPDATE invoices SET total_amount=? WHERE id=?", (tot, inv_id))
            show_items_for_invoice(inv_id)
            refresh_invoices()

    ctrl = ttk.Frame(win)
    ctrl.pack(fill="x", padx=10, pady=6)
    ttk.Button(ctrl, text="New Invoice (clear fields)",
               command=lambda: [partner_cb.set(""), date_e.delete(0, 'end'),
                                due_e.delete(0, 'end'), status_cb.set("")]).grid(row=0, column=0, padx=6)
    ttk.Button(ctrl, text="Add Invoice", command=add_invoice).grid(row=0, column=1, padx=6)
    ttk.Button(ctrl, text="Load Selected", command=load_invoice_for_edit).grid(row=0, column=2, padx=6)
    ttk.Button(ctrl, text="Update Invoice", command=update_invoice).grid(row=0, column=3, padx=6)
    ttk.Button(ctrl, text="Delete Invoice", command=delete_invoice).grid(row=0, column=4, padx=6)
    ttk.Button(ctrl, text="Export Invoices CSV", command=lambda: export_table_to_csv("invoices")).grid(row=0, column=5,
                                                                                                     padx=6)
    ttk.Button(ctrl, text="Import Partners CSV",
               command=lambda: [import_partners_csv(), load_partners()]).grid(row=0, column=6, padx=6)

    item_btns = ttk.Frame(win)
    item_btns.pack(fill="x", padx=10, pady=6)
    ttk.Button(item_btns, text="Add Item", command=add_item_to_invoice).pack(side="left", padx=6)
    ttk.Button(item_btns, text="Delete Item", command=delete_item).pack(side="left", padx=6)
    ttk.Button(item_btns, text="Refresh partners/products",
               command=lambda: [load_partners(), load_products()]).pack(side="right", padx=6)
    refresh_invoices()

def open_main_menu():
    root = tk.Tk()
    root.title(APP_TITLE)
    center_window(root, 500, 420)
    root.configure(bg="#f3f7fb")
    title = ttk.Label(root, text="NovaInvoice — Invoicing Software", font=("Helvetica", 16, "bold"))
    title.pack(pady=24)
    ttk.Button(root, text="Manage Partners", width=28,
               command=lambda: open_partners_window(root)).pack(pady=6)
    ttk.Button(root, text="Manage Products", width=28,
               command=lambda: open_products_window(root)).pack(pady=6)
    ttk.Button(root, text="Manage Invoices", width=28,
               command=lambda: open_invoices_window(root)).pack(pady=6)
    ttk.Button(root, text="Reports", width=28,
               command=lambda: open_reports_window(root)).pack(pady=6)
    ttk.Button(root, text="Exit", width=28, command=root.destroy).pack(pady=8)
    root.mainloop()

def run():
    init_db()
    open_main_menu()

if __name__ == "__main__":
    run()
