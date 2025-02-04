from flask import Flask, render_template, g
import sqlite3

app = Flask(__name__)

# Database setup
DATABASE = './database/articles.db'

def get_db():
    """Connect to SQLite database."""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    """Create the database and table if they don't exist."""
    with app.app_context():
        db = get_db()
        db.execute('''CREATE TABLE IF NOT EXISTS articles
                       (id INTEGER PRIMARY KEY,
                        title TEXT NOT NULL,
                        source TEXT NOT NULL,
                        summary TEXT NOT NULL)''')
        db.commit()

@app.route('/')
def index():
    """Render the homepage."""
    return render_template('index.html')

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

if __name__ == '__main__':
    init_db()  # Initialize DB
    app.run(debug=True)
