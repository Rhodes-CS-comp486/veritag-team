import os
import random
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, session
import sqlite3
import json
from flask_session import Session

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secure random key for session
DATABASE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'database.db')

# Configure Flask-Session
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 3600
app.config['SESSION_FILE_DIR'] = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'sessions')
Session(app)  # Initialize Flask-Session

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
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
        db.execute('''CREATE TABLE IF NOT EXISTS reviews (
                                review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                article_id TEXT NOT NULL,
                                user_id INTEGER NOT NULL,
                                bias_rating INTEGER NOT NULL,
                                accuracy_rating INTEGER NOT NULL,
                                quality_rating INTEGER NOT NULL,
                                value_rating INTEGER NOT NULL,
                                overall_rating REAL NOT NULL,
                                review TEXT NOT NULL,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                FOREIGN KEY (article_id) REFERENCES articles(id),
                                FOREIGN KEY (user_id) REFERENCES users(id)
                              )''')
        db.commit()
        load_articles_from_json()
        load_reviews_from_json()

def load_reviews_from_json():
    json_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'dev-reviews.json')
    
    if not os.path.exists(json_file):
        print("Error: File does not exist!")
        return
    
    with open(json_file, 'r', encoding='utf-8') as file:
        content = file.read()
        if not content.strip():
            print("Error: File is empty or contains only whitespace!")
            return
        try:
            reviews = json.loads(content)  # Use json.loads since we read the content
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            return

    db = get_db()
    cursor = db.cursor()
    for review in reviews:
        cursor.execute(
            '''INSERT OR IGNORE INTO reviews (review_id, article_id, user_id, created_at, overall_rating, 
               quality_rating, bias_rating, accuracy_rating, value_rating, review) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (review["review_id"], review["article_id"], review["user_id"], review["created_at"],
             review["overall_rating"], review["quality_rating"], review["bias_rating"],
             review["accuracy_rating"], review["value_rating"], review["review"])
        )
    db.commit()
    db.close()

def load_articles_from_json():
    json_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'dev-articles.json')
    lorem_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lorem.txt')

    try:
        LoremShort, LoremMedium, LoremLong = read_lorem_file(lorem_file)
    except FileNotFoundError:
        LoremShort = "Short placeholder text."
        LoremMedium = "Medium placeholder text."
        LoremLong = "Long placeholder text."

    with open(json_file, 'r', encoding='utf-8') as file:
        articles = json.load(file)

    db = get_db()
    cursor = db.cursor()
    for article in articles:
        length_str = article["length"]
        if length_str == "Short":
            body = LoremShort
            length_int = 5
        elif length_str == "Medium":
            body = LoremMedium
            length_int = 10
        else:
            body = LoremLong
            length_int = 15
        cursor.execute(
            '''INSERT OR IGNORE INTO articles (id, title, author, category, length, summary, rating, source, publication_date, body) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (article["id"], article["title"], article["author"], article["category"], length_int,
             article["summary"], article["rating"], article["source"], article["publication_date"], body)
        )
    db.commit()
    db.close()

def read_lorem_file(filename):
    with open(filename, "r", encoding="utf-8") as file:
        lines = file.readlines()
    short = lines[0].strip() if len(lines) > 0 else "Short placeholder."
    medium = lines[1].strip() if len(lines) > 1 else "Medium placeholder."
    long = lines[2].strip() if len(lines) > 2 else "Long placeholder."
    return short, medium, long

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
        if verified_code not in VALID_VERIFICATION_CODES:
            flash('Invalid verification code!', 'error')
            return redirect(url_for('create_verified_account'))
        db = get_db()
        try:
            db.execute('INSERT INTO users (username, email, password, verified_code) VALUES (?, ?, ?, ?)',
                       (username, email, password, verified_code))
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

    user_id = session.get('user_id')
    username = session.get('username')

    if user_id and username:
        user = db.execute('SELECT verified_code FROM users WHERE id = ?', (user_id,)).fetchone()
        if user and user['verified_code'] != '':
            username = session['username']
        else:
            username = f"Anonymous{random.randint(1, 1000)}"
    else:
        username = f"Anonymous{random.randint(1, 1000)}"

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
    db = get_db()
    user_info = None
    if 'user_id' in session:
        user = db.execute('SELECT username, email FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if user:
            user_info = dict(user)
        else:
            print(f"Debug: No user found for user_id={session['user_id']} in browse")
    articles = db.execute('SELECT id, title, source, author, length, category, summary, body, publication_date, rating FROM articles').fetchall()
    print(f"Debug: browse - user_info={user_info}, session={session}")
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
            session.permanent = True  # Ensure session persists
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['verified_code'] = user['verified_code']
            flash('Login successful!', 'success')
            print(f"Debug: User logged in - user_id={user['id']}, username={username}, verified_code={user['verified_code']}, session={session}")
            return redirect(url_for('browse'))
        else:
            error = True
            flash('Invalid username or password.', 'error')
            print(f"Debug: Login failed for username={username}")
    return render_template('login.html', error=error)

@app.route('/verified_login', methods=['GET', 'POST'])
def verified_login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ? AND password = ? AND verified_code != ""', (username, password)).fetchone()
        if user:
            session.permanent = True  # Ensure session persists
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['verified_code'] = user['verified_code']
            flash('Verified login successful!', 'success')
            print(f"Debug: Verified user logged in - user_id={user['id']}, username={username}, verified_code={user['verified_code']}, session={session}")
            return redirect(url_for('browse_verified'))
        else:
            error = True
            flash('Invalid username, password, or not a verified account.', 'error')
            print(f"Debug: Verified login failed for username={username}")
    return render_template('verified_login.html', error=error)

@app.route('/browse_verified', methods=['POST', 'GET'])
def browse_verified():
    db = get_db()
    user_info = None
    articles = db.execute('SELECT id, title, source, author, length, category, summary, body, publication_date, rating FROM articles').fetchall()
    if 'user_id' in session:
        user = db.execute('SELECT username, email FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if user:
            user_info = dict(user)
        else:
            print(f"Debug: No user found for user_id={session['user_id']} in browse_verified")
    else:
        print("Debug: No user_id in session for browse_verified")
    print(f"Debug: browse_verified - user_info={user_info}, session={session}, articles_count={len(articles)}")
    return render_template('browse_verified.html', user_info=user_info, articles=articles)

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
        return render_template('404.html'), 404
    return render_template('article.html', article=article)

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
    print("Debug: User logged out, session cleared")
    return redirect(url_for('index'))

def get_article_by_id(article_id):
    db = get_db()
    article = db.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    return article


@app.route('/reviews')
def reviews_page():
    db = get_db()
    article_id = request.args.get('article_id')

    if not article_id:
        return "Article ID is required", 400

    article = get_article_by_id(article_id)  # Fetch article details
    if not article:
        return "Article not found", 404

    user_id = session.get('user_id')  # Get user_id from session
    user = None  # Default to None if not logged in

    if user_id:  # Fetch user details if logged in
        user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

    # Fetch all reviews for this article
    reviews = db.execute('SELECT * FROM reviews WHERE article_id = ?', (article_id,)).fetchall()

    return render_template("reviews.html", article=article, user=user, reviews=reviews)


@app.route('/submit_review', methods=['POST'])
def submit_review():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    article_id = request.form.get('article_id')
    bias = int(request.form.get('bias'))
    accuracy = int(request.form.get('accuracy'))
    quality = int(request.form.get('quality'))
    value = int(request.form.get('value'))
    text = request.form.get('text')

    # Calculate the overall rating
    overall_rating = (bias + accuracy + quality + value) / 4.0

    # Insert review into database
    db = get_db()
    db.execute('''
        INSERT INTO reviews (article_id, user_id, bias_rating, accuracy_rating, quality_rating, value_rating, overall_rating, review)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (article_id, user_id, bias, accuracy, quality, value, overall_rating, text))

    db.commit()

    return redirect(url_for('reviews_page', article_id=article_id))


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
else:
    # Initialize when imported
    with app.app_context():
        init_db()