# seQRly – QR Codes That Save the Day
One QR, endless possibilities. Create smart QR codes for medical emergencies, lost items, vehicles, or custom content – all managed from a sleek, dark‑themed dashboard.

https://via.placeholder.com/1200x400/0d0d12/d4a373?text=seQRly

✨ Features
Four QR types – Medical (emergency ID), Lost & Found, Vehicle Data, and fully Custom.

User authentication – Register, login, and manage all your QR packs from a personal dashboard.

Rich data forms – Structured, interactive fields (checkboxes, dropdowns, date pickers) instead of plain textareas.

Pin & security questions – Protect sensitive information (documents, contact details) – optional per use case.

Public / private toggle – Each QR pack can be made private; only the owner can view it when logged in.

Live scan logging – Every scan records IP, geolocation (city/country), and user agent.

Found reports & contact requests – For Lost & Found items, finders can submit reports or answer a security question to reveal contact info.

macOS‑style public view – Beautiful, responsive window that displays all data clearly.

Dark / light theme – Respects system preference and allows manual toggle.

Logo upload – Replace the QR code with your own logo on the public page.

File attachments – Upload proof of ownership, driver’s licence, insurance documents, etc. (PIN‑protected for vehicles).

🛠️ Tech Stack
Technology	Purpose
Python 3.10+	Backend language
Flask	Web framework
Flask‑SQLAlchemy	ORM for database
Flask‑Login	User session management
SQLite	Default database (can be swapped for PostgreSQL/MySQL)
Werkzeug	File upload handling
qrcode	QR code generation
Requests	IP geolocation (ip-api.com)
Jinja2	Templating with template inheritance
Font Awesome	Icons
Google Fonts (Inter & Playfair Display)	Typography
📦 Installation
Clone the repository

bash
git clone https://github.com/yourusername/seqrly.git
cd seqrly
Create a virtual environment

bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
Install dependencies

bash
pip install -r requirements.txt
Set environment variables (optional)
Create a .env file in the root directory:

env
SECRET_KEY=your-super-secret-key
DATABASE_URL=sqlite:///seqrly.db   # or postgresql://user:pass@localhost/seqrly
Initialize the database

bash
flask shell
>>> from app import db
>>> db.create_all()
>>> exit()
Run the application

bash
python app.py
Visit http://127.0.0.1:5000 in your browser.

🚀 Usage
Creating a QR Pack
Log in (or sign up).

From the dashboard, click “New QR”.

Choose a use case (Medical, Lost, Vehicle, Custom).

Fill in the structured form.

Optionally set a PIN or security question.

Click “Generate QR”.

Download the QR code image or copy the public link.

Managing Packs
All your packs are listed on the dashboard.

Click “Manage” to view statistics, recent scans, and notifications.

Use the Edit button to update any field.

Toggle the Public/Private switch to control visibility.

Delete the pack permanently.

Public View
Anyone with the link can view the public page (unless it’s private).

For Lost & Found items, finders can answer the security question to reveal contact details, or use the “I found this!” button to send a report.

For Vehicle packs, documents are shown only after entering the correct PIN.

For Medical packs, emergency contacts and life‑saving info are displayed instantly.

🗄️ Database Schema
The core model is QRData, which stores all user‑submitted data as JSON in the data column. This allows flexible structure without altering the database for each use case.

python
class QRData(db.Model):
    id                 # Integer primary key
    user_id            # Foreign key to User
    use_case           # medical / lost / vehicle / custom
    status             # active / stolen / recovered / inactive
    secret_key         # Unique token for management
    data               # JSON – all structured fields
    ui                 # JSON – now empty (theme is global)
    security_question  # Optional
    security_answer_hash
    pin_hash
    logo_path
    created_at
    scan_count
    last_scanned
    is_public          # Boolean – default True
Related models: User, ScanLog, Notification.

📡 API Endpoints
Endpoint	Method	Description
/api/report_found/<pack_id>	POST	Submit a found report for a Lost & Found item
/api/request_contact/<pack_id>	POST	Verify security answer and return contact info
/api/log_geolocation/<pack_id>	POST	Update the latest scan with precise coordinates
/api/toggle_visibility/<pack_id>	POST	Toggle the public/private state (authenticated owner)
🎨 Customisation
Theme – Toggle is available in the navbar; system preference is used by default.

Logo – Upload a custom logo during creation to replace the QR code on the public page.

Fonts – The UI uses Inter and Playfair Display, but can be overridden in base.html.

🤝 Contributing
Contributions are welcome! Please follow these steps:

Fork the project.

Create a feature branch (git checkout -b feature/amazing-feature).

Commit your changes (git commit -m 'Add some amazing feature').

Push to the branch (git push origin feature/amazing-feature).

Open a Pull Request.

📄 License
This project is licensed under the MIT License – see the LICENSE file for details.

🙏 Acknowledgements
QRCode library

ip-api.com for free IP geolocation.

Font Awesome for icons.

Google Fonts for typefaces.

📸 Screenshots
<details> <summary>Click to expand</summary>
https://via.placeholder.com/800x500/0d0d12/d4a373?text=Landing+Page
https://via.placeholder.com/800x500/0d0d12/d4a373?text=Dashboard
https://via.placeholder.com/800x500/0d0d12/d4a373?text=Medical+Form
https://via.placeholder.com/800x500/0d0d12/d4a373?text=Public+View

</details>
💬 Support
If you encounter any issues, please open an issue or reach out to the maintainer.

Built with ☕ and clarity by the seQRly team.
