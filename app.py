import os
import json
import hashlib
import secrets
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
import qrcode
import requests

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-change-this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///seqrly.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = 'static/uploads'
QR_FOLDER = 'static/qrcodes'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'mp4', 'mp3', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['QR_FOLDER'] = QR_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(QR_FOLDER, exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    qr_packs = db.relationship('QRData', backref='owner', lazy=True)

    def set_password(self, password):
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()

    def check_password(self, password):
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class QRData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    use_case = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='active')
    secret_key = db.Column(db.String(64), unique=True, nullable=False)
    data = db.Column(db.Text, nullable=False)
    ui = db.Column(db.Text, nullable=False)
    security_question = db.Column(db.String(200), nullable=True)
    security_answer_hash = db.Column(db.String(64), nullable=True)
    pin_hash = db.Column(db.String(64), nullable=True)
    logo_path = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_public = db.Column(db.Boolean, default=True)
    scan_count = db.Column(db.Integer, default=0)
    last_scanned = db.Column(db.DateTime, nullable=True)

    def get_data(self):
        return json.loads(self.data)

    def get_ui(self):
        return json.loads(self.ui)

    def set_data(self, data_dict):
        self.data = json.dumps(data_dict)

    def set_ui(self, ui_dict):
        self.ui = json.dumps(ui_dict)

    def set_pin(self, pin):
        if pin:
            self.pin_hash = hashlib.sha256(pin.encode()).hexdigest()
        else:
            self.pin_hash = None

    def check_pin(self, pin):
        if not self.pin_hash:
            return True
        return hashlib.sha256(pin.encode()).hexdigest() == self.pin_hash

    def set_security_answer(self, answer):
        if answer:
            self.security_answer_hash = hashlib.sha256(answer.lower().strip().encode()).hexdigest()
        else:
            self.security_answer_hash = None

    def check_security_answer(self, answer):
        if not self.security_answer_hash:
            return False
        return hashlib.sha256(answer.lower().strip().encode()).hexdigest() == self.security_answer_hash

class ScanLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pack_id = db.Column(db.Integer, db.ForeignKey('qr_data.id'), nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(200), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    city = db.Column(db.String(100), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_found_report = db.Column(db.Boolean, default=False)

    pack = db.relationship('QRData', backref=db.backref('scan_logs', lazy=True, cascade='all, delete-orphan'))

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pack_id = db.Column(db.Integer, db.ForeignKey('qr_data.id'), nullable=False)
    type = db.Column(db.String(30), nullable=False)
    message = db.Column(db.Text, nullable=False)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    extra_data = db.Column(db.Text, nullable=True)

    pack = db.relationship('QRData', backref=db.backref('notifications', lazy=True, cascade='all, delete-orphan'))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_secret_key():
    return secrets.token_urlsafe(32)

def generate_qr(pack_id):
    url = url_for('view_pack', pack_id=pack_id, _external=True)
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#775035", back_color="#faede7")
    filename = f"{pack_id}.png"
    filepath = os.path.join(app.config['QR_FOLDER'], filename)
    img.save(filepath)
    return filename

def get_geolocation(ip):
    try:
        resp = requests.get(f'http://ip-api.com/json/{ip}?fields=status,lat,lon,city,country')
        if resp.status_code == 200:
            data = resp.json()
            if data.get('status') == 'success':
                return {
                    'lat': data.get('lat'),
                    'lon': data.get('lon'),
                    'city': data.get('city'),
                    'country': data.get('country')
                }
    except:
        pass
    return None

def calculate_age(born_str):
    """Convert ISO date string to age in years."""
    if not born_str:
        return None
    try:
        born = datetime.strptime(born_str, '%Y-%m-%d').date()
        today = datetime.utcnow().date()
        age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        return age
    except ValueError:
        return None

def get_real_ip(request):
    """Get the real client IP from request headers."""
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr


@app.template_filter('format_date')
def format_date_filter(date_str):
    """Convert ISO date (YYYY-MM-DD) to DD/MM/YYYY."""
    if not date_str:
        return ''
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        return dt.strftime('%d/%m/%Y')
    except ValueError:
        return date_str

@app.template_filter('age_from_dob')
def age_from_dob_filter(date_str):
    """Compute age in years from ISO date string (YYYY-MM-DD)."""
    if not date_str:
        return None
    try:
        born = datetime.strptime(date_str, '%Y-%m-%d').date()
        today = datetime.utcnow().date()
        age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        return age
    except ValueError:
        return None

@app.template_filter('utc_to_ist')
def utc_to_ist_filter(utc_dt):
    """Convert UTC datetime to IST (UTC+5:30) string."""
    if not utc_dt:
        return ''
    from datetime import timedelta
    ist = utc_dt + timedelta(hours=5, minutes=30)
    return ist.strftime('%d %b %Y %I:%M %p')

@app.template_filter('from_json')
def from_json_filter(s):
    return json.loads(s)


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static', 'images'),
        'favic.png',
        mimetype='image/png'
    )

@app.route('/api/submit_form/<int:pack_id>', methods=['POST'])
def submit_form(pack_id):
    pack = QRData.query.get_or_404(pack_id)
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'Invalid request'}), 400

    notif = Notification(
        pack_id=pack.id,
        type='form_submission',
        message="New form submission received",
        extra_data=json.dumps(data)
    )
    db.session.add(notif)
    db.session.commit()
    return jsonify({'status': 'ok', 'message': 'Form submitted successfully!'})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('login'))
        login_user(user, remember=remember)
        next_page = request.args.get('next')
        return redirect(next_page) if next_page else redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    packs = QRData.query.filter_by(user_id=current_user.id).order_by(QRData.created_at.desc()).all()
    return render_template('dashboard.html', packs=packs)

@app.route('/select')
@login_required
def select():
    return render_template('select.html')

@app.route('/create/<case>', methods=['GET', 'POST'])
@login_required
def create(case):
    if case not in ['medical', 'lost', 'vehicle', 'custom']:
        return "Invalid case", 404

    if request.method == 'POST':
        data = {}
        ui = {}

        if case == 'medical':
            data['patient_name'] = request.form.get('patient_name')
            data['date_of_birth'] = request.form.get('date_of_birth')
            data['age'] = calculate_age(data['date_of_birth'])
            data['blood_group'] = request.form.get('blood_group')
            data['allergy_penicillin'] = 'allergy_penicillin' in request.form
            data['allergy_sulfa'] = 'allergy_sulfa' in request.form
            data['allergy_nsaids'] = 'allergy_nsaids' in request.form
            data['allergy_shellfish'] = 'allergy_shellfish' in request.form
            data['allergy_latex'] = 'allergy_latex' in request.form
            data['allergy_other'] = request.form.get('allergy_other') if 'allergy_other' in request.form else ''
            data['condition_heart_disease'] = 'condition_heart_disease' in request.form
            data['condition_hypertension'] = 'condition_hypertension' in request.form
            data['condition_diabetes'] = 'condition_diabetes' in request.form
            data['condition_asthma'] = 'condition_asthma' in request.form
            data['condition_copd'] = 'condition_copd' in request.form
            data['condition_kidney_disease'] = 'condition_kidney_disease' in request.form
            data['condition_liver_disease'] = 'condition_liver_disease' in request.form
            data['condition_stroke'] = 'condition_stroke' in request.form
            data['condition_cancer'] = 'condition_cancer' in request.form
            data['condition_thyroid'] = 'condition_thyroid' in request.form
            data['condition_epilepsy'] = 'condition_epilepsy' in request.form
            data['condition_hiv_aids'] = 'condition_hiv_aids' in request.form
            data['condition_tuberculosis'] = 'condition_tuberculosis' in request.form
            data['condition_mental_health'] = 'condition_mental_health' in request.form
            data['condition_other'] = request.form.get('condition_other')
            data['medications'] = request.form.get('medications')
            data['organ_donor'] = 'organ_donor' in request.form
            data['dnr'] = 'dnr' in request.form
            data['emergency_contact_name'] = request.form.get('emergency_contact_name')
            data['emergency_contact_relationship'] = request.form.get('emergency_contact_relationship')
            data['emergency_contact_phone'] = request.form.get('emergency_contact_phone')
            data['primary_care_physician'] = request.form.get('primary_care_physician')
            data['primary_care_physician_phone'] = request.form.get('primary_care_physician_phone')
            data['hospital_affiliation'] = request.form.get('hospital_affiliation')
            data['insurance_policy_number'] = request.form.get('insurance_policy_number')
            data['abha_id'] = request.form.get('abha_id')
            data['additional_notes'] = request.form.get('additional_notes')

        elif case == 'lost':
            data['item_name'] = request.form.get('item_name')
            data['item_category'] = request.form.get('item_category')
            data['brand'] = request.form.get('brand')
            data['model'] = request.form.get('model')
            data['color'] = request.form.get('color')
            data['unique_identifier'] = request.form.get('unique_identifier')
            data['description'] = request.form.get('description')
            data['reward'] = request.form.get('reward')
            data['last_known_location'] = request.form.get('last_known_location')
            data['date_lost'] = request.form.get('date_lost')
            data['contact_name'] = request.form.get('contact_name')
            data['contact_phone'] = request.form.get('contact_phone')
            data['contact_email'] = request.form.get('contact_email')
            data['additional_notes'] = request.form.get('additional_notes')
            proof = request.files.get('proof_file')
            if proof and allowed_file(proof.filename):
                fname = secure_filename(proof.filename)
                proof.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                data['proof_file'] = fname
            else:
                data['proof_file'] = None

        elif case == 'vehicle':
            data['registration_number'] = request.form.get('registration_number')
            data['make'] = request.form.get('make')
            data['model'] = request.form.get('model')
            data['year'] = request.form.get('year')
            data['color'] = request.form.get('color')
            data['fuel_type'] = request.form.get('fuel_type')
            data['transmission'] = request.form.get('transmission')
            data['engine_number'] = request.form.get('engine_number')
            data['chassis_number'] = request.form.get('chassis_number')
            data['owner_name'] = request.form.get('owner_name')
            data['owner_phone'] = request.form.get('owner_phone')
            data['owner_email'] = request.form.get('owner_email')
            data['insurance_policy_number'] = request.form.get('insurance_policy_number')
            data['insurance_expiry_date'] = request.form.get('insurance_expiry_date')
            data['rc_details'] = request.form.get('rc_details')
            data['tow_notes'] = request.form.get('tow_notes')
            data['emergency_contact_name'] = request.form.get('emergency_contact_name')
            data['emergency_contact_phone'] = request.form.get('emergency_contact_phone')
            data['additional_notes'] = request.form.get('additional_notes')
            dl = request.files.get('dl_file')
            if dl and allowed_file(dl.filename):
                fname = secure_filename(dl.filename)
                dl.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                data['dl_file'] = fname
            else:
                data['dl_file'] = None
            ins = request.files.get('ins_file')
            if ins and allowed_file(ins.filename):
                fname = secure_filename(ins.filename)
                ins.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                data['ins_file'] = fname
            else:
                data['ins_file'] = None

        else:
            blocks = []
            block_types = request.form.getlist('block_type[]')
            block_contents = request.form.getlist('block_content[]')
            block_files = request.files.getlist('block_file[]')

            for idx, btype in enumerate(block_types):
                content = block_contents[idx] if idx < len(block_contents) else ''
                if btype == 'file':
                    file_obj = block_files[idx] if idx < len(block_files) else None
                    if file_obj and allowed_file(file_obj.filename):
                        fname = secure_filename(file_obj.filename)
                        import time
                        unique_name = f"{int(time.time())}_{fname}"
                        file_obj.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
                        content = unique_name
                    else:
                        content = ''
                blocks.append({'type': btype, 'content': content})
            data['blocks'] = blocks

            file_inputs = request.files.getlist('block_file[]')
            file_idx = 0
            for i, block in enumerate(blocks):
                if block['type'] == 'file':
                    if file_idx < len(file_inputs):
                        file = file_inputs[file_idx]
                        if file and allowed_file(file.filename):
                            fname = secure_filename(file.filename)
                            file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                            block['content'] = fname
                        else:
                            block['content'] = ''
                        file_idx += 1

        logo = request.files.get('logo')
        logo_filename = None
        if logo and allowed_file(logo.filename):
            logo_filename = secure_filename(logo.filename)
            logo.save(os.path.join(app.config['UPLOAD_FOLDER'], logo_filename))

        secret = generate_secret_key()
        new_pack = QRData(
            user_id=current_user.id,
            use_case=case,
            status='active',
            secret_key=secret,
            data=json.dumps(data),
            ui=json.dumps(ui),
            logo_path=logo_filename
        )

        if case != 'medical':
            pin = request.form.get('pin')
            security_question = request.form.get('security_question')
            security_answer = request.form.get('security_answer')
            new_pack.set_pin(pin)
            new_pack.set_security_answer(security_answer)
            if security_question:
                new_pack.security_question = security_question

        db.session.add(new_pack)
        db.session.commit()

        qr_filename = generate_qr(new_pack.id)

        return render_template('success.html', pack=new_pack, qr_filename=qr_filename, secret=secret)

    return render_template(f'create_{case}.html', case=case)

@app.route('/view/<int:pack_id>')
def view_pack(pack_id):
    pack = QRData.query.get_or_404(pack_id)

    data = pack.get_data()
    ui = pack.get_ui()

    if not pack.is_public:
        if not current_user.is_authenticated or current_user.id != pack.user_id:
            return render_template('private.html'), 403

    ip = get_real_ip(request)
    ua = request.headers.get('User-Agent')
    geo = get_geolocation(ip)

    log = ScanLog(
        pack_id=pack.id,
        ip_address=ip,
        user_agent=ua,
        latitude=geo['lat'] if geo else None,
        longitude=geo['lon'] if geo else None,
        city=geo['city'] if geo else None,
        country=geo['country'] if geo else None,
        is_found_report=False
    )
    db.session.add(log)
    pack.scan_count += 1
    pack.last_scanned = datetime.utcnow()
    db.session.commit()

    show_sensitive = False
    if pack.pin_hash:
        pin_provided = request.args.get('pin')
        if pin_provided and pack.check_pin(pin_provided):
            show_sensitive = True
    else:
        show_sensitive = True

    return render_template('view.html', pack=pack, data=data, ui=ui, show_sensitive=show_sensitive)

@app.route('/api/report_found/<int:pack_id>', methods=['POST'])
def report_found(pack_id):
    pack = QRData.query.get_or_404(pack_id)
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'Invalid request'}), 400

    finder_name = data.get('name', 'Anonymous')
    finder_phone = data.get('phone', '')
    finder_email = data.get('email', '')
    finder_message = data.get('message', '')
    geo = data.get('geo')

    extra = {
        'finder_name': finder_name,
        'finder_phone': finder_phone,
        'finder_email': finder_email,
        'finder_message': finder_message,
        'ip': request.remote_addr,
        'user_agent': request.headers.get('User-Agent'),
    }
    if geo:
        extra['latitude'] = geo.get('lat')
        extra['longitude'] = geo.get('lon')

    notif = Notification(
        pack_id=pack.id,
        type='found_report',
        message=f"Found by {finder_name} (Phone: {finder_phone})",
        extra_data=json.dumps(extra)
    )
    db.session.add(notif)

    log = ScanLog(
        pack_id=pack.id,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent'),
        is_found_report=True,
        latitude=geo.get('lat') if geo else None,
        longitude=geo.get('lon') if geo else None,
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({'status': 'ok', 'message': 'Report sent to owner. Thank you!'})

@app.route('/api/request_contact/<int:pack_id>', methods=['POST'])
def request_contact(pack_id):
    pack = QRData.query.get_or_404(pack_id)
    answer = request.form.get('answer')
    if not pack.check_security_answer(answer):
        return jsonify({'status': 'error', 'message': 'Incorrect answer'}), 403
    data = pack.get_data()
    contact = {
        'name': data.get('contact_name'),
        'phone': data.get('contact_phone'),
        'email': data.get('contact_email')
    }
    notif = Notification(
        pack_id=pack.id,
        type='contact_request',
        message=f"Contact info requested and verified by {request.remote_addr}",
        extra_data=json.dumps(contact)
    )
    db.session.add(notif)
    db.session.commit()
    return jsonify({'status': 'ok', 'contact': contact})

@app.route('/api/log_geolocation/<int:pack_id>', methods=['POST'])
def log_geolocation(pack_id):
    pack = QRData.query.get_or_404(pack_id)
    data = request.get_json()
    lat = data.get('lat')
    lon = data.get('lon')
    if lat and lon:
        latest = ScanLog.query.filter_by(pack_id=pack.id, latitude=None).order_by(ScanLog.timestamp.desc()).first()
        if latest:
            latest.latitude = lat
            latest.longitude = lon
            db.session.commit()
    return jsonify({'status': 'ok'})

@app.route('/api/toggle_visibility/<int:pack_id>', methods=['POST'])
@login_required
def toggle_visibility(pack_id):
    pack = QRData.query.get_or_404(pack_id)
    if pack.user_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    pack.is_public = not pack.is_public
    db.session.commit()
    return jsonify({
        'status': 'ok',
        'is_public': pack.is_public,
        'message': 'Visibility updated'
    })

@app.route('/dashboard/<int:pack_id>')
def pack_dashboard(pack_id):
    secret = request.args.get('secret')
    if not secret:
        return "Secret key required", 401
    pack = QRData.query.get_or_404(pack_id)
    if pack.secret_key != secret:
        return "Invalid secret", 403
    logs = ScanLog.query.filter_by(pack_id=pack.id).order_by(ScanLog.timestamp.desc()).limit(50).all()
    notifs = Notification.query.filter_by(pack_id=pack.id).order_by(Notification.created_at.desc()).limit(20).all()
    for n in notifs:
        if n.extra_data:
            n.extra = json.loads(n.extra_data)
        else:
            n.extra = {}
    return render_template('pack_dashboard.html', pack=pack, logs=logs, notifs=notifs)

@app.route('/dashboard/<int:pack_id>/edit', methods=['GET', 'POST'])
def edit_pack(pack_id):
    secret = request.args.get('secret')
    if not secret:
        return "Secret key required", 401
    pack = QRData.query.get_or_404(pack_id)
    if pack.secret_key != secret:
        return "Invalid secret", 403

    if request.method == 'POST':
        data = pack.get_data()

        if pack.use_case == 'medical':
            data['patient_name'] = request.form.get('patient_name', data.get('patient_name'))
            data['patient_name'] = request.form.get('patient_name', data.get('patient_name'))
            new_dob = request.form.get('date_of_birth', data.get('date_of_birth'))
            data['date_of_birth'] = new_dob
            data['age'] = calculate_age(new_dob)
            data['blood_group'] = request.form.get('blood_group', data.get('blood_group'))
            data['allergy_penicillin'] = 'allergy_penicillin' in request.form
            data['allergy_sulfa'] = 'allergy_sulfa' in request.form
            data['allergy_nsaids'] = 'allergy_nsaids' in request.form
            data['allergy_shellfish'] = 'allergy_shellfish' in request.form
            data['allergy_latex'] = 'allergy_latex' in request.form
            data['allergy_other'] = request.form.get('allergy_other', data.get('allergy_other')) if 'allergy_other' in request.form else ''
            data['condition_heart_disease'] = 'condition_heart_disease' in request.form
            data['condition_hypertension'] = 'condition_hypertension' in request.form
            data['condition_diabetes'] = 'condition_diabetes' in request.form
            data['condition_asthma'] = 'condition_asthma' in request.form
            data['condition_copd'] = 'condition_copd' in request.form
            data['condition_kidney_disease'] = 'condition_kidney_disease' in request.form
            data['condition_liver_disease'] = 'condition_liver_disease' in request.form
            data['condition_stroke'] = 'condition_stroke' in request.form
            data['condition_cancer'] = 'condition_cancer' in request.form
            data['condition_thyroid'] = 'condition_thyroid' in request.form
            data['condition_epilepsy'] = 'condition_epilepsy' in request.form
            data['condition_hiv_aids'] = 'condition_hiv_aids' in request.form
            data['condition_tuberculosis'] = 'condition_tuberculosis' in request.form
            data['condition_mental_health'] = 'condition_mental_health' in request.form
            data['condition_other'] = request.form.get('condition_other', data.get('condition_other'))
            data['medications'] = request.form.get('medications', data.get('medications'))
            data['organ_donor'] = 'organ_donor' in request.form
            data['dnr'] = 'dnr' in request.form
            data['emergency_contact_name'] = request.form.get('emergency_contact_name', data.get('emergency_contact_name'))
            data['emergency_contact_relationship'] = request.form.get('emergency_contact_relationship', data.get('emergency_contact_relationship'))
            data['emergency_contact_phone'] = request.form.get('emergency_contact_phone', data.get('emergency_contact_phone'))
            data['primary_care_physician'] = request.form.get('primary_care_physician', data.get('primary_care_physician'))
            data['primary_care_physician_phone'] = request.form.get('primary_care_physician_phone', data.get('primary_care_physician_phone'))
            data['hospital_affiliation'] = request.form.get('hospital_affiliation', data.get('hospital_affiliation'))
            data['insurance_policy_number'] = request.form.get('insurance_policy_number', data.get('insurance_policy_number'))
            data['abha_id'] = request.form.get('abha_id', data.get('abha_id'))
            data['additional_notes'] = request.form.get('additional_notes', data.get('additional_notes'))

        elif pack.use_case == 'lost':
            data['item_name'] = request.form.get('item_name', data.get('item_name'))
            data['item_category'] = request.form.get('item_category', data.get('item_category'))
            data['brand'] = request.form.get('brand', data.get('brand'))
            data['model'] = request.form.get('model', data.get('model'))
            data['color'] = request.form.get('color', data.get('color'))
            data['unique_identifier'] = request.form.get('unique_identifier', data.get('unique_identifier'))
            data['description'] = request.form.get('description', data.get('description'))
            data['reward'] = request.form.get('reward', data.get('reward'))
            data['last_known_location'] = request.form.get('last_known_location', data.get('last_known_location'))
            data['date_lost'] = request.form.get('date_lost', data.get('date_lost'))
            data['contact_name'] = request.form.get('contact_name', data.get('contact_name'))
            data['contact_phone'] = request.form.get('contact_phone', data.get('contact_phone'))
            data['contact_email'] = request.form.get('contact_email', data.get('contact_email'))
            data['additional_notes'] = request.form.get('additional_notes', data.get('additional_notes'))
            proof = request.files.get('proof_file')
            if proof and allowed_file(proof.filename):
                fname = secure_filename(proof.filename)
                proof.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                data['proof_file'] = fname

        elif pack.use_case == 'vehicle':
            data['registration_number'] = request.form.get('registration_number', data.get('registration_number'))
            data['make'] = request.form.get('make', data.get('make'))
            data['model'] = request.form.get('model', data.get('model'))
            data['year'] = request.form.get('year', data.get('year'))
            data['color'] = request.form.get('color', data.get('color'))
            data['fuel_type'] = request.form.get('fuel_type', data.get('fuel_type'))
            data['transmission'] = request.form.get('transmission', data.get('transmission'))
            data['engine_number'] = request.form.get('engine_number', data.get('engine_number'))
            data['chassis_number'] = request.form.get('chassis_number', data.get('chassis_number'))
            data['owner_name'] = request.form.get('owner_name', data.get('owner_name'))
            data['owner_phone'] = request.form.get('owner_phone', data.get('owner_phone'))
            data['owner_email'] = request.form.get('owner_email', data.get('owner_email'))
            data['insurance_policy_number'] = request.form.get('insurance_policy_number', data.get('insurance_policy_number'))
            data['insurance_expiry_date'] = request.form.get('insurance_expiry_date', data.get('insurance_expiry_date'))
            data['rc_details'] = request.form.get('rc_details', data.get('rc_details'))
            data['tow_notes'] = request.form.get('tow_notes', data.get('tow_notes'))
            data['emergency_contact_name'] = request.form.get('emergency_contact_name', data.get('emergency_contact_name'))
            data['emergency_contact_phone'] = request.form.get('emergency_contact_phone', data.get('emergency_contact_phone'))
            data['additional_notes'] = request.form.get('additional_notes', data.get('additional_notes'))
            dl = request.files.get('dl_file')
            if dl and allowed_file(dl.filename):
                fname = secure_filename(dl.filename)
                dl.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                data['dl_file'] = fname
            ins = request.files.get('ins_file')
            if ins and allowed_file(ins.filename):
                fname = secure_filename(ins.filename)
                ins.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                data['ins_file'] = fname

        else:
            blocks = []
            block_types = request.form.getlist('block_type[]')
            block_contents = request.form.getlist('block_content[]')
            for btype, bcontent in zip(block_types, block_contents):
                if bcontent.strip():
                    blocks.append({'type': btype, 'content': bcontent.strip()})
            data['blocks'] = blocks

        if pack.use_case != 'medical':
            new_pin = request.form.get('pin')
            if new_pin:
                pack.set_pin(new_pin)
            else:
                pack.pin_hash = None

            new_security_question = request.form.get('security_question')
            new_security_answer = request.form.get('security_answer')
            if new_security_question and new_security_answer:
                pack.security_question = new_security_question
                pack.set_security_answer(new_security_answer)
            else:
                pack.security_question = None
                pack.security_answer_hash = None

        new_status = request.form.get('status')
        if new_status in ['active', 'stolen', 'recovered', 'inactive']:
            pack.status = new_status

        logo = request.files.get('logo')
        if logo and allowed_file(logo.filename):
            logo_filename = secure_filename(logo.filename)
            logo.save(os.path.join(app.config['UPLOAD_FOLDER'], logo_filename))
            pack.logo_path = logo_filename

        is_public = request.form.get('is_public') == 'on'
        pack.is_public = is_public

        pack.set_data(data)
        db.session.commit()
        flash('Pack updated successfully!', 'success')
        return redirect(url_for('pack_dashboard', pack_id=pack.id, secret=pack.secret_key))


    data = pack.get_data()
    ui = pack.get_ui()
    return render_template('edit.html', pack=pack, data=data, ui=ui)

@app.route('/dashboard/<int:pack_id>/delete', methods=['POST'])
def delete_pack(pack_id):
    secret = request.args.get('secret')
    if not secret:
        return "Secret required", 401
    pack = QRData.query.get_or_404(pack_id)
    if pack.secret_key != secret:
        return "Invalid secret", 403

    ScanLog.query.filter_by(pack_id=pack.id).delete()
    Notification.query.filter_by(pack_id=pack.id).delete()
    db.session.delete(pack)
    db.session.commit()
    flash('Pack deleted', 'info')
    return redirect(url_for('dashboard'))

@app.route('/static/qrcodes/<filename>')
def qr_image(filename):
    return send_from_directory(app.config['QR_FOLDER'], filename)

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host="0.0.0.0")
