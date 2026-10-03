import sqlite3
from flask import Flask, render_template, request, redirect, session

app = Flask(__name__)
app.secret_key = 'fertilizer123'

def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE, password TEXT, role TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, type TEXT, company TEXT, bag_size TEXT,
        batch_no TEXT, expiry TEXT,
        purchase_price REAL, sale_price REAL, quantity INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER, action TEXT, qty INTEGER, date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER, qty INTEGER, total REAL, date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, phone TEXT, address TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pw = request.form['password']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (user, pw))
        data = c.fetchone()
        conn.close()
        if data:
            session['user'] = user
            session['role'] = data[3]
            return redirect('/dashboard')
        return "Wrong username or password"
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM products")
    total_products = c.fetchone()[0]
    c.execute("SELECT SUM(quantity) FROM products")
    total_stock = c.fetchone()[0] or 0
    c.execute("SELECT SUM(total) FROM sales")
    total_sales = c.fetchone()[0] or 0
    c.execute("SELECT name, quantity FROM products WHERE quantity < 10")
    low_stock = c.fetchall()
    conn.close()
    return render_template('dashboard.html', user=session['user'],
        total_products=total_products, total_stock=total_stock,
        total_sales=total_sales, low_stock=low_stock)
@app.route('/products')
def products():
    if 'user' not in session:
        return redirect('/')
    q = request.args.get('q', '')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if q:
        c.execute("SELECT * FROM products WHERE name LIKE ? OR type LIKE ? OR company LIKE ?",
                  ('%'+q+'%', '%'+q+'%', '%'+q+'%'))
    else:
        c.execute("SELECT * FROM products")
    data = c.fetchall()
    conn.close()
    return render_template('products.html', products=data, q=q)

@app.route('/add_product', methods=['POST'])
def add_product():
    if 'user' not in session:
        return redirect('/')
    name = request.form['name']
    type_ = request.form['type']
    company = request.form['company']
    bag_size = request.form['bag_size']
    batch_no = request.form['batch_no']
    expiry = request.form['expiry']
    purchase_price = request.form['purchase_price']
    sale_price = request.form['sale_price']
    quantity = request.form['quantity']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("""INSERT INTO products
        (name,type,company,bag_size,batch_no,expiry,purchase_price,sale_price,quantity)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (name,type_,company,bag_size,batch_no,expiry,purchase_price,sale_price,quantity))
    conn.commit()
    conn.close()
    return redirect('/products')

@app.route('/delete_product/<int:id>')
def delete_product(id):
    if 'user' not in session:
        return redirect('/')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect('/products')
@app.route('/sales')
def sales():
    if 'user' not in session:
        return redirect('/')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id, name, sale_price, quantity FROM products")
    prods = c.fetchall()
    c.execute("""SELECT sales.id, products.name, sales.qty, sales.total, sales.date
                 FROM sales JOIN products ON sales.product_id = products.id
                 ORDER BY sales.id DESC""")
    data = c.fetchall()
    conn.close()
    return render_template('sales.html', products=prods, sales=data)

@app.route('/add_sale', methods=['POST'])
def add_sale():
    if 'user' not in session:
        return redirect('/')
    pid = request.form['product_id']
    qty = int(request.form['qty'])
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT sale_price, quantity FROM products WHERE id=?", (pid,))
    row = c.fetchone()
    if not row or row[1] < qty:
        conn.close()
        return "Not enough stock"
    price = row[0]
    total = price * qty
    from datetime import datetime
    date = datetime.now().strftime("%Y-%m-%d %H:%M")
    c.execute("INSERT INTO sales (product_id, qty, total, date) VALUES (?,?,?,?)",
              (pid, qty, total, date))
    c.execute("UPDATE products SET quantity = quantity - ? WHERE id=?", (qty, pid))
    c.execute("INSERT INTO stock (product_id, action, qty, date) VALUES (?,?,?,?)",
              (pid, 'OUT', qty, date))
    conn.commit()
    conn.close()
    return redirect('/sales')

@app.route('/reports')
def reports():
    if 'user' not in session:
        return redirect('/')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("SELECT COUNT(*), SUM(total) FROM sales")
    total_sales_count, total_sales_amount = c.fetchone()
    total_sales_amount = total_sales_amount or 0

    c.execute("SELECT SUM(quantity) FROM products")
    total_stock = c.fetchone()[0] or 0

    c.execute("""SELECT products.name, SUM(sales.qty), SUM(sales.total)
                 FROM sales JOIN products ON sales.product_id = products.id
                 GROUP BY products.name""")
    by_product = c.fetchall()

    c.execute("""SELECT date(sales.date) as d, SUM(sales.total)
                 FROM sales GROUP BY d ORDER BY d DESC LIMIT 30""")
    by_day = c.fetchall()

    conn.close()
    return render_template('reports.html',
        total_sales_count=total_sales_count,
        total_sales_amount=total_sales_amount,
        total_stock=total_stock,
        by_product=by_product,
        by_day=by_day)

@app.route('/suppliers')
def suppliers():
    if 'user' not in session:
        return redirect('/')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM suppliers")
    data = c.fetchall()
    conn.close()
    return render_template('suppliers.html', suppliers=data)

@app.route('/add_supplier', methods=['POST'])
def add_supplier():
    if 'user' not in session:
        return redirect('/')
    name = request.form['name']
    phone = request.form['phone']
    address = request.form['address']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT INTO suppliers (name, phone, address) VALUES (?,?,?)",
              (name, phone, address))
    conn.commit()
    conn.close()
    return redirect('/suppliers')

@app.route('/delete_supplier/<int:id>')
def delete_supplier(id):
    if 'user' not in session:
        return redirect('/')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM suppliers WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect('/suppliers')
@app.route('/stock_in')
def stock_in():
    if 'user' not in session:
        return redirect('/')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id, name, quantity FROM products")
    prods = c.fetchall()
    c.execute("""SELECT stock.id, products.name, stock.qty, stock.date
                 FROM stock JOIN products ON stock.product_id = products.id
                 WHERE stock.action='IN' ORDER BY stock.id DESC""")
    data = c.fetchall()
    conn.close()
    return render_template('stock_in.html', products=prods, stock=data)
@app.route('/add_stock_in', methods=['POST'])
def add_stock_in():
    if 'user' not in session:
        return redirect('/')
    pid = request.form['product_id']
    qty = int(request.form['qty'])
    from datetime import datetime
    date = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE products SET quantity = quantity + ? WHERE id=?", (qty, pid))
    c.execute("INSERT INTO stock (product_id, action, qty, date) VALUES (?,?,?,?)",
              (pid, 'IN', qty, date))
    conn.commit()
    conn.close()
    return redirect('/stock_in')
@app.route('/edit_product/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    if 'user' not in session:
        return redirect('/')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if request.method == 'POST':
        name = request.form['name']
        type_ = request.form['type']
        company = request.form['company']
        bag_size = request.form['bag_size']
        batch_no = request.form['batch_no']
        expiry = request.form['expiry']
        purchase_price = request.form['purchase_price']
        sale_price = request.form['sale_price']
        quantity = request.form['quantity']
        c.execute("""UPDATE products SET name=?, type=?, company=?, bag_size=?,
                     batch_no=?, expiry=?, purchase_price=?, sale_price=?, quantity=?
                     WHERE id=?""",
                  (name, type_, company, bag_size, batch_no, expiry,
                   purchase_price, sale_price, quantity, id))
        conn.commit()
        conn.close()
        return redirect('/products')
    c.execute("SELECT * FROM products WHERE id=?", (id,))
    p = c.fetchone()
    conn.close()
    return render_template('edit_product.html', p=p)

@app.route('/backup')
def backup():
    if 'user' not in session:
        return redirect('/')
    from shutil import copyfile
    from datetime import datetime
    filename = "backup_" + datetime.now().strftime("%Y%m%d_%H%M") + ".db"
    copyfile('database.db', filename)
    return "Backup saved as " + filename
@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'user' not in session:
        return redirect('/')
    if request.method == 'POST':
        old = request.form['old']
        new = request.form['new']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?",
                  (session['user'], old))
        if c.fetchone():
            c.execute("UPDATE users SET password=? WHERE username=?",
                      (new, session['user']))
            conn.commit()
            conn.close()
            return "Password changed. <a href='/dashboard'>Go back</a>"
        conn.close()
        return "Old password wrong"
    return render_template('change_password.html')
@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        code = request.form['code']
        new = request.form['new']
        if code == 'SHOP123':
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("UPDATE users SET password=? WHERE username='admin'", (new,))
            conn.commit()
            conn.close()
            return "Password reset. <a href='/'>Login</a>"
        return "Wrong master code"
    return render_template('forgot.html')
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)