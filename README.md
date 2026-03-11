# Asset Vault

A polished, self-hosted web application for tracking and managing household assets. Built with Flask and SQLite — runs locally or in Docker with zero cloud dependencies.

![Python](https://img.shields.io/badge/Python-3.9+-blue) ![Flask](https://img.shields.io/badge/Flask-3.x-green) ![SQLite](https://img.shields.io/badge/Database-SQLite-orange) ![Docker](https://img.shields.io/badge/Docker-ready-blue) ![Tests](https://img.shields.io/badge/Tests-21%20passing-brightgreen)

---

## Features

- **Full CRUD** — Add, view, edit, and delete assets with full field history
- **Rich Asset Fields** — Name, category, brand, model, serial number, condition, purchase price, purchase date, warranty expiration, location, tags, and notes
- **Photo Attachments** — Upload multiple photos per asset with primary photo selection
- **QR Code Labels** — Generate and download printable QR codes for any asset
- **Insurance Reports** — One-click PDF-ready insurance reports per asset or full inventory
- **Warranty Tracking** — Expiration alerts surfaced on the dashboard
- **Search & Filter** — Filter by name, category, location, condition, or value range
- **Bulk Import/Export** — CSV and JSON import with preview, export to CSV/JSON/PDF
- **Activity Log** — Full audit trail of every create/update/delete action
- **REST API** — JSON API for integrations and automation
- **Polished UI** — Linear/Stripe-inspired design system with dark mode support
- **Docker Ready** — One-command deployment
- **Secure by Default** — CSRF protection, parameterized queries, rate limiting, security headers

---

## Screenshots

| Dashboard                                          | Asset Detail                                  | Add Asset                                    |
| -------------------------------------------------- | --------------------------------------------- | -------------------------------------------- |
| Search, filter, summary stats, category breakdown  | Photos, QR code, quick actions, activity log  | Full form with brand, model, warranty, tags  |

---

## Quick Start

### Local (Python)

```bash
git clone https://github.com/DRAZY/asset-vault.git
cd asset-vault

pip install -r requirements.txt
python app.py
```

Open <http://localhost:9080>

> **macOS note:** Port 9080 is used by default because macOS reserves port 5000 for AirPlay Receiver.

### Docker Compose

```bash
docker-compose up -d
open http://localhost:9080
```

To use a different port:

```bash
PORT=3000 docker-compose up -d
```

---

## Deployment

### Docker Standalone

```bash
docker build -t asset-vault .

docker run -d \
  --name asset-vault \
  -p 9080:9080 \
  -v asset-data:/app/data \
  -e SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))") \
  asset-vault
```

### Production (Docker Compose)

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### VM / VPS (systemd)

```bash
sudo apt update && sudo apt install python3 python3-pip python3-venv

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run with gunicorn
gunicorn --bind 0.0.0.0:9080 --workers 2 app:app
```

**Systemd service** — create `/etc/systemd/system/asset-vault.service`:

```ini
[Unit]
Description=Asset Vault
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/asset-vault
Environment=PATH=/opt/asset-vault/venv/bin
Environment=SECRET_KEY=your-secret-key-here
ExecStart=/opt/asset-vault/venv/bin/gunicorn --bind 0.0.0.0:9080 --workers 2 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable asset-vault && sudo systemctl start asset-vault
```

---

## Configuration

Copy `.env.example` to `.env` and adjust:

```bash
cp .env.example .env
```

| Variable          | Default           | Description                                          |
| ----------------- | ----------------- | ---------------------------------------------------- |
| `PORT`            | `9080`            | HTTP port                                            |
| `HOST`            | `0.0.0.0`         | Bind address                                         |
| `DEBUG`           | `false`           | Enable Flask debug mode                              |
| `SECRET_KEY`      | auto-generated    | Session encryption key - **set this in production**  |
| `DATABASE_PATH`   | `./inventory.db`  | Path to SQLite database                              |
| `RATE_LIMIT`      | `100`             | Max requests per minute per IP                       |
| `HTTPS`           | `false`           | Set `true` if running behind an HTTPS proxy          |

---

## API Reference

| Method     | Endpoint            | Description               |
| ---------- | ------------------- | ------------------------- |
| `GET`      | `/api/assets`       | List all assets           |
| `GET`      | `/api/assets/<id>`  | Get single asset          |
| `POST`     | `/api/assets`       | Create asset              |
| `PUT`      | `/api/assets/<id>`  | Update asset              |
| `DELETE`   | `/api/assets/<id>`  | Delete asset              |
| `GET`      | `/api/summary`      | Inventory summary stats   |
| `GET`      | `/api/export`       | Export all assets as JSON |
| `GET`      | `/health`           | Health check              |

### Example

```bash
curl -X POST http://localhost:9080/api/assets \
  -H "Content-Type: application/json" \
  -d '{
    "item_name": "MacBook Pro",
    "category": "Electronics",
    "serial_number": "C02X1234",
    "estimated_value": 2499.99,
    "location": "Home Office",
    "condition": "Excellent",
    "brand": "Apple",
    "tags": "work,insured"
  }'
```

---

## Running Tests

```bash
python -m unittest tests/test_features.py -v
```

21 tests covering: dashboard, add, update, delete, asset detail, import (CSV + JSON), export (CSV + JSON), and error pages. Each test uses an isolated temp database — your `inventory.db` is never touched.

---

## Project Structure

```text
asset-vault/
├── app.py                      # Flask app, routes, forms
├── Dockerfile
├── docker-compose.yml
├── docker-compose.prod.yml
├── requirements.txt
├── .env.example
│
├── models/
│   └── asset.py                # Asset data model & validation
│
├── database/
│   └── db_manager.py           # SQLite manager (parameterized queries)
│
├── services/
│   └── asset_service.py        # Business logic, photo handling, QR codes
│
├── templates/
│   ├── base.html               # Design system, nav, dark mode
│   ├── index.html              # Dashboard
│   ├── asset_detail.html       # Asset view with photos & activity log
│   ├── add_edit.html           # Add / Edit form
│   ├── import.html             # Bulk import with preview
│   └── error.html              # 404 / 500 error pages
│
├── static/
│   └── uploads/                # Photo uploads (gitignored)
│
└── tests/
    └── test_features.py        # Feature test suite (21 tests)
```

---

## Security

- CSRF tokens on all forms (Flask-WTF)
- Parameterized SQL queries throughout
- Input validation with length limits
- Rate limiting (100 req/min per IP, configurable)
- Security headers: CSP, X-Frame-Options, X-Content-Type-Options
- Non-root Docker user
- `inventory.db` excluded from version control

---

## Backup & Restore

```bash
# Backup via API
curl http://localhost:9080/api/export > backup.json

# Backup database file (Docker)
docker cp asset-vault:/app/data/inventory.db ./backup.db

# Restore (Docker)
docker cp ./backup.db asset-vault:/app/data/inventory.db
docker restart asset-vault
```

---

## License

MIT — free to use and modify for personal or commercial use.
