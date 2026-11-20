import os, sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'marketplace.db')
UPLOAD_DIR = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-development-secret')
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = UPLOAD_DIR



def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    con = db()
    con.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
        phone TEXT, college TEXT, location TEXT, password_hash TEXT NOT NULL, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS listings (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, title TEXT NOT NULL,
        category TEXT NOT NULL, price REAL NOT NULL, condition_text TEXT, description TEXT NOT NULL,
        location TEXT, image TEXT, status TEXT DEFAULT 'Available', created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS favorites (
        user_id INTEGER NOT NULL, listing_id INTEGER NOT NULL,
        PRIMARY KEY(user_id, listing_id)
    );
    CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT, listing_id INTEGER NOT NULL,
        buyer_id INTEGER NOT NULL, seller_id INTEGER NOT NULL, created_at TEXT NOT NULL,
        UNIQUE(listing_id, buyer_id, seller_id)
    );
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL,
        sender_id INTEGER NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL
    );
    ''')
    con.commit(); con.close()


init_db()


def current_user():
    if not session.get('user_id'): return None
    con = db(); user = con.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone(); con.close()
    return user


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please login to continue.')
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return wrapper


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



@app.route('/')
def home():
    q = request.args.get('q', '').strip(); category = request.args.get('category', '').strip()
    con = db(); sql = "SELECT listings.*, users.name AS seller_name FROM listings JOIN users ON users.id=listings.user_id WHERE listings.status='Available'"; args=[]
    if q: sql += ' AND (title LIKE ? OR description LIKE ?)'; args += [f'%{q}%', f'%{q}%']
    if category: sql += ' AND category=?'; args.append(category)
    sql += ' ORDER BY listings.id DESC'
    products = con.execute(sql, args).fetchall()
    cats = con.execute('SELECT category, COUNT(*) AS total FROM listings GROUP BY category').fetchall()
    favs = set()
    if session.get('user_id'):
        favs = {r['listing_id'] for r in con.execute('SELECT listing_id FROM favorites WHERE user_id=?', (session['user_id'],)).fetchall()}
    con.close()
    return render_template('home.html', products=products, categories=categories, q=q, selected_category=category, favs=favs, cats=cats, user=current_user())

categories = ['Electronics', 'Laptops', 'Books & Notes', 'Mobiles', 'Cycles', 'Hostel Essentials', 'Accessories', 'Other']

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name=request.form.get('name','').strip(); email=request.form.get('email','').strip().lower(); phone=request.form.get('phone','').strip(); college=request.form.get('college','').strip(); location=request.form.get('location','').strip(); password=request.form.get('password','')
        if not name or not email or len(password)<6:
            flash('Please complete all fields. Password must be at least 6 characters.'); return render_template('register.html')
        con=db()
        try:
            con.execute('INSERT INTO users(name,email,phone,college,location,password_hash,created_at) VALUES(?,?,?,?,?,?,?)',(name,email,phone,college,location,generate_password_hash(password),datetime.now().isoformat(timespec='minutes')))
            con.commit(); uid=con.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()['id']; session['user_id']=uid; session['user_name']=name; flash('Account created. Welcome!'); return redirect(url_for('home'))
        except sqlite3.IntegrityError:
            flash('This email is already registered.')
        finally: con.close()
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
        con=db(); user=con.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone(); con.close()
        if user and check_password_hash(user['password_hash'],password):
            session.clear(); session['user_id']=user['id']; session['user_name']=user['name']; flash('Welcome back!'); return redirect(request.args.get('next') or url_for('home'))
        flash('Incorrect email or password.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear(); flash('You have been logged out.'); return redirect(url_for('home'))

@app.route('/sell', methods=['GET','POST'])
@login_required
def sell():
    if request.method=='POST':
        title=request.form.get('title','').strip(); category=request.form.get('category',''); price=request.form.get('price',''); condition=request.form.get('condition',''); description=request.form.get('description','').strip(); location=request.form.get('location','').strip()
        if not title or not category or not description or not location:
            flash('Please fill all required fields.'); return render_template('sell.html', categories=categories)
        try: price=float(price)
        except ValueError: flash('Enter a valid price.'); return render_template('sell.html', categories=categories)
        image_name=None; file=request.files.get('image')
        if file and file.filename:
            if not allowed_file(file.filename): flash('Only JPG, PNG or WEBP images are allowed.'); return render_template('sell.html', categories=categories)
            image_name=f"{session['user_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"; file.save(os.path.join(UPLOAD_DIR,image_name))
        con=db(); con.execute('INSERT INTO listings(user_id,title,category,price,condition_text,description,location,image,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(session['user_id'],title,category,price,condition,description,location,image_name,datetime.now().isoformat(timespec='minutes'))); con.commit(); con.close(); flash('Your listing is live!'); return redirect(url_for('my_ads'))
    return render_template('sell.html', categories=categories)

@app.route('/product/<int:listing_id>')
def product_detail(listing_id):
    con=db(); product=con.execute('SELECT listings.*, users.name AS seller_name, users.id AS seller_id, users.college AS seller_college FROM listings JOIN users ON users.id=listings.user_id WHERE listings.id=?',(listing_id,)).fetchone(); con.close()
    if not product: abort(404)
    is_fav=False
    if session.get('user_id'):
        con=db(); is_fav=con.execute('SELECT 1 FROM favorites WHERE user_id=? AND listing_id=?',(session['user_id'],listing_id)).fetchone() is not None; con.close()
    return render_template('product_detail.html', product=product, is_fav=is_fav, user=current_user())

@app.route('/favorite/<int:listing_id>', methods=['POST'])
@login_required
def favorite(listing_id):
    con=db(); existing=con.execute('SELECT 1 FROM favorites WHERE user_id=? AND listing_id=?',(session['user_id'],listing_id)).fetchone()
    if existing: con.execute('DELETE FROM favorites WHERE user_id=? AND listing_id=?',(session['user_id'],listing_id))
    else: con.execute('INSERT OR IGNORE INTO favorites(user_id,listing_id) VALUES(?,?)',(session['user_id'],listing_id))
    con.commit(); con.close(); return redirect(request.referrer or url_for('home'))

@app.route('/my-ads')
@login_required
def my_ads():
    con=db(); products=con.execute('SELECT * FROM listings WHERE user_id=? ORDER BY id DESC',(session['user_id'],)).fetchall(); con.close(); return render_template('my_ads.html', products=products)

@app.route('/account')
@login_required
def account():
    return render_template('account.html', user=current_user())

@app.route('/account/update', methods=['POST'])
@login_required
def account_update():
    name=request.form.get('name','').strip(); phone=request.form.get('phone','').strip(); college=request.form.get('college','').strip(); location=request.form.get('location','').strip()
    if name:
        con=db(); con.execute('UPDATE users SET name=?,phone=?,college=?,location=? WHERE id=?',(name,phone,college,location,session['user_id'])); con.commit(); con.close(); session['user_name']=name; flash('Profile updated.')
    return redirect(url_for('account'))

@app.route('/my-ads/delete/<int:listing_id>', methods=['POST'])
@login_required
def delete_ad(listing_id):
    con=db(); row=con.execute('SELECT image FROM listings WHERE id=? AND user_id=?',(listing_id,session['user_id'])).fetchone()
    if row:
        con.execute('DELETE FROM favorites WHERE listing_id=?',(listing_id,)); con.execute('DELETE FROM listings WHERE id=?',(listing_id,)); con.commit()
        if row['image']:
            try: os.remove(os.path.join(UPLOAD_DIR,row['image']))
            except OSError: pass
        flash('Listing removed.')
    con.close(); return redirect(url_for('my_ads'))

@app.route('/chats')
@login_required
def chats():
    con=db(); rows=con.execute('''SELECT chats.id, listings.title, listings.image, users.name AS other_name,
      (SELECT body FROM messages WHERE chat_id=chats.id ORDER BY id DESC LIMIT 1) AS last_message,
      (SELECT created_at FROM messages WHERE chat_id=chats.id ORDER BY id DESC LIMIT 1) AS last_time
      FROM chats JOIN listings ON listings.id=chats.listing_id
      JOIN users ON users.id=CASE WHEN chats.buyer_id=? THEN chats.seller_id ELSE chats.buyer_id END
      WHERE chats.buyer_id=? OR chats.seller_id=? ORDER BY chats.id DESC''',(session['user_id'],session['user_id'],session['user_id'])).fetchall(); con.close(); return render_template('chats.html', chats=rows)

@app.route('/chat/start/<int:listing_id>', methods=['POST'])
@login_required
def start_chat(listing_id):
    con=db(); product=con.execute('SELECT user_id FROM listings WHERE id=?',(listing_id,)).fetchone()
    if not product: con.close(); abort(404)
    seller_id=product['user_id']; buyer_id=session['user_id']
    if seller_id==buyer_id: con.close(); flash('You cannot chat with yourself.'); return redirect(url_for('product_detail',listing_id=listing_id))
    con.execute('INSERT OR IGNORE INTO chats(listing_id,buyer_id,seller_id,created_at) VALUES(?,?,?,?)',(listing_id,buyer_id,seller_id,datetime.now().isoformat(timespec='minutes'))); con.commit(); chat=con.execute('SELECT id FROM chats WHERE listing_id=? AND buyer_id=? AND seller_id=?',(listing_id,buyer_id,seller_id)).fetchone(); con.close(); return redirect(url_for('chat_room',chat_id=chat['id']))

@app.route('/chat/<int:chat_id>', methods=['GET','POST'])
@login_required
def chat_room(chat_id):
    con=db(); chat=con.execute('''SELECT chats.*, listings.title, listings.image, users.name AS other_name FROM chats
      JOIN listings ON listings.id=chats.listing_id JOIN users ON users.id=CASE WHEN chats.buyer_id=? THEN chats.seller_id ELSE chats.buyer_id END
      WHERE chats.id=? AND (chats.buyer_id=? OR chats.seller_id=?)''',(session['user_id'],chat_id,session['user_id'],session['user_id'])).fetchone()
    if not chat: con.close(); abort(404)
    if request.method=='POST':
        body=request.form.get('body','').strip()
        if body:
            con.execute('INSERT INTO messages(chat_id,sender_id,body,created_at) VALUES(?,?,?,?)',(chat_id,session['user_id'],body,datetime.now().isoformat(timespec='minutes'))); con.commit()
        con.close(); return redirect(url_for('chat_room',chat_id=chat_id))
    messages=con.execute('SELECT messages.*, users.name AS sender_name FROM messages JOIN users ON users.id=messages.sender_id WHERE chat_id=? ORDER BY id',(chat_id,)).fetchall(); con.close(); return render_template('chat_room.html', chat=chat, messages=messages)


@app.errorhandler(413)
def too_large(_): return 'Image is too large. Please upload a file under 8 MB.', 413


if __name__ == '__main__':
    app.run(debug=True)
