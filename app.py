import os
from flask import Flask, render_template, g, redirect, url_for, request, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for flashing messages

# Database setup
# Path relative to the script location, no matter where the script is run from
DATABASE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'database.db')
db = sqlite3.connect(DATABASE)




def get_db():
    """Connect to SQLite database."""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    """Create the database and tables if they don't exist."""
    with app.app_context():
        db = get_db()
        db.execute('''CREATE TABLE IF NOT EXISTS articles
                       (id INTEGER PRIMARY KEY,
                        title TEXT NOT NULL,
                        source TEXT NOT NULL,
                        summary TEXT NOT NULL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS users
                       (id INTEGER PRIMARY KEY,
                        username TEXT NOT NULL UNIQUE,
                        email TEXT NOT NULL UNIQUE,
                        password TEXT NOT NULL)''')
        db.commit()

@app.route('/')
def index():
    """Render the login page."""
    return redirect(url_for('login'))

@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
    """Handle account creation."""
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('create_account'))

        db = get_db()
        try:
            db.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                       (username, email, password))
            db.commit()
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists!', 'error')
            return redirect(url_for('create_account'))

    return render_template('create_account.html')

# Route for the About page
@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/browse')
def browse():
    """Display article headlines."""
    db = get_db()
    articles = db.execute('SELECT * FROM articles').fetchall()
    return render_template('browse.html', articles=articles)

@app.route('/article/<int:article_id>')
def article(article_id):
    """View a single article."""
    db = get_db()
    article = db.execute('SELECT * FROM articles WHERE id = ?', (article_id,)).fetchone()
    return render_template('article.html', article=article)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    error = None  # Initialize error variable
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()

        if user:
            flash('Login successful!', 'success')
            return redirect(url_for('browse'))  # Redirect to browse after successful login
        else:
            error = True  # Set error to True if login fails

    return render_template('login.html', error=error)  # Pass error to the template

if __name__ == '__main__':
    init_db()  # Initialize DB
    app.run(debug=True)
