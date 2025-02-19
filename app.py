import os
from flask import Flask, render_template, g, redirect, url_for, request, flash, jsonify
import sqlite3
import os
import json


app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for flashing messages

# Database setup
# Path relative to the script location, no matter where the script is run from
DATABASE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'database.db')
db = sqlite3.connect(DATABASE)


def seed_articles():
    db = sqlite3.connect(DATABASE)
    cursor = db.cursor()

    # Check if there are already articles in the database
    cursor.execute("SELECT COUNT(*) FROM articles")
    count = cursor.fetchone()[0]

    if count == 0:  # Only insert if no articles exist
        cursor.execute("INSERT INTO articles (title, source, author, length, category, summary) VALUES (?, ?, ?, ?, ?, ?)",
                       ("The Future of AI", "Tech Daily", "Dr. John Smith", 12, "Tech", "AI is transforming the world at an incredible pace."))
        cursor.execute("INSERT INTO articles (title, source, author, length, category, summary) VALUES (?, ?, ?, ?, ?, ?)",
                       ("Health Tips 2025", "Wellness Weekly", "Dr. Alice Johnson", 10, "Health", "New health research reveals how to stay fit."))
        cursor.execute("INSERT INTO articles (title, source, author, length, category, summary) VALUES (?, ?, ?, ?, ?, ?)",
                       ("Exploring Space", "Science World", "Dr. Mark Lee", 15, "Science",
                        "Scientists are looking at new planets beyond our solar system."))

        db.commit()

    db.close()


@app.route('/api/articles')
def get_articles():
    """Fetch all articles from the database and return as JSON."""
    db = get_db()
    articles = db.execute('SELECT id, title, source, author, length, category, summary FROM articles').fetchall()

    articles_list = [dict(article) for article in articles]  # Convert rows to dicts

    return jsonify({"articles": articles_list})  # Wrap list in a dictionary



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
                       (id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        source TEXT NOT NULL,
                        author TEXT NOT NULL,
                        length INTEGER NOT NULL,
                        category TEXT NOT NULL,
                        rating INTEGER NOT NULL,
                        summary TEXT NOT NULL,
                        publication_date TEXT NOT NULL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS users
                       (id INTEGER PRIMARY KEY,
                        username TEXT NOT NULL UNIQUE,
                        email TEXT NOT NULL UNIQUE,
                        password TEXT NOT NULL,
                        verified_code TEXT NOT NULL)''')
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
            '''INSERT OR IGNORE INTO articles (id, title, author, category, length, summary, rating, source, publication_date) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (article["id"], article["title"], article["author"], article["category"], article["length"],
             article["summary"], article["rating"], article["source"], article["publication_date"])
        )

    db.commit()
    db.close()

@app.route('/')
def index():
    """Redirect to the browse page on startup."""
    return redirect(url_for('browse'))


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

VALID_VERIFICATION_CODES = ['12345']  # Example valid codes

@app.route('/create_verified_account', methods=['GET', 'POST'])
def create_verified_account():
    """Handle the creation of a verified account."""
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        verified_code = request.form['verification_code']

        # Password match check
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('create_verified_account'))

        # Verified code check
        if verified_code not in VALID_VERIFICATION_CODES:
            flash('Invalid verification code!', 'error')
            return redirect(url_for('create_verified_account'))

        # Connect to SQLite and insert the user with the verified code
        db = get_db()
        try:
            db.execute('INSERT INTO users (username, email, password, verified_code) VALUES (?, ?, ?, ?)',
                       (username, email, password, verified_code))
            db.commit()
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('verified_login'))  # Redirect to login page
        except sqlite3.IntegrityError:
            flash('Username or email already exists!', 'error')
            return redirect(url_for('create_verified_account'))

    return render_template('create_verified_account.html')


# Route for the About page
@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/api/article/<int:article_id>')
def get_article(article_id):
    """Fetch a single article by ID from the database and return it as JSON."""

    db = get_db()
    article = db.execute('SELECT * FROM articles WHERE id = ?', (article_id,)).fetchone()
    if article is None:
        return jsonify({"error": "Article not found"}), 404

    return jsonify(dict(article))  # Convert row to dict


@app.route('/article/<int:article_id>')
def article_page(article_id):
    """Render the article.html page, which will fetch article data via JavaScript."""
    return render_template("article.html")

@app.route('/browse')
def browse():
    """Display article headlines."""
    db = get_db()
    #articles = db.execute('SELECT * FROM articles').fetchall()
    return render_template('browse.html', articles=get_articles())

@app.route('/article/<int:article_id>')
def article(article_id):
    """View a single article in full screen."""
    db = get_db()
    article = db.execute('SELECT * FROM articles WHERE id = ?', (article_id,)).fetchone()
    if article is None:
        flash('Article not found!', 'error')
        return redirect(url_for('browse'))
    return render_template('article.html', articleId=article_id)


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



@app.route('/verified_login', methods=['GET', 'POST'])
def verified_login():
    """Handle verified user login."""
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ? AND password = ? AND verified_code != ""', 
                          (username, password)).fetchone()

        if user:
            flash('Verified login successful!', 'success')
            return render_template('browse_verified.html')  # Change to browse_verified.html
        else:
            error = True

    return render_template('verified_login.html', error=error)


@app.route('/browse_verified', methods=['POST', 'GET'])
def browse_verified():
    if request.method == 'POST':
        # handle POST logic
        return render_template('browse_verified.html')
    return render_template('browse_verified.html')

# Route for the community page
@app.route('/community')
def community():
    return render_template('community.html')

@app.route('/categories')
def categories():
    response = get_articles()  # This returns a Response object
    articles = json.loads(response.get_data(as_text=True))["articles"]  # Extract article list

    # Group articles by category
    categories = {}
    for article in articles:
        category = article["category"]
        if category not in categories:
            categories[category] = []
        categories[category].append(article)

    return render_template('categories.html', categories=categories)

@app.route('/explore')
def explore():
    return render_template('browse.html')



if __name__ == '__main__':
    init_db()  # Initialize DB
    app.run(debug=True)

