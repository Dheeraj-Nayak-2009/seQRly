# seQRly – QR Codes That Save the Day

<p align="center">
<img width="364" alt="Screenshot_2026-08-22_222810-removebg-preview" src="https://github.com/user-attachments/assets/e685de6f-d1a4-4f08-ab79-f3dae372db57" />
</p>

> One QR, endless possibilities. Create smart QR codes for medical emergencies, lost items, vehicles, or custom content – all managed from a sleek, dark‑themed dashboard.
> 
<p align="center">
<img width="817" alt="Screenshot 2026-08-22 222535" src="https://github.com/user-attachments/assets/f5e47760-37ee-45db-95db-c63b97450108" />
</p>
---

## ✨ Features

- **Four QR types** – Medical (emergency ID), Lost & Found, Vehicle Data, and fully Custom.
- **User authentication** – Register, login, and manage all your QR packs from a personal dashboard.
- **Rich data forms** – Structured, interactive fields (checkboxes, dropdowns, date pickers) instead of plain textareas.
- **Pin & security questions** – Protect sensitive information (documents, contact details) – optional per use case.
- **Public / private toggle** – Each QR pack can be made private; only the owner can view it when logged in.
- **Live scan logging** – Every scan records IP, geolocation (city/country), and user agent.
- **Found reports & contact requests** – For Lost & Found items, finders can submit reports or answer a security question to reveal contact info.
- **macOS‑style public view** – Beautiful, responsive window that displays all data clearly.
- **Dark / light theme** – Respects system preference and allows manual toggle.
- **Logo upload** – Replace the QR code with your own logo on the public page.
- **File attachments** – Upload proof of ownership, driver’s licence, insurance documents, etc. (PIN‑protected for vehicles).

---

## 🛠️ Tech Stack

| Technology | Purpose |
|------------|---------|
| **Python 3.10+** | Backend language |
| **Flask** | Web framework |
| **Flask‑SQLAlchemy** | ORM for database |
| **Flask‑Login** | User session management |
| **SQLite** | Default database (can be swapped for PostgreSQL/MySQL) |
| **Werkzeug** | File upload handling |
| **qrcode** | QR code generation |
| **Requests** | IP geolocation (ip-api.com) |
| **Jinja2** | Templating with template inheritance |
| **Font Awesome** | Icons |
| **Google Fonts** (Inter & Playfair Display) | Typography |

---
