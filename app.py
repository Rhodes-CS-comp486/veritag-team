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
        # Drop the comments and reviews tables if they exist to ensure the schema is updated
        db.execute('DROP TABLE IF EXISTS comments')
        db.execute('DROP TABLE IF EXISTS reviews')
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
                        upvotes INTEGER DEFAULT 0,
                        downvotes INTEGER DEFAULT 0,
                        verified BOOLEAN DEFAULT 0,
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
        db.execute('''CREATE TABLE IF NOT EXISTS comment_votes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        comment_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        vote_type TEXT NOT NULL, -- 'upvote' or 'downvote'
                        UNIQUE(comment_id, user_id),
                        FOREIGN KEY (comment_id) REFERENCES comments(id),
                        FOREIGN KEY (user_id) REFERENCES users(id)
                      )''')
        
        db.execute('''CREATE TABLE IF NOT EXISTS following (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        follower_id INTEGER NOT NULL,
                        following_id INTEGER NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (follower_id, following_id),
                        CHECK (follower_id != following_id),
                        FOREIGN KEY (follower_id) REFERENCES users(id),
                        FOREIGN KEY (following_id) REFERENCES users(id)
                    )
                ''')
        
        db.commit()
        load_articles_from_json()
        load_reviews_from_json()
        load_users_from_json()
        fix_ratings()


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
            (article["id"], article["title"], article["author"], article["category"], article["length"],
             article["summary"], article["rating"], article["source"], article["publication_date"], body)
        )
    db.commit()
    db.close()

def load_users_from_json():
    json_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'dev-users.json')

    if not os.path.exists(json_file):
        print("Error: File does not exist!")
        return

    with open(json_file, 'r', encoding='utf-8') as file:
        content = file.read()
        if not content.strip():
            print("Error: File is empty or contains only whitespace!")
            return
        try:
            users = json.loads(content)  # Use json.loads since we read the content
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            return

    db = get_db()
    cursor = db.cursor()
    for user in users:
        cursor.execute(
            '''INSERT OR IGNORE INTO users (id, username, email, password, verified_code) 
               VALUES (?, ?, ?, ?, ?)''',
            (user["id"], user["username"], user["email"], user["password"], user["verified_code"])
        )
    db.commit()
    db.close()

def fix_ratings():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT article_id FROM reviews GROUP BY article_id')
    article_ids = cursor.fetchall()
    for article_id in article_ids:
        cursor.execute('SELECT AVG(overall_rating) FROM reviews WHERE article_id = ?', (article_id['article_id'],))
        avg_rating = cursor.fetchone()
        cursor.execute('UPDATE articles SET rating = ? WHERE id = ?', (("{:.2f}".format(avg_rating[0]), article_id['article_id'])))
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
        db = get_db()
        user = db.execute('SELECT username, verified_code FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if user:
            return jsonify({
                "username": user['username'],
                "verified": user['verified_code'] != ''  # Return true if verified_code is non-empty
            })
        return jsonify({}), 404  # User not found in DB (shouldn't happen with valid session)
    return jsonify({}), 401  # Not logged in

@app.route('/api/articles')
def get_articles():
    db = get_db()
    articles = db.execute('''
        SELECT a.id, a.title, a.source, a.author, a.length, a.category, 
               COALESCE(AVG(r.overall_rating), 0) AS rating, 
               a.body, a.summary, a.publication_date
        FROM articles a
        LEFT JOIN reviews r ON a.id = r.article_id
        GROUP BY a.id
        ORDER BY a.publication_date DESC
    ''').fetchall()

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
    # Check if the article exists
    article = db.execute('SELECT id FROM articles WHERE id = ?', (article_id,)).fetchone()
    if not article:
        return jsonify({"error": "Article not found"}), 404

    comments = db.execute(
        '''SELECT c.id, c.username, c.text, c.upvotes, c.downvotes, c.created_at, 
                  CASE WHEN u.verified_code != '' THEN 1 ELSE 0 END AS verified
           FROM comments c
           LEFT JOIN users u ON c.user_id = u.id
           WHERE c.article_id = ?
           ORDER BY c.created_at DESC''',
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
    is_verified = False

    if user_id and username:
        user = db.execute('SELECT verified_code FROM users WHERE id = ?', (user_id,)).fetchone()
        if user and user['verified_code'] != '':
            is_verified = True
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
            'SELECT id, username, text, upvotes, downvotes, created_at FROM comments WHERE id = ?',
            (cursor.lastrowid,)
        ).fetchone()
        return jsonify({
            "id": new_comment['id'],
            "username": new_comment['username'],
            "text": new_comment['text'],
            "upvotes": new_comment['upvotes'],
            "downvotes": new_comment['downvotes'],
            "created_at": new_comment['created_at'],
            "verified": is_verified  # Include verified status in response
        }), 201
    except sqlite3.Error as e:
        return jsonify({"error": "Failed to post comment: " + str(e)}), 500

@app.route('/api/comment/<int:comment_id>/vote', methods=['POST'])
def vote_comment(comment_id):
    if 'user_id' not in session:
        return jsonify({"error": "User not logged in"}), 401

    data = request.get_json()
    vote_type = data.get('vote_type')  # 'upvote', 'downvote', or None (to remove vote)
    user_id = session['user_id']
    db = get_db()

    # Check if the user has already voted on this comment
    existing_vote = db.execute(
        'SELECT vote_type FROM comment_votes WHERE comment_id = ? AND user_id = ?',
        (comment_id, user_id)
    ).fetchone()

    if existing_vote:
        if vote_type is None:
            # Remove the existing vote
            db.execute('DELETE FROM comment_votes WHERE comment_id = ? AND user_id = ?', (comment_id, user_id))
            if existing_vote['vote_type'] == 'upvote':
                db.execute('UPDATE comments SET upvotes = upvotes - 1 WHERE id = ?', (comment_id,))
            else:
                db.execute('UPDATE comments SET downvotes = downvotes - 1 WHERE id = ?', (comment_id,))
        elif existing_vote['vote_type'] != vote_type:
            # Change the vote type
            db.execute(
                'UPDATE comment_votes SET vote_type = ? WHERE comment_id = ? AND user_id = ?',
                (vote_type, comment_id, user_id)
            )
            if vote_type == 'upvote':
                db.execute('UPDATE comments SET upvotes = upvotes + 1, downvotes = downvotes - 1 WHERE id = ?', (comment_id,))
            else:
                db.execute('UPDATE comments SET upvotes = upvotes - 1, downvotes = downvotes + 1 WHERE id = ?', (comment_id,))
    else:
        if vote_type is not None:
            # Add a new vote
            db.execute(
                'INSERT INTO comment_votes (comment_id, user_id, vote_type) VALUES (?, ?, ?)',
                (comment_id, user_id, vote_type)
            )
            if vote_type == 'upvote':
                db.execute('UPDATE comments SET upvotes = upvotes + 1 WHERE id = ?', (comment_id,))
            else:
                db.execute('UPDATE comments SET downvotes = downvotes + 1 WHERE id = ?', (comment_id,))

    db.commit()
    updated_comment = db.execute('SELECT upvotes, downvotes FROM comments WHERE id = ?', (comment_id,)).fetchone()
    return jsonify({"upvotes": updated_comment['upvotes'], "downvotes": updated_comment['downvotes']})

@app.route('/article/<article_id>')
def article_page(article_id):
    db = get_db()
    is_verified = False
    if 'user_id' in session:
        user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if user:
            user_info = dict(user)
        if user and user['verified_code'] != '':
            is_verified = True
    return render_template('article.html', is_verified=is_verified, user_info=user_info)

@app.route('/browse')
def browse():
    db = get_db()
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
            session.permanent = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['verified_code'] = user['verified_code']
            flash('Login successful!', 'success')
            return redirect(url_for('browse'))
        else:
            error = True
            flash('Invalid username or password.', 'error')
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
            session.permanent = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['verified_code'] = user['verified_code']
            flash('Verified login successful!', 'success')
            return redirect(url_for('browse_verified'))
        else:
            error = True
            flash('Invalid username, password, or not a verified account.', 'error')
    return render_template('verified_login.html', error=error)

@app.route('/browse', methods=['POST', 'GET'])
def browse_verified():
    db = get_db()
    user_info = None
    articles = db.execute('SELECT id, title, source, author, length, category, summary, body, publication_date, rating FROM articles').fetchall()
    if 'user_id' in session:
        user = db.execute('SELECT username, email FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if user:
            user_info = dict(user)
    return render_template('browse.html', user_info=user_info, articles=articles)


@app.route('/verified_users', methods=['POST', 'GET'])
def verified_users():
    db = get_db()
    # Query to get verified users and their reviewed articles
    verified_users = db.execute('''
        SELECT DISTINCT u.id, u.username 
        FROM users u 
        WHERE u.verified_code != ""
    ''').fetchall()

    # For each verified user, get the articles they've reviewed
    users_with_reviews = []
    for user in verified_users:
        reviewed_articles = db.execute('''
            SELECT a.id, a.title 
            FROM articles a
            INNER JOIN reviews r ON a.id = r.article_id
            WHERE r.user_id = ?
            ORDER BY r.created_at DESC
        ''', (user['id'],)).fetchall()

        users_with_reviews.append({
            'id': user['id'],
            'username': user['username'],
            'reviewed_articles': [dict(article) for article in reviewed_articles]
        })

        if 'user_id' in session:
            user = db.execute('SELECT username, email FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if user:
            user_info = dict(user)

    return render_template('verified_users.html', verified_users=users_with_reviews, user=user_info)

@app.route('/api/toggle_follow', methods=['POST'])
def toggle_follow():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    # Get request data
    data = request.get_json()
    following_id = data.get('following_id')
    action = data.get('action')
    
    # Validate request data
    if not following_id or action not in ['follow', 'unfollow']:
        return jsonify({'success': False, 'message': 'Invalid request'}), 400
    
    db = get_db()
    user_id = session.get('user_id')
    
    try:
        if action == 'follow':
            # Check if already following to avoid duplicates
            existing = db.execute(
                'SELECT id FROM following WHERE follower_id = ? AND following_id = ?',
                (user_id, following_id)
            ).fetchone()
            
            if not existing:
                # Create new follow relationship
                db.execute(
                    'INSERT INTO following (follower_id, following_id) VALUES (?, ?)',
                    (user_id, following_id)
                )
                db.commit()
        
        elif action == 'unfollow':
            # Delete existing follow relationship
            db.execute(
                'DELETE FROM following WHERE follower_id = ? AND following_id = ?',
                (user_id, following_id)
            )
            db.commit()
        
        return jsonify({'success': True})
    
    except sqlite3.Error as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/following')
def get_following():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'following': []})
    
    db = get_db()
    # Get all users that the current user is following
    following = db.execute(
        'SELECT following_id FROM following WHERE follower_id = ?',
        (user_id,)
    ).fetchall()
    
    following_ids = [follow['following_id'] for follow in following]
    return jsonify({'following': following_ids})

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
    user_info = None
    if 'user_id' in session:
        user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if user:
            user_info = dict(user)
    if article is None:
        return render_template('404.html'), 404
    return render_template('article.html', article=article, user_info=user_info)

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
    article = get_article_by_id(article_id)
    if not article:
        return "Article not found", 404
    user_id = session.get('user_id')
    user = None
    if user_id:
        user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    reviews = db.execute('SELECT * FROM reviews WHERE article_id = ?', (article_id,)).fetchall()
    authors = {}
    for review in reviews:
        author = db.execute('SELECT * FROM users WHERE id = ?', (review['user_id'],)).fetchone()
        if author:
            authors[review['user_id']] = author['username']
        else:
            authors[review['user_id']] = 'User ' + str(review['user_id'])

    return render_template("reviews.html", article=article, user=user, reviews=reviews, authors=authors)


@app.route('/submit_review', methods=['POST'])
def submit_review():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    article_id = request.form.get('article_id')
    bias = float(request.form.get('bias'))
    accuracy = float(request.form.get('accuracy'))
    quality = float(request.form.get('quality'))
    value = float(request.form.get('value'))
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


@app.route('/api/article_ratings/<int:article_id>')
def get_article_ratings(article_id):
    db = get_db()
    ratings = db.execute('''
        SELECT AVG(bias_rating) as avg_bias, 
               AVG(accuracy_rating) as avg_accuracy, 
               AVG(quality_rating) as avg_quality, 
               AVG(value_rating) as avg_value, 
               AVG(overall_rating) as avg_overall
        FROM reviews WHERE article_id = ?
    ''', (article_id,)).fetchone()

    if not ratings or ratings['avg_overall'] is None:
        return jsonify({"error": "No ratings available"}), 404

    return jsonify({
        "bias": round(ratings['avg_bias'], 2),
        "accuracy": round(ratings['avg_accuracy'], 2),
        "quality": round(ratings['avg_quality'], 2),
        "value": round(ratings['avg_value'], 2),
        "overall": round(ratings['avg_overall'], 2)
    })


@app.route('/profile')
def profile():
    db = get_db()
    user_info = None
    following = []  # Assuming you'll fetch the list of followed users from the database

    # Check if user is logged in
    if 'user_id' in session:
        user = db.execute('SELECT username, email FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if user:
            user_info = dict(user)

        # Fetch following list, assuming you have a table for user follow relationships
        following = db.execute('SELECT following_id FROM following WHERE id = ?', (session['user_id'],)).fetchall()

    return render_template('profile.html', user_info=user_info, following=following)



if __name__ == '__main__':
    init_db()
    app.run(debug=True)
else:
    # Initialize when imported
    with app.app_context():
        init_db()