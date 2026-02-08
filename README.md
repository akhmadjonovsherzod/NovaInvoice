# NovaInvoice – Python Invoicing System

**NovaInvoice** is a desktop invoicing application developed in **Python** to help small businesses manage partners, products, and invoices in one place.  
It supports data management, reporting, and visualization, providing both operational functionality and essential business insights.

---

## 🧩 Features

### Partner Management
- Add, edit, delete, and view business partners  
- Store contact details (email, phone, address, tax ID)  
- View invoices associated with each partner  

### Product Management
- Manage product catalog with SKU, price, and stock  
- Track inventory levels  
- View invoices containing specific products  

### Invoice Management
- Create and update invoices  
- Add multiple items per invoice  
- Automatic calculation of line totals and invoice totals  
- Track invoice statuses: **Draft**, **Sent**, **Paid**, **Cancelled**  

### Data Import & Export
- Import partners and products from CSV files  
- Export database tables to CSV for external analysis  

### Reporting & Analytics
- Product sales summary  
- Top 10 best-selling products  
- Top invoices by total amount  
- Interactive charts built with **Matplotlib**  

### Data Validation
- Email format validation  
- Numeric and date validation  
- Input checks to ensure data accuracy and consistency  

---

## ⚙️ Technologies Used
- **Python**  
- **SQLite** (Relational Database)  
- **Tkinter** (GUI)  
- **Pandas** (Data handling)  
- **Matplotlib** (Data visualization)  
- **SQL**

---

## 🗂️ Database Structure

The application uses a relational **SQLite** database with the following tables:

| Table Name      | Description                          |
|-----------------|--------------------------------------|
| `partners`      | Customer information                 |
| `products`      | Product catalog and stock management  |
| `invoices`      | Invoice header data                   |
| `invoice_items` | Individual invoice line items         |

Foreign key relationships maintain data integrity across the database.

---

## 🚀 How to Run

Clone the repository:
```bash
git clone https://github.com/your-username/NovaInvoice.git
cd NovaInvoice
```

Install the required libraries:
```bash
pip install pandas matplotlib
```

Run the application:
```bash
python main.py
```

> The database file (`invoicing.db`) will be automatically created on first launch.

---

## 🎯 Project Purpose

Developed as part of the **Developing Data Handling Programs** coursework in the **BSc Business Informatics** program at the **University of Debrecen**.  

**Goals:**
- Design a relational database  
- Build a functional business application  
- Implement data validation and file handling  
- Create analytical reports and basic data visualizations  

---

## 🔮 Future Improvements
- User authentication system  
- PDF invoice generation  
- Dashboard with advanced analytics  
- Web version using **Streamlit** or **Flask**  
- Cloud database integration  

---

## 👥 Authors
- **Sherzodbek Akhmadjonov**  
- **Mokhichekhra [Last Name]**  
**BSc Business Informatics**  
University of Debrecen
```
