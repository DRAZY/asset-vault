# Home Asset Inventory

A secure, self-hosted web application for tracking and managing household assets. Built with Flask and SQLite, designed for Docker deployment.

## Features

- **Full CRUD Operations**: Add, view, edit, and delete assets
- **Search & Filter**: Find assets by name, category, location, or value range
- **Responsive Web UI**: Modern Bootstrap 5 interface works on desktop and mobile
- **REST API**: Full JSON API for integrations
- **Docker Ready**: One-command deployment with Docker Compose
- **Secure by Default**: CSRF protection, input sanitization, SQL injection prevention
- **Data Persistence**: SQLite database with backup functionality
- **Rate Limiting**: Built-in protection against abuse

## Quick Start

### Docker (Recommended)

```bash
# Clone or download the project
cd "Asset Inventory"

# Start with Docker Compose
docker-compose up -d

# Access the application
open http://localhost:8080
```

> **Note**: Default port is 8080 because macOS uses port 5000 for AirPlay Receiver.
> To use a different port: `PORT=3000 docker-compose up -d`

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py

# Access at http://localhost:5000
```

## Deployment Options

### 1. Docker Compose (Simplest)

```bash
# Development
docker-compose up

# Production (with restart policy)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### 2. Docker Standalone

```bash
# Build the image
docker build -t asset-inventory .

# Run the container
docker run -d \
  --name asset-inventory \
  -p 5000:5000 \
  -v asset-data:/app/data \
  -e SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))") \
  asset-inventory
```

### 3. VM Deployment

```bash
# On your VM (Ubuntu/Debian example)
sudo apt update
sudo apt install python3 python3-pip python3-venv

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run with gunicorn
gunicorn --bind 0.0.0.0:5000 --workers 2 app:app
```

### 4. Systemd Service (VM)

Create `/etc/systemd/system/asset-inventory.service`:

```ini
[Unit]
Description=Asset Inventory Web Application
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/asset-inventory
Environment=PATH=/opt/asset-inventory/venv/bin
Environment=SECRET_KEY=your-secret-key-here
ExecStart=/opt/asset-inventory/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 2 app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl enable asset-inventory
sudo systemctl start asset-inventory
sudo systemctl status asset-inventory
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 5000 | HTTP port |
| `HOST` | 0.0.0.0 | Bind address |
| `DEBUG` | false | Enable debug mode |
| `SECRET_KEY` | auto-generated | Session encryption key |
| `DATABASE_PATH` | ./inventory.db | SQLite database path |
| `RATE_LIMIT` | 100 | Requests per minute per IP |
| `HTTPS` | false | Set true if behind HTTPS proxy |

### Using .env File

```bash
cp .env.example .env
# Edit .env with your settings
```

## API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/assets` | List all assets |
| GET | `/api/assets/<id>` | Get single asset |
| POST | `/api/assets` | Create asset |
| PUT | `/api/assets/<id>` | Update asset |
| DELETE | `/api/assets/<id>` | Delete asset |
| GET | `/api/summary` | Get inventory summary |
| GET | `/api/export` | Export all assets as JSON |
| GET | `/health` | Health check endpoint |

### Example: Create Asset

```bash
curl -X POST http://localhost:5000/api/assets \
  -H "Content-Type: application/json" \
  -d '{
    "item_name": "MacBook Pro",
    "category": "Electronics",
    "serial_number": "C02X1234",
    "estimated_value": 2499.99,
    "location": "Home Office",
    "notes": "Work laptop"
  }'
```

## Security Features

- **CSRF Protection**: All forms protected with tokens
- **SQL Injection Prevention**: Parameterized queries only
- **XSS Prevention**: HTML escaping on all inputs
- **Input Validation**: Server-side validation with length limits
- **Rate Limiting**: Prevents brute force attacks
- **Security Headers**: CSP, X-Frame-Options, etc.
- **Non-root Container**: Runs as unprivileged user

## Backup & Restore

### Backup Database

```bash
# Docker
docker cp asset-inventory:/app/data/inventory.db ./backup.db

# Or via API
curl http://localhost:5000/api/export > backup.json
```

### Restore Database

```bash
# Docker
docker cp ./backup.db asset-inventory:/app/data/inventory.db
docker restart asset-inventory
```

## Project Structure

```
Asset Inventory/
├── app.py                    # Flask web application
├── Dockerfile                # Docker image definition
├── docker-compose.yml        # Docker Compose config
├── docker-compose.prod.yml   # Production overrides
├── requirements.txt          # Python dependencies
├── .env.example             # Example environment config
│
├── models/
│   └── asset.py             # Asset data model
│
├── database/
│   └── db_manager.py        # SQLite database manager
│
├── services/
│   └── asset_service.py     # Business logic layer
│
├── templates/
│   ├── base.html            # Base template
│   ├── index.html           # Home page
│   ├── add_edit.html        # Add/Edit form
│   └── error.html           # Error pages
│
├── home_asset_inventory.py      # CLI version
└── home_asset_inventory_gui.py  # Desktop GUI version
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs asset-inventory

# Verify health
curl http://localhost:5000/health
```

### Database locked

```bash
# Restart the container
docker-compose restart
```

### Permission denied

```bash
# Fix volume permissions
docker-compose down
docker volume rm asset-inventory_asset-data
docker-compose up -d
```

## License

MIT License - Feel free to use and modify for personal or commercial use.
