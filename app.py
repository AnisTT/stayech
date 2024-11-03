import json
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime
from collections import defaultdict
from assistant import Assistant  # Import the Assistant class
from dotenv import load_dotenv
import google.generativeai as genai
import pyodbc as odbc
print(odbc.drivers())
import os

load_dotenv()

# Configure the Gemini API
server = "stayech.database.windows.net"
DATABASE = "tracker"
# connction_string = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER='+server+';DATABASE='+DATABASE+';UID='+username+';PWD='+ password
username = os.environ["username"]
password = os.environ["password"]
conn = odbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER='+server+';DATABASE='+DATABASE+';UID='+username+';PWD='+ password)
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-1.5-flash")

app = Flask(__name__)
app.secret_key = 'your_secret_key'
Assistant = Assistant()

def init_db():
    c = conn.cursor()
    # Existing users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    # Existing transactions table for expenses
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            payment_method TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
   
    # New income table
    c.execute('''
        CREATE TABLE IF NOT EXISTS incomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()


@app.route('/')
def index():
    if 'username' in session:
        user_id = session['user_id']
        username = session['username']
        
        # Fetch transactions (expenses) from the database
        
        c = conn.cursor()
        c.execute("SELECT * FROM transactions WHERE user_id = ?", (user_id,))
        transactions = c.fetchall()
        c.execute("SELECT * FROM incomes WHERE user_id = ?", (user_id,))
        incomes = c.fetchall()
        user_data = get_user_data(user_id)
        # Compute total expenses and breakdowns
        total_expenses = sum(transaction[2] for transaction in transactions)
        total_upi = sum(transaction[2] for transaction in transactions if transaction[6] == 'UPI')
        total_cash = sum(transaction[2] for transaction in transactions if transaction[6] == 'Cash')

        # Fetch income from the database
        c.execute("SELECT * FROM income WHERE user_id = ?", (user_id,))
        income_records = c.fetchall()
        total_income = sum(income[2] for income in incomes)
        if user_data["transactions"] or user_data["income"]:
            # Get recommendations from the assistant
            recommendations = Assistant.get_recommendations(user_data)
        else:
            recommendations = {"message": "No data available for recommendations."}
        conn.close()

        return render_template('index.html', username=username, total_expenses=total_expenses, total_income=total_income,
                               total_upi=total_upi, total_cash=total_cash, recommendations=recommendations)
    return redirect(url_for('login'))
def get_user_data(user_id):
    
    c = conn.cursor()
    
    # Fetch transactions
    c.execute("SELECT date,  amount FROM transactions WHERE user_id = ?", (user_id,))
    transactions = [{'date': row[0],  'amount': row[1]} for row in c.fetchall()]
    
    # Fetch incomes
    c.execute("SELECT date, amount FROM incomes WHERE user_id = ?", (user_id,))
    incomes = [{'date': row[0],  'amount': row[1]} for row in c.fetchall()]
    
    conn.close()
    
    return {
        'transactions': transactions,
        'income': incomes
    }
def send_message(message, history):
    user_data = get_user_data(session['user_id'])
    user_data_str = json.dumps(user_data)
    mess = (
        "my name is " + session['username'] + ", I am a student"
        "your name is stayech, you are a student, you are 20 years"
        "you help us to manage our finance, you are a good person"
                "now, you know my incomes and expenses, please provide tailored finaincial conversation "
                "if you already got the data please don't send the same message"
                "Don't answer anything isn't financial or related"
                "Here’s the user data: " + user_data_str  # Include user data in the message
            )
    history.append({"role":"user", "parts":mess})
    chat = model.start_chat(history = history)
    response = chat.send_message(message)
    history.append({"role":"model", "parts":response.text})
    return response.text, history



@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message')
    history = request.json.get('history')
    response, history = send_message(user_message, history)
    return jsonify({'message': response, "history":history})
@app.route('/chatbot')
def chatbot():
    return render_template('chat.html')




@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        c = conn.cursor()
        c.execute("SELECT id, username FROM users WHERE username = ? AND password = ?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password. Please try again.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        existing_user = c.fetchone()
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'error')
        else:
            c.execute("INSERT INTO users (username, email, phone, password) VALUES (?, ?, ?, ?)",
                      (username, email, phone, password))
            conn.commit()
            conn.close()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/transactions')
def transactions():
    if 'username' in session:
        user_id = session['user_id']
        username = session['username']
        
        c = conn.cursor()
        c.execute("SELECT * FROM transactions WHERE user_id = ?", (user_id,))
        transactions = c.fetchall()
        conn.close()

        return render_template('transaction.html', transactions=transactions, username=username)
    else:
        return redirect(url_for('login'))

@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    if 'username' in session:
        user_id = session['user_id']
        date = request.form['date']
        category = request.form['category']
        amount = request.form['amount']
        payment_method = request.form['payment_method']
        description = request.form['notes']

        
        c = conn.cursor()
        c.execute("INSERT INTO transactions (user_id, date, category, amount, payment_method, description) VALUES (?, ?, ?, ?, ?, ?)",
                  (user_id, date, category, amount, payment_method, description))
        conn.commit()
        conn.close()

        return redirect(url_for('transactions'))
    else:
        return redirect(url_for('login'))

@app.route('/delete_transaction/<int:transaction_id>', methods=['POST'])
def delete_transaction(transaction_id):
    if 'username' in session:
        
        c = conn.cursor()
        c.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
        conn.commit()
        conn.close()
        flash('Transaction deleted successfully.', 'success')
    else:
        flash('You must be logged in to delete a transaction.', 'error')
    return redirect(url_for('transactions'))

@app.route('/add_income', methods=['GET', 'POST'])
def add_income():
    if 'username' in session:
        if request.method == 'POST':
            user_id = session['user_id']
            date = request.form['date']
            amount = request.form['amount']
            description = request.form['notes']

            
            c = conn.cursor()
            c.execute("INSERT INTO incomes (user_id, date,  amount,  description) VALUES (?, ?, ?, ?)",
                      (user_id, date,  amount,  description))
            conn.commit()
            conn.close()

            flash('Income added successfully!', 'success')
            return redirect(url_for('income'))

        return render_template('add_income.html')
    else:
        return redirect(url_for('login'))

@app.route('/income')
def income():
    if 'username' in session:
        user_id = session['user_id']
        
        c = conn.cursor()
        c.execute("SELECT * FROM incomes WHERE user_id = ?", (user_id,))
        income_records = c.fetchall()
        conn.close()

        return render_template('income.html', income_records=income_records)
    else:
        return redirect(url_for('login'))
@app.route('/delete_income/<int:income_id>', methods=['POST'])
def delete_income(income_id):
    if 'username' in session:
        
        c = conn.cursor()
        c.execute("DELETE FROM incomes WHERE id = ?", (income_id,))
        conn.commit()
        conn.close()
        flash('Income record deleted successfully.', 'success')
    else:
        flash('You must be logged in to delete an income record.', 'error')
    return redirect(url_for('income'))
@app.route('/monthly_income_data')
def monthly_income_data():
    if 'username' in session:
        
        c = conn.cursor()
        c.execute('''
            SELECT strftime('%Y-%m', date) as month, SUM(amount) as total_income
            FROM incomes
            GROUP BY month
            ORDER BY month DESC
        ''')
        monthly_income = c.fetchall()
        conn.close()
        return jsonify(monthly_income)
    else:
        flash('You must be logged in to view monthly income data.', 'error')
        return redirect(url_for('login'))

@app.route('/daily_spending_data')
def daily_spending_data():
    if 'username' in session:
        user_id = session['user_id']
        
        
        c = conn.cursor()
        c.execute("SELECT date, SUM(amount) FROM transactions WHERE user_id = ? GROUP BY date", (user_id,))
        data = c.fetchall()
        conn.close()

        labels = [row[0] for row in data]
        amounts = [row[1] for row in data]

        return jsonify({'labels': labels, 'amounts': amounts})
    else:
        return redirect(url_for('login'))

@app.route('/monthly_spending_data')
def monthly_spending_data():
    if 'username' in session:
        user_id = session['user_id']
        
        
        c = conn.cursor()
        c.execute("SELECT strftime('%Y-%m', date) AS month, SUM(amount) FROM transactions WHERE user_id = ? GROUP BY month", (user_id,))
        data = c.fetchall()
        conn.close()

        labels = [datetime.strptime(row[0], '%Y-%m').strftime('%b %Y') for row in data]
        amounts = [row[1] for row in data]

        return jsonify({'labels': labels, 'amounts': amounts})
    else:
        return redirect(url_for('login'))
@app.route('/daily_income_data')
def daily_income_data():
    if 'username' in session:
        user_id = session['user_id']
        
        
        c = conn.cursor()
        c.execute("SELECT date, SUM(amount) FROM incomes WHERE user_id = ? GROUP BY date", (user_id,))
        data = c.fetchall()
        conn.close()

        labels = [row[0] for row in data]
        amounts = [row[1] for row in data]

        return jsonify({'labels': labels, 'amounts': amounts})
    else:
        flash('You must be logged in to view daily income data.', 'error')
        return redirect(url_for('login'))
@app.route('/balance')
def balance():
    if 'username' in session:
        user_id = session['user_id']
        
        
        c = conn.cursor()
        
        # Fetch total income
        c.execute("SELECT SUM(amount) FROM incomes WHERE user_id = ?", (user_id,))
        total_income = c.fetchone()[0] or 0.0
        
        # Fetch total expenses
        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ?", (user_id,))
        total_expenses = c.fetchone()[0] or 0.0
        conn.close()
        
        # Calculate balance
        balance = total_income - total_expenses
        
        return jsonify({'total_income': total_income, 'total_expenses': total_expenses, 'balance': balance})
    else:
        flash('You must be logged in to view the balance.', 'error')
        return redirect(url_for('login'))

@app.route('/statistics')
def statistics():
    user_id = session.get('user_id')
    
    if user_id:
        
        c = conn.cursor()

        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ?", (user_id,))
        total_expenses_result = c.fetchone()
        total_expenses = total_expenses_result[0] if total_expenses_result else 0

        c.execute("SELECT SUM(amount) FROM incomes WHERE user_id = ?", (user_id,))
        total_income_result = c.fetchone()
        total_income = total_income_result[0] if total_income_result else 0

        c.execute("SELECT category, SUM(amount) FROM transactions WHERE user_id = ? GROUP BY category", (user_id,))
        expense_by_category_result = c.fetchall()
        expense_by_category = dict(expense_by_category_result) if expense_by_category_result else {}

        c.execute("SELECT category, SUM(amount) FROM income WHERE user_id = ? GROUP BY category", (user_id,))
        income_by_category_result = c.fetchall()
        income_by_category = dict(income_by_category_result) if income_by_category_result else {}

        c.execute("SELECT category, SUM(amount) FROM transactions WHERE user_id = ? GROUP BY category ORDER BY SUM(amount) DESC LIMIT 5", (user_id,))
        top_spending_categories_result = c.fetchall()
        top_spending_categories = dict(top_spending_categories_result) if top_spending_categories_result else {}

        conn.close()

        return render_template('statistics.html', total_expenses=total_expenses, total_income=total_income,
                               expense_by_category=expense_by_category, income_by_category=income_by_category, top_spending_categories=top_spending_categories)
    else:
        return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
