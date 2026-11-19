import os
import re
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import or_

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'campus_marketplace_2026_secret')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///campus_market_v4.db'

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'docx', 'pptx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- Validation Helpers ---
def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def is_valid_phone(phone):
    # Strictly 10 digits starting with 6-9
    return re.match(r'^[6-9]\d{9}$', phone) is not None

# --- Database Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Resource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300), nullable=True)
    price = db.Column(db.String(50), default='Free')
    is_available = db.Column(db.Boolean, default=True)
    filename = db.Column(db.String(300), nullable=False)
    owner = db.Column(db.String(150), nullable=False)
    owner_id = db.Column(db.Integer, nullable=False)
    contact = db.Column(db.String(15), nullable=False)
    uploaded_at = db.Column(db.String(50), default=lambda: datetime.now().strftime("%d %b %Y"))

class ResourceRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    details = db.Column(db.String(300), nullable=False)
    requested_by = db.Column(db.String(150), nullable=False)
    status = db.Column(db.String(50), default='Pending')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Ensure database tables exist even when started via Gunicorn
with app.app_context():
    db.create_all()

# --- Routes ---
@app.route('/')
def home():
    search_query = request.args.get('search', '').strip()
    category_filter = request.args.get('category', 'All')
    avail_filter = request.args.get('availability', 'All')

    query = Resource.query

    if search_query:
        query = query.filter(
            or_(
                Resource.title.ilike(f'%{search_query}%'),
                Resource.description.ilike(f'%{search_query}%'),
                Resource.category.ilike(f'%{search_query}%')
            )
        )
    if category_filter and category_filter != 'All':
        query = query.filter(Resource.category == category_filter)

    if avail_filter == 'Available':
        query = query.filter(Resource.is_available == True)
    elif avail_filter == 'Not Available':
        query = query.filter(Resource.is_available == False)

    resources = query.order_by(Resource.id.desc()).all()
    all_titles = [r.title for r in Resource.query.all()]

    stats = {
        'total_users': User.query.count(),
        'total_resources': Resource.query.count(),
        'available_items': Resource.query.filter_by(is_available=True).count()
    }
    return render_template('index.html', resources=resources, stats=stats, all_titles=all_titles)

@app.route('/contribute')
@login_required
def contribute():
    return render_template('contribute.html')

@app.route('/add', methods=['POST'])
@login_required
def add_resource():
    title = request.form.get('title', '').strip()
    category = request.form.get('category', '')
    description = request.form.get('description', '').strip()
    price = request.form.get('price', 'Free').strip() or 'Free'
    is_available = request.form.get('is_available') == 'true'
    contact = request.form.get('contact', '').strip()
    file = request.files.get('file')

    if len(title) < 3:
        flash('Error: Item title must be at least 3 characters long.')
        return redirect(url_for('contribute'))

    if not is_valid_phone(contact):
        flash('Error: Invalid Mobile Number! Enter an exact 10-digit mobile number (starting with 6-9).')
        return redirect(url_for('contribute'))

    if not file or not allowed_file(file.filename):
        flash('Error: Invalid file! Allowed formats: JPG, PNG, PDF, DOCX, PPTX')
        return redirect(url_for('contribute'))

    original_name = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4().hex[:8]}_{original_name}"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))

    new_res = Resource(
        title=title,
        category=category,
        description=description,
        price=price,
        is_available=is_available,
        filename=unique_filename,
        owner=current_user.username,
        owner_id=current_user.id,
        contact=contact
    )
    db.session.add(new_res)
    db.session.commit()
    flash('Item listed successfully on Campus Marketplace!')
    return redirect(url_for('home'))

@app.route('/toggle_status/<int:id>', methods=['POST'])
@login_required
def toggle_status(id):
    resource = Resource.query.get_or_404(id)
    if current_user.is_admin or current_user.id == resource.owner_id:
        resource.is_available = not resource.is_available
        db.session.commit()
        status_text = "Available" if resource.is_available else "Not Available"
        flash(f'Status updated to "{status_text}"!')
    return redirect(request.referrer or url_for('home'))

@app.route('/requests')
def view_requests():
    requests_list = ResourceRequest.query.order_by(ResourceRequest.id.desc()).all()
    return render_template('requests.html', requests_list=requests_list)

@app.route('/request_resource', methods=['POST'])
@login_required
def request_resource():
    topic = request.form.get('topic', '').strip()
    category = request.form.get('category', '')
    details = request.form.get('details', '').strip()

    if len(topic) < 3:
        flash('Error: Please enter a valid topic name.')
        return redirect(url_for('contribute'))

    new_req = ResourceRequest(
        topic=topic,
        category=category,
        details=details,
        requested_by=current_user.username
    )
    db.session.add(new_req)
    db.session.commit()
    flash('Request posted on the Request Board!')
    return redirect(url_for('view_requests'))

@app.route('/fulfill_request/<int:id>', methods=['POST'])
@login_required
def fulfill_request(id):
    req = ResourceRequest.query.get_or_404(id)
    if current_user.is_admin or current_user.username == req.requested_by:
        req.status = 'Fulfilled'
        db.session.commit()
        flash('Request marked as Fulfilled!')
    return redirect(url_for('view_requests'))

@app.route('/delete_request/<int:id>', methods=['POST'])
@login_required
def delete_request(id):
    req = ResourceRequest.query.get_or_404(id)
    if current_user.is_admin or current_user.username == req.requested_by:
        db.session.delete(req)
        db.session.commit()
        flash('Request deleted.')
    return redirect(url_for('view_requests'))

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access Denied: Admins only.')
        return redirect(url_for('home'))
    users = User.query.all()
    resources = Resource.query.order_by(Resource.id.desc()).all()
    requests_list = ResourceRequest.query.order_by(ResourceRequest.id.desc()).all()
    return render_template('admin.html', users=users, resources=resources, requests_list=requests_list)

@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_resource(id):
    resource = Resource.query.get_or_404(id)
    if current_user.is_admin or current_user.id == resource.owner_id:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], resource.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        db.session.delete(resource)
        db.session.commit()
        flash('Item deleted successfully.')
    return redirect(request.referrer or url_for('home'))

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')

        if len(username) < 3:
            flash('Error: Full Name must be at least 3 characters.')
            return redirect(url_for('register'))

        if not is_valid_email(email):
            flash('Error: Please enter a valid Email Address (e.g., name@college.edu).')
            return redirect(url_for('register'))

        if not is_valid_phone(phone):
            flash('Error: Mobile number must be exact 10 digits (starting with 6-9).')
            return redirect(url_for('register'))

        if len(password) < 6:
            flash('Error: Password must be at least 6 characters long.')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Error: This email is already registered! Please login.')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='scrypt')
        is_admin = User.query.count() == 0

        new_user = User(username=username, email=email, phone=phone, password=hashed_password, is_admin=is_admin)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        flash('Account created successfully!')
        return redirect(url_for('home'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not is_valid_email(email):
            flash('Error: Invalid email format!')
            return redirect(url_for('login'))

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash(f'Welcome back, {user.username}!')
            return redirect(url_for('home'))
        else:
            flash('Error: Incorrect email or password! Account not found.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)