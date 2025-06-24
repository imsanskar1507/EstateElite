from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from tinydb import TinyDB, Query

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Image Upload Config
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Ensure the upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Databases
db = TinyDB('database/users.json')
property_db = TinyDB('database/properties.json')
User = Query()

# ---------------- Routes ----------------

@app.route('/')
def home():
    properties = property_db.all()
    return render_template("index.html", properties=properties)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        name = request.form['name']

        # Optional admin code
        is_admin = True if request.form.get('admin_code') == 'admin123' else False

        if db.search(User.email == email):
            flash('Email already registered.')
        else:
            # ✅ Define hashed_password before inserting it
            hashed_password = generate_password_hash(password)
            db.insert({
                'name': name,
                'email': email,
                'password': hashed_password,  # hashed password
                'is_admin': is_admin
            })
            flash('Registered successfully!')
            return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # ✅ Get user by email
        user = db.get(User.email == email)

        # ✅ Check if user exists and verify hashed password
        if user and check_password_hash(user['password'], password):
            session['user'] = user['email']
            flash(f"Welcome back, {user['name']}!")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials")

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        flash('Please log in first.')
        return redirect(url_for('login'))

    total_props = len(property_db)
    my_props = property_db.search(Query().added_by == session['user'])
    my_count = len(my_props)
    image_count = len([p for p in my_props if p.get('image')])

    return render_template("dashboard.html",
                           total_props=total_props,
                           my_count=my_count,
                           image_count=image_count)


@app.route('/add_property', methods=['GET', 'POST'])
def add_property():
    if 'user' not in session:
        flash('You must be logged in to add a property.')
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        location = request.form['location']
        price = request.form['price']

        image = request.files.get('image')
        image_filename = None

        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_filename = filename

        property_db.insert({
            'title': title,
            'description': description,
            'location': location,
            'price': price,
            'added_by': session['user'],
            'image': image_filename
        })

        flash('Property added successfully!')
        return redirect(url_for('home'))

    return render_template('add_property.html')

@app.route('/my_properties')
def my_properties():
    if 'user' not in session:
        flash('Please log in first.')
        return redirect(url_for('login'))

    my_props = property_db.search(Query().added_by == session['user'])
    return render_template('my_properties.html', properties=my_props)

@app.route('/edit_property/<int:prop_id>', methods=['GET', 'POST'])
def edit_property(prop_id):
    if 'user' not in session:
        flash('Login required')
        return redirect(url_for('login'))

    property = property_db.get(doc_id=prop_id)

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        location = request.form['location']
        price = request.form['price']
        image = request.files.get('image')

        update_data = {
            'title': title,
            'description': description,
            'location': location,
            'price': price
        }

        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            update_data['image'] = filename  # Only update if new image given

        property_db.update(update_data, doc_ids=[prop_id])

        flash('Property updated successfully.')
        return redirect(url_for('my_properties'))

    return render_template('edit_property.html', property=property)


@app.route('/delete_property/<int:prop_id>')
def delete_property(prop_id):
    if 'user' not in session:
        flash('Login required')
        return redirect(url_for('login'))

    property_db.remove(doc_ids=[prop_id])
    flash('Property deleted successfully.')
    return redirect(url_for('my_properties'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('You have been logged out.')
    return redirect(url_for('home'))

# ---------------- Run the App ----------------

if __name__ == '__main__':
    app.run(debug=True)

@app.route('/', methods=['GET', 'POST'])
def home():
    properties = property_db.all()

    # Handle search/filter
    if request.method == 'POST':
        location = request.form.get('location')
        min_price = request.form.get('min_price')
        max_price = request.form.get('max_price')

        filtered = []

        for prop in properties:
            if location and location.lower() not in prop['location'].lower():
                continue
            if min_price and float(prop['price']) < float(min_price):
                continue
            if max_price and float(prop['price']) > float(max_price):
                continue
            filtered.append(prop)

        properties = filtered

    return render_template("index.html", properties=properties)

@app.route('/admin')
def admin_panel():
    if 'user' not in session:
        flash('Please log in first.')
        return redirect(url_for('login'))

    # Get current user from DB
    current_user = db.get(User.email == session['user'])
    if not current_user or not current_user.get('is_admin'):
        flash('Access denied. Admins only.')
        return redirect(url_for('home'))

    all_props = property_db.all()
    return render_template('admin_panel.html', properties=all_props)
