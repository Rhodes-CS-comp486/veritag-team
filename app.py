import os
import random
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, session
import sqlite3
import json

app = Flask(__name__)
app.secret_key = '12345'  # Replace with a secure key for production
DATABASE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'database.db')

app.config['SESSION_PERMANENT'] = True
app.config['SESSION_TYPE'] = 'filesystem'

def get_db():
    conn = sqlite3.connect(DATABASE)  # Fixed to use DATABASE variable
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create the database and tables if they don't exist."""
    with app.app_context():
        db = get_db()
        db.execute('''CREATE TABLE IF NOT EXISTS articles
                       (id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        source TEXT NOT NULL,
                        author TEXT NOT NULL,
                        length INTEGER NOT NULL,
                        category TEXT NOT NULL,
                        rating INTEGER NOT NULL,
                        summary TEXT NOT NULL,
                        publication_date TEXT NOT NULL,
                        body TEXT)''')
        db.execute('''CREATE TABLE IF NOT EXISTS users
                       (id INTEGER PRIMARY KEY,
                        username TEXT NOT NULL UNIQUE,
                        email TEXT NOT NULL UNIQUE,
                        password TEXT NOT NULL,
                        verified_code TEXT NOT NULL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS comments
                       (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        article_id TEXT NOT NULL,
                        user_id INTEGER,
                        username TEXT NOT NULL,
                        text TEXT NOT NULL,
                        votes INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (article_id) REFERENCES articles(id),
                        FOREIGN KEY (user_id) REFERENCES users(id))''')
        db.commit()
        load_articles_from_json()

def load_articles_from_json():
    """Load articles from dev-articles.json into the database."""
    json_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'dev-articles.json')
    with open(json_file, 'r', encoding='utf-8') as file:
        articles = json.load(file)

    db = get_db()
    cursor = db.cursor()
    for article in articles:
        cursor.execute(
            '''INSERT OR IGNORE INTO articles (id, title, author, category, length, summary, rating, source, publication_date, body) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (article["id"], article["title"], article["author"], article["category"], article["length"],
             article["summary"], article["rating"], article["source"], article["publication_date"], article["body"])
        )
    db.commit()
    db.close()

def seed_articles():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM articles")
    count = cursor.fetchone()[0]
    if count == 0:
        cursor.execute("INSERT INTO articles (id, title, source, author, length, category, summary, rating, publication_date, body) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       ("1", "The Future of AI", "Tech Daily", "Dr. John Smith", 12, "Tech", "AI is transforming the world.", 4, "2023-01-01", "Full article body here..."))
        cursor.execute("INSERT INTO articles (id, title, source, author, length, category, summary, rating, publication_date, body) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       ("2", "Health Tips 2025", "Wellness Weekly", "Dr. Alice Johnson", 10, "Health", "New health research.", 5, "2023-02-01", "Full article body here..."))
        db.commit()
    db.close()
@app.route('/')
def index():
    return redirect(url_for('browse'))

@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
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
            db.execute('INSERT INTO users (username, email, password, verified_code) VALUES (?, ?, ?, ?)',
                       (username, email, password, ''))
            db.commit()
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists!', 'error')
            return redirect(url_for('create_account'))
    return render_template('create_account.html')

VALID_VERIFICATION_CODES = ['12345']

@app.route('/create_verified_account', methods=['GET', 'POST'])
def create_verified_account():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        verified_code = request.form['verification_code']
        if verified_code not in VALID_VERIFICATION_CODES:  # Checks against ['12345']
            flash('Invalid verification code!', 'error')
            return redirect(url_for('create_verified_account'))
        db = get_db()
        try:
            db.execute('INSERT INTO users (username, email, password, verified_code) VALUES (?, ?, ?, ?)',
                       (username, email, password, verified_code))  # Stores '12345'
            db.commit()
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('verified_login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists!', 'error')
            return redirect(url_for('create_verified_account'))
    return render_template('create_verified_account.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/api/user')
def get_user():
    if 'user_id' in session:
        return jsonify({"username": session['username']})
    return jsonify({}), 401

@app.route('/api/articles')
def get_articles():
    db = get_db()
    articles = db.execute('SELECT id, title, source, author, length, category, rating, body, summary FROM articles').fetchall()
    articles_list = [dict(article) for article in articles]
    return jsonify({"articles": articles_list})

@app.route('/api/article/<int:article_id>', endpoint='article')
def get_article(article_id):
    db = get_db()
    article = db.execute('SELECT * FROM articles WHERE id = ?', (article_id,)).fetchone()
    if article is None:
        return jsonify({"error": "Article not found"}), 404
    return jsonify(dict(article))

@app.route('/api/article/<article_id>/comments', methods=['GET'])
def get_comments(article_id):
    db = get_db()
    comments = db.execute(
        'SELECT id, username, text, votes, created_at FROM comments WHERE article_id = ? ORDER BY created_at DESC',
        (article_id,)
    ).fetchall()
    comments_list = [dict(comment) for comment in comments]
    return jsonify({"comments": comments_list})

@app.route('/api/article/<article_id>/comments', methods=['POST'])
def post_comment(article_id):
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({"error": "Comment text is required"}), 400

    comment_text = data['text']
    db = get_db()
    article = db.execute('SELECT id FROM articles WHERE id = ?', (article_id,)).fetchone()
    if not article:
        return jsonify({"error": "Article not found"}), 404

    user_id = session.get('user_id')  # Get user ID from session
    username = session.get('username')  # Get username from session

    if user_id and username:  # If user is logged in
        # Check if the user is verified by looking at verified_code
        user = db.execute('SELECT verified_code FROM users WHERE id = ?', (user_id,)).fetchone()
        if user and user['verified_code'] != '':  # Verified user
            username = session['username']  # Use their actual username
        else:
            username = f"Anonymous{random.randint(1, 1000)}"  # Non-verified logged-in user gets anonymous
    else:
        username = f"Anonymous{random.randint(1, 1000)}"  # Not logged in, always anonymous

    try:
        cursor = db.execute(
            'INSERT INTO comments (article_id, user_id, username, text) VALUES (?, ?, ?, ?)',
            (article_id, user_id, username, comment_text)
        )
        db.commit()
        new_comment = db.execute(
            'SELECT id, username, text, votes, created_at FROM comments WHERE id = ?',
            (cursor.lastrowid,)
        ).fetchone()
        return jsonify(dict(new_comment)), 201
    except sqlite3.Error as e:
        return jsonify({"error": "Failed to post comment: " + str(e)}), 500

@app.route('/article/<article_id>')
def article_page(article_id):
    db = get_db()
    is_verified = False
    if 'user_id' in session:
        user = db.execute('SELECT verified_code FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if user and user['verified_code'] != '':
            is_verified = True
    return render_template('article.html', is_verified=is_verified)
@app.route('/browse')
def browse():
    db = get_db()  # Initialize db connection here
    user_info = None
    if 'user_id' in session:
        user = db.execute('SELECT username, email FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if user:
            user_info = dict(user)
    articles = db.execute('SELECT id, title, source, author, length, category, summary, body, publication_date, rating FROM articles').fetchall()
    return render_template('browse.html', articles=articles, user_info=user_info)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['verified_code'] = user['verified_code']  # Add verified_code to session
            flash('Login successful!', 'success')
            print(f"Debug: User logged in - session={session}")
            return redirect(url_for('browse'))
        else:
            error = True  # Set error to True if login fails

    return render_template('login.html', error=error)  # Pass error to the template

@app.route('/verified_login', methods=['GET', 'POST'])
def verified_login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ? AND password = ? AND verified_code != ""', (username, password)).fetchone()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['verified_code'] = user['verified_code']  # Add verified_code to session
            flash('Verified login successful!', 'success')
            print(f"Debug: Verified user logged in - session={session}")
            return redirect(url_for('browse_verified'))  # Redirect instead of rendering directly
        else:
            error = True
            flash('Invalid username, password, or not a verified account.', 'error')

    print(f"Debug: Verified login error - error={error}, session={session}")
    return render_template('verified_login.html', error=error)

@app.route('/browse_verified', methods=['POST', 'GET'])
def browse_verified():
    user_info = None
    if 'user_id' in session:
        db = get_db()
        user = db.execute('SELECT username, email FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if user:
            user_info = dict(user)
    print(f"Debug: browse_verified - user_info={user_info}, session={session}")
    return render_template('browse_verified.html', user_info=user_info)

@app.route('/community')
def community():
    return render_template('community.html')

@app.route('/categories')
def categories():
    response = get_articles()
    articles = json.loads(response.get_data(as_text=True))["articles"]
    categories = {}
    for article in articles:
        category = article["category"]
        if category not in categories:
            categories[category] = []
        categories[category].append(article)
    return render_template('categories.html', categories=categories)

@app.route('/article/<int:article_id>', endpoint='view_article')
def view_article(article_id):
    db = get_db()
    article = db.execute('SELECT * FROM articles WHERE id = ?', (article_id,)).fetchone()
    if article is None:
        return render_template('404.html'), 404  # Render a custom 404 page
    return render_template('article.html', article=article)  # Render the HTML page

@app.route('/explore')
def explore():
    return render_template('browse.html')

@app.route('/db_contents')
def db_contents():
    db = get_db()
    users = db.execute('SELECT * FROM users').fetchall()
    articles = db.execute('SELECT * FROM articles').fetchall()
    comments = db.execute('SELECT * FROM comments').fetchall()
    db.close()

    return render_template('db_contents.html', users=users, articles=articles, comments=comments)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    seed_articles()
    app.run(debug=True)