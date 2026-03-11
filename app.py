#!/usr/bin/env python3
"""
Home Asset Inventory - Flask Web Application

A polished, self-hosted web app for managing household assets.
Features: photo attachments, QR codes, insurance reports, warranty tracking,
activity logging, and a modern glass-morphism UI.
"""
import os
import sys
import secrets
import logging
from functools import wraps
from datetime import datetime

import csv
import io
import json

from flask import (
    Flask, render_template, request, jsonify, redirect,
    url_for, flash, session, abort, Response, make_response,
    send_from_directory
)
from flask_wtf import FlaskForm, CSRFProtect
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, FloatField, TextAreaField, SelectField, DateField
from wtforms.validators import DataRequired, Optional, NumberRange, Length
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.asset_service import AssetService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Security configuration
secret_key = os.environ.get('SECRET_KEY', '')
if not secret_key:
    secret_key = secrets.token_hex(32)
    logger.warning("No SECRET_KEY set - using auto-generated key")
app.config['SECRET_KEY'] = secret_key
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_TIME_LIMIT'] = 3600
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('HTTPS', 'false').lower() == 'true'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Upload configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'static', 'uploads', 'photos')
THUMBNAIL_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'static', 'uploads', 'thumbnails')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Handle proxy headers
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Initialize asset service
db_path = os.environ.get('DATABASE_PATH', None)
asset_service = AssetService(db_path, UPLOAD_FOLDER)

# Check for CSV migration on startup
if asset_service.has_pending_migration:
    logger.info("Migrating existing CSV data to database...")
    successful, failed = asset_service.migrate_from_csv()
    logger.info(f"Migration complete: {successful} imported, {failed} failed")


# =============================================================================
# Security Middleware
# =============================================================================

@app.after_request
def add_security_headers(response):
    """Add security headers to all responses."""
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; "
        "img-src 'self' data: blob:; "
        "frame-ancestors 'none';"
    )
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response


# Rate limiting
request_counts = {}
RATE_LIMIT = int(os.environ.get('RATE_LIMIT', 100))
RATE_WINDOW = 60


def rate_limit(f):
    """Simple rate limiting decorator."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.remote_addr
        now = datetime.now().timestamp()
        request_counts[client_ip] = [
            t for t in request_counts.get(client_ip, [])
            if now - t < RATE_WINDOW
        ]
        if len(request_counts.get(client_ip, [])) >= RATE_LIMIT:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            abort(429)
        request_counts.setdefault(client_ip, []).append(now)
        return f(*args, **kwargs)
    return decorated_function


# =============================================================================
# Forms
# =============================================================================

class AssetForm(FlaskForm):
    """Form for creating/editing assets with extended fields."""
    item_name = StringField('Item Name', validators=[
        DataRequired(message="Item name is required"),
        Length(min=1, max=200, message="Item name must be 1-200 characters")
    ])
    category = StringField('Category', validators=[
        DataRequired(message="Category is required"),
        Length(min=1, max=100, message="Category must be 1-100 characters")
    ])
    brand = StringField('Brand', validators=[
        Optional(), Length(max=100)
    ])
    model_number = StringField('Model Number', validators=[
        Optional(), Length(max=100)
    ])
    serial_number = StringField('Serial Number', validators=[
        Optional(), Length(max=100)
    ])
    estimated_value = FloatField('Estimated Value ($)', validators=[
        DataRequired(message="Estimated value is required"),
        NumberRange(min=0, max=999999999.99)
    ])
    purchase_price = FloatField('Purchase Price ($)', validators=[
        Optional(), NumberRange(min=0, max=999999999.99)
    ])
    purchase_date = StringField('Purchase Date', validators=[Optional()])
    warranty_expiration = StringField('Warranty Expiration', validators=[Optional()])
    condition = SelectField('Condition', choices=[
        ('New', 'New'), ('Excellent', 'Excellent'), ('Good', 'Good'),
        ('Fair', 'Fair'), ('Poor', 'Poor')
    ], default='Good')
    location = StringField('Location', validators=[
        DataRequired(message="Location is required"),
        Length(min=1, max=200)
    ])
    tags = StringField('Tags', validators=[Optional(), Length(max=500)])
    notes = TextAreaField('Notes', validators=[
        Optional(), Length(max=1000)
    ])


class ImportForm(FlaskForm):
    """Form for importing assets from file."""
    file = FileField('Import File', validators=[
        DataRequired(message="Please select a file to import"),
        FileAllowed(['csv', 'txt', 'json'], 'Only CSV, TXT, and JSON files are allowed')
    ])


# =============================================================================
# Routes - Pages
# =============================================================================

@app.route('/')
@rate_limit
def index():
    """Dashboard page."""
    assets = asset_service.get_all_assets()
    summary = asset_service.get_summary()
    categories = asset_service.get_categories()
    locations = asset_service.get_locations()

    return render_template(
        'index.html',
        assets=assets,
        summary=summary,
        categories=categories,
        locations=locations
    )


@app.route('/asset/<int:asset_id>')
@rate_limit
def asset_detail(asset_id):
    """Asset detail page with photos, QR code, and activity log."""
    asset = asset_service.get_asset(asset_id)
    if not asset:
        flash('Asset not found', 'error')
        return redirect(url_for('index'))

    activity = asset_service.get_activity_log(asset_id=asset_id, limit=20)
    return render_template(
        'asset_detail.html',
        asset=asset,
        activity=activity
    )


@app.route('/add', methods=['GET', 'POST'])
@rate_limit
def add_asset():
    """Add a new asset."""
    form = AssetForm()

    if form.validate_on_submit():
        purchase_price = form.purchase_price.data
        success, message, asset_id = asset_service.add_asset(
            item_name=form.item_name.data,
            category=form.category.data,
            serial_number=form.serial_number.data or '',
            estimated_value=form.estimated_value.data,
            location=form.location.data,
            notes=form.notes.data or '',
            purchase_price=purchase_price if purchase_price else None,
            purchase_date=form.purchase_date.data or None,
            warranty_expiration=form.warranty_expiration.data or None,
            condition=form.condition.data or 'Good',
            brand=form.brand.data or '',
            model_number=form.model_number.data or '',
            tags=form.tags.data or ''
        )

        if success:
            flash(message, 'success')
            logger.info(f"Asset added: {form.item_name.data} (ID: {asset_id})")
            return redirect(url_for('asset_detail', asset_id=asset_id))
        else:
            flash(message, 'error')

    categories = asset_service.get_categories()
    locations = asset_service.get_locations()
    return render_template('add_edit.html', form=form, title='Add New Asset',
                           categories=categories, locations=locations)


@app.route('/edit/<int:asset_id>', methods=['GET', 'POST'])
@rate_limit
def edit_asset(asset_id):
    """Edit an existing asset."""
    asset = asset_service.get_asset(asset_id)
    if not asset:
        flash('Asset not found', 'error')
        return redirect(url_for('index'))

    form = AssetForm()

    if form.validate_on_submit():
        purchase_price = form.purchase_price.data
        success, message = asset_service.update_asset(
            asset_id=asset_id,
            item_name=form.item_name.data,
            category=form.category.data,
            serial_number=form.serial_number.data or '',
            estimated_value=form.estimated_value.data,
            location=form.location.data,
            notes=form.notes.data or '',
            purchase_price=purchase_price if purchase_price else None,
            purchase_date=form.purchase_date.data or None,
            warranty_expiration=form.warranty_expiration.data or None,
            condition=form.condition.data or 'Good',
            brand=form.brand.data or '',
            model_number=form.model_number.data or '',
            tags=form.tags.data or ''
        )

        if success:
            flash(message, 'success')
            return redirect(url_for('asset_detail', asset_id=asset_id))
        else:
            flash(message, 'error')

    elif request.method == 'GET':
        form.item_name.data = asset.item_name
        form.category.data = asset.category
        form.serial_number.data = asset.serial_number
        form.estimated_value.data = asset.estimated_value
        form.location.data = asset.location
        form.notes.data = asset.notes
        form.purchase_price.data = asset.purchase_price
        form.purchase_date.data = asset.purchase_date or ''
        form.warranty_expiration.data = asset.warranty_expiration or ''
        form.condition.data = asset.condition
        form.brand.data = asset.brand
        form.model_number.data = asset.model_number
        form.tags.data = asset.tags

    categories = asset_service.get_categories()
    locations = asset_service.get_locations()
    return render_template(
        'add_edit.html', form=form,
        title=f'Edit: {asset.item_name}',
        asset=asset,
        categories=categories,
        locations=locations
    )


@app.route('/delete/<int:asset_id>', methods=['POST'])
@rate_limit
def delete_asset(asset_id):
    """Delete an asset."""
    success, message = asset_service.delete_asset(asset_id)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    return redirect(url_for('index'))


@app.route('/search')
@rate_limit
def search():
    """Search assets."""
    query = request.args.get('q', '')
    category = request.args.get('category', '')
    location = request.args.get('location', '')
    min_value = request.args.get('min_value', type=float)
    max_value = request.args.get('max_value', type=float)

    assets = asset_service.search_assets(
        query=query,
        category=category if category else None,
        location=location if location else None,
        min_value=min_value,
        max_value=max_value
    )

    summary = asset_service.get_summary()
    categories = asset_service.get_categories()
    locations = asset_service.get_locations()

    return render_template(
        'index.html',
        assets=assets,
        summary=summary,
        categories=categories,
        locations=locations,
        search_query=query,
        search_category=category,
        search_location=location
    )


# =============================================================================
# Routes - Photo Management
# =============================================================================

@app.route('/asset/<int:asset_id>/photos', methods=['POST'])
@rate_limit
def upload_photo(asset_id):
    """Upload a photo for an asset."""
    asset = asset_service.get_asset(asset_id)
    if not asset:
        flash('Asset not found', 'error')
        return redirect(url_for('index'))

    if 'photo' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('asset_detail', asset_id=asset_id))

    files = request.files.getlist('photo')
    success_count = 0

    for file in files:
        if file and file.filename:
            original_filename = secure_filename(file.filename)
            success, message, photo_id = asset_service.add_photo(
                asset_id, file, original_filename
            )
            if success:
                success_count += 1
            else:
                flash(message, 'error')

    if success_count > 0:
        flash(f'{success_count} photo(s) uploaded successfully', 'success')

    return redirect(url_for('asset_detail', asset_id=asset_id))


@app.route('/asset/<int:asset_id>/photos/<int:photo_id>/delete', methods=['POST'])
@rate_limit
def delete_photo(asset_id, photo_id):
    """Delete a photo."""
    success, message = asset_service.delete_photo(photo_id)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    return redirect(url_for('asset_detail', asset_id=asset_id))


@app.route('/asset/<int:asset_id>/photos/<int:photo_id>/primary', methods=['POST'])
@rate_limit
def set_primary_photo(asset_id, photo_id):
    """Set a photo as primary."""
    success, message = asset_service.set_primary_photo(asset_id, photo_id)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    return redirect(url_for('asset_detail', asset_id=asset_id))


@app.route('/uploads/photos/<filename>')
def uploaded_photo(filename):
    """Serve uploaded photos."""
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route('/uploads/thumbnails/<filename>')
def uploaded_thumbnail(filename):
    """Serve photo thumbnails."""
    return send_from_directory(THUMBNAIL_FOLDER, filename)


# =============================================================================
# Routes - QR Code
# =============================================================================

@app.route('/asset/<int:asset_id>/qr')
@rate_limit
def asset_qr_code(asset_id):
    """Generate QR code for an asset."""
    base_url = request.host_url.rstrip('/')
    qr_data = asset_service.generate_qr_code(asset_id, base_url)
    if qr_data:
        return Response(qr_data, mimetype='image/png',
                        headers={'Content-Disposition': f'inline; filename=asset_{asset_id}_qr.png'})
    abort(404)


# =============================================================================
# Routes - Insurance Report
# =============================================================================

@app.route('/insurance-report')
@rate_limit
def insurance_report():
    """Generate insurance report PDF for all assets."""
    pdf_data = asset_service.generate_insurance_report()
    if pdf_data:
        return Response(
            pdf_data, mimetype='application/pdf',
            headers={
                'Content-Disposition':
                    f'attachment; filename=insurance_report_{datetime.now().strftime("%Y%m%d")}.pdf'
            }
        )
    flash('Failed to generate insurance report', 'error')
    return redirect(url_for('index'))


@app.route('/asset/<int:asset_id>/insurance-report')
@rate_limit
def asset_insurance_report(asset_id):
    """Generate insurance report for a single asset."""
    pdf_data = asset_service.generate_insurance_report(asset_ids=[asset_id])
    if pdf_data:
        return Response(
            pdf_data, mimetype='application/pdf',
            headers={
                'Content-Disposition':
                    f'attachment; filename=asset_{asset_id}_insurance_{datetime.now().strftime("%Y%m%d")}.pdf'
            }
        )
    flash('Failed to generate report', 'error')
    return redirect(url_for('asset_detail', asset_id=asset_id))


# =============================================================================
# Routes - Import
# =============================================================================

def parse_json_import(file_content):
    """Parse JSON import file content."""
    assets = []
    errors = []
    try:
        data = json.loads(file_content)
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get('assets', data.get('data', []))
            if not isinstance(items, list):
                return [], ["JSON must contain an array of assets"]
        else:
            return [], ["Invalid JSON format"]

        for idx, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                errors.append(f"Item {idx}: Not a valid object")
                continue

            normalized = {}
            for key, value in item.items():
                k = key.lower().strip().replace(' ', '_')
                if k in ['item_name', 'name', 'item', 'asset_name', 'asset']:
                    normalized['item_name'] = str(value).strip() if value else ''
                elif k in ['category', 'cat', 'type']:
                    normalized['category'] = str(value).strip() if value else ''
                elif k in ['serial_number', 'serial', 'sn', 'serial_no']:
                    normalized['serial_number'] = str(value).strip() if value else ''
                elif k in ['estimated_value', 'value', 'price', 'cost', 'amount']:
                    normalized['estimated_value'] = value
                elif k in ['location', 'loc', 'room', 'place']:
                    normalized['location'] = str(value).strip() if value else ''
                elif k in ['notes', 'note', 'description', 'comments', 'comment']:
                    normalized['notes'] = str(value).strip() if value else ''
                elif k in ['brand']:
                    normalized['brand'] = str(value).strip() if value else ''
                elif k in ['model', 'model_number']:
                    normalized['model_number'] = str(value).strip() if value else ''
                elif k in ['condition']:
                    normalized['condition'] = str(value).strip() if value else 'Good'
                elif k in ['purchase_price']:
                    normalized['purchase_price'] = value
                elif k in ['purchase_date']:
                    normalized['purchase_date'] = str(value).strip() if value else ''
                elif k in ['warranty', 'warranty_expiration']:
                    normalized['warranty_expiration'] = str(value).strip() if value else ''
                elif k in ['tags', 'tag']:
                    normalized['tags'] = str(value).strip() if value else ''

            item_name = normalized.get('item_name', '')
            category = normalized.get('category', '')
            location = normalized.get('location', '')
            if not item_name:
                errors.append(f"Item {idx}: Missing item name")
                continue
            if not category:
                errors.append(f"Item {idx}: Missing category")
                continue
            if not location:
                errors.append(f"Item {idx}: Missing location")
                continue

            value_raw = normalized.get('estimated_value', 0)
            try:
                if isinstance(value_raw, (int, float)):
                    estimated_value = float(value_raw)
                else:
                    value_str = str(value_raw).replace('$', '').replace(',', '').strip()
                    estimated_value = float(value_str) if value_str else 0.0
            except (ValueError, TypeError):
                errors.append(f"Item {idx}: Invalid value '{value_raw}'")
                continue

            purchase_price_raw = normalized.get('purchase_price')
            purchase_price = None
            if purchase_price_raw is not None:
                try:
                    purchase_price = float(str(purchase_price_raw).replace('$', '').replace(',', ''))
                except (ValueError, TypeError):
                    pass

            assets.append({
                'item_name': item_name,
                'category': category,
                'serial_number': normalized.get('serial_number', ''),
                'estimated_value': estimated_value,
                'location': location,
                'notes': normalized.get('notes', ''),
                'brand': normalized.get('brand', ''),
                'model_number': normalized.get('model_number', ''),
                'condition': normalized.get('condition', 'Good'),
                'purchase_price': purchase_price,
                'purchase_date': normalized.get('purchase_date', ''),
                'warranty_expiration': normalized.get('warranty_expiration', ''),
                'tags': normalized.get('tags', ''),
            })

    except json.JSONDecodeError as e:
        return [], [f"Invalid JSON: {str(e)}"]
    except Exception as e:
        return [], [f"Error parsing JSON: {str(e)}"]

    return assets, errors


def parse_import_file(file_content, filename):
    """Parse imported file content supporting JSON, CSV, and text formats."""
    if isinstance(file_content, bytes):
        try:
            file_content = file_content.decode('utf-8')
        except UnicodeDecodeError:
            try:
                file_content = file_content.decode('latin-1')
            except Exception:
                return [], ["Unable to decode file."]

    if filename.lower().endswith('.json') or file_content.strip().startswith(('[', '{')):
        return parse_json_import(file_content)

    assets = []
    errors = []
    lines = file_content.strip().split('\n')
    if not lines:
        return [], ["File is empty"]

    first_line = lines[0].strip().lower()
    is_csv_with_headers = any(h in first_line for h in ['item_name', 'item name', 'name', 'category'])

    if '\t' in lines[0]:
        delimiter = '\t'
    else:
        delimiter = ','

    if is_csv_with_headers:
        reader = csv.DictReader(io.StringIO(file_content), delimiter=delimiter)
        if reader.fieldnames:
            normalized_headers = {}
            for h in reader.fieldnames:
                hl = h.lower().strip().replace(' ', '_')
                if hl in ['item_name', 'name', 'item', 'asset_name', 'asset']:
                    normalized_headers[h] = 'item_name'
                elif hl in ['category', 'cat', 'type']:
                    normalized_headers[h] = 'category'
                elif hl in ['serial_number', 'serial', 'sn']:
                    normalized_headers[h] = 'serial_number'
                elif hl in ['estimated_value', 'value', 'price', 'cost', 'amount']:
                    normalized_headers[h] = 'estimated_value'
                elif hl in ['location', 'loc', 'room', 'place']:
                    normalized_headers[h] = 'location'
                elif hl in ['notes', 'note', 'description']:
                    normalized_headers[h] = 'notes'
                elif hl in ['brand']:
                    normalized_headers[h] = 'brand'
                elif hl in ['model', 'model_number']:
                    normalized_headers[h] = 'model_number'
                elif hl in ['condition']:
                    normalized_headers[h] = 'condition'
                elif hl in ['tags', 'tag']:
                    normalized_headers[h] = 'tags'

        for row_num, row in enumerate(reader, start=2):
            try:
                nr = {}
                for orig_key, value in row.items():
                    if orig_key in normalized_headers:
                        nr[normalized_headers[orig_key]] = value
                    else:
                        nr[orig_key.lower().strip().replace(' ', '_')] = value

                item_name = nr.get('item_name', '').strip()
                category = nr.get('category', '').strip()
                location = nr.get('location', '').strip()
                if not item_name:
                    errors.append(f"Row {row_num}: Missing item name")
                    continue
                if not category:
                    errors.append(f"Row {row_num}: Missing category")
                    continue
                if not location:
                    errors.append(f"Row {row_num}: Missing location")
                    continue

                value_str = nr.get('estimated_value', '0').strip()
                value_str = value_str.replace('$', '').replace(',', '').strip()
                try:
                    estimated_value = float(value_str) if value_str else 0.0
                except ValueError:
                    errors.append(f"Row {row_num}: Invalid value '{value_str}'")
                    continue

                assets.append({
                    'item_name': item_name,
                    'category': category,
                    'serial_number': nr.get('serial_number', '').strip(),
                    'estimated_value': estimated_value,
                    'location': location,
                    'notes': nr.get('notes', '').strip(),
                    'brand': nr.get('brand', '').strip(),
                    'model_number': nr.get('model_number', '').strip(),
                    'condition': nr.get('condition', 'Good').strip(),
                    'tags': nr.get('tags', '').strip(),
                })
            except Exception as e:
                errors.append(f"Row {row_num}: Error parsing - {str(e)}")
    else:
        for row_num, line in enumerate(lines, start=1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                parts = [p.strip() for p in line.split(delimiter)]
                if len(parts) < 4:
                    errors.append(f"Row {row_num}: Not enough fields")
                    continue

                item_name = parts[0]
                category = parts[1]
                value_str = parts[2].replace('$', '').replace(',', '').strip()
                location = parts[3]
                serial_number = parts[4] if len(parts) > 4 else ''
                notes = parts[5] if len(parts) > 5 else ''

                if not item_name or not category or not location:
                    errors.append(f"Row {row_num}: Missing required field")
                    continue

                estimated_value = float(value_str) if value_str else 0.0

                assets.append({
                    'item_name': item_name,
                    'category': category,
                    'serial_number': serial_number,
                    'estimated_value': estimated_value,
                    'location': location,
                    'notes': notes,
                })
            except Exception as e:
                errors.append(f"Row {row_num}: Error parsing - {str(e)}")

    return assets, errors


@app.route('/import', methods=['GET', 'POST'])
@rate_limit
def import_assets():
    """Import assets from CSV or text file."""
    form = ImportForm()
    preview_data = None
    import_errors = []

    if form.validate_on_submit():
        file = form.file.data
        filename = secure_filename(file.filename)

        try:
            file_content = file.read()
            action = request.form.get('action', 'preview')
            assets, errors = parse_import_file(file_content, filename)
            import_errors = errors

            if action == 'preview':
                preview_data = {
                    'filename': filename,
                    'assets': assets[:50],
                    'total_count': len(assets),
                    'total_value': sum(a['estimated_value'] for a in assets),
                    'errors': errors[:20]
                }
                session['import_data'] = assets
                session['import_filename'] = filename

            elif action == 'import':
                assets = session.get('import_data', [])
                if not assets:
                    flash('No import data found. Please upload the file again.', 'error')
                    return redirect(url_for('import_assets'))

                success_count = 0
                fail_count = 0
                for asset_data in assets:
                    success, message, asset_id = asset_service.add_asset(
                        item_name=asset_data['item_name'],
                        category=asset_data['category'],
                        serial_number=asset_data.get('serial_number', ''),
                        estimated_value=asset_data['estimated_value'],
                        location=asset_data['location'],
                        notes=asset_data.get('notes', ''),
                        brand=asset_data.get('brand', ''),
                        model_number=asset_data.get('model_number', ''),
                        condition=asset_data.get('condition', 'Good'),
                        tags=asset_data.get('tags', ''),
                    )
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1
                        import_errors.append(f"{asset_data['item_name']}: {message}")

                session.pop('import_data', None)
                session.pop('import_filename', None)

                if success_count > 0:
                    flash(f'Successfully imported {success_count} asset(s).', 'success')
                if fail_count > 0:
                    flash(f'Failed to import {fail_count} asset(s).', 'error')
                return redirect(url_for('index'))

        except Exception as e:
            logger.error(f"Import error: {e}")
            flash(f'Error processing file: {str(e)}', 'error')

    return render_template('import.html', form=form, preview=preview_data,
                           errors=import_errors)


@app.route('/import/template')
@app.route('/import/template/csv')
@rate_limit
def import_template():
    """Download a CSV template for importing assets."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'item_name', 'category', 'serial_number', 'estimated_value',
        'location', 'notes', 'brand', 'model_number', 'condition', 'tags'
    ])
    writer.writerow([
        'Samsung 65" Smart TV', 'Electronics', 'SN123456789', '999.99',
        'Living Room', 'Purchased 2024', 'Samsung', 'QN65Q80C', 'Excellent',
        'insured,high-value'
    ])
    writer.writerow([
        'Leather Sofa', 'Furniture', '', '1500.00',
        'Living Room', 'Brown, 3-seater', 'West Elm', 'Haven', 'Good', ''
    ])
    writer.writerow([
        'MacBook Pro 14"', 'Electronics', 'C02XYZ123', '2499.00',
        'Office', 'M3 Pro chip', 'Apple', 'MacBook Pro 14', 'Excellent',
        'insured,work'
    ])
    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=asset_import_template.csv'})


@app.route('/import/template/json')
@rate_limit
def import_template_json():
    """Download a JSON template for importing assets."""
    template_data = {
        "assets": [
            {
                "item_name": "Samsung 65\" Smart TV",
                "category": "Electronics",
                "serial_number": "SN123456789",
                "estimated_value": 999.99,
                "location": "Living Room",
                "notes": "Purchased 2024",
                "brand": "Samsung",
                "model_number": "QN65Q80C",
                "condition": "Excellent",
                "tags": "insured,high-value"
            },
            {
                "item_name": "Leather Sofa",
                "category": "Furniture",
                "estimated_value": 1500.00,
                "location": "Living Room",
                "brand": "West Elm",
                "condition": "Good"
            }
        ]
    }
    return Response(json.dumps(template_data, indent=2), mimetype='application/json',
                    headers={'Content-Disposition': 'attachment; filename=asset_import_template.json'})


# =============================================================================
# Routes - API (JSON)
# =============================================================================

@app.route('/api/assets', methods=['GET'])
@rate_limit
def api_get_assets():
    assets = asset_service.get_all_assets()
    return jsonify({'success': True, 'data': [a.to_dict() for a in assets], 'count': len(assets)})


@app.route('/api/assets/<int:asset_id>', methods=['GET'])
@rate_limit
def api_get_asset(asset_id):
    asset = asset_service.get_asset(asset_id)
    if not asset:
        return jsonify({'success': False, 'error': 'Asset not found'}), 404
    return jsonify({'success': True, 'data': asset.to_dict()})


@app.route('/api/assets', methods=['POST'])
@rate_limit
@csrf.exempt
def api_create_asset():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    purchase_price = data.get('purchase_price')
    success, message, asset_id = asset_service.add_asset(
        item_name=data.get('item_name', ''),
        category=data.get('category', ''),
        serial_number=data.get('serial_number', ''),
        estimated_value=float(data.get('estimated_value', 0)),
        location=data.get('location', ''),
        notes=data.get('notes', ''),
        purchase_price=float(purchase_price) if purchase_price is not None else None,
        purchase_date=data.get('purchase_date'),
        warranty_expiration=data.get('warranty_expiration'),
        condition=data.get('condition', 'Good'),
        brand=data.get('brand', ''),
        model_number=data.get('model_number', ''),
        tags=data.get('tags', '')
    )
    if success:
        return jsonify({'success': True, 'message': message, 'id': asset_id}), 201
    return jsonify({'success': False, 'error': message}), 400


@app.route('/api/assets/<int:asset_id>', methods=['PUT'])
@rate_limit
@csrf.exempt
def api_update_asset(asset_id):
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    purchase_price = data.get('purchase_price')
    success, message = asset_service.update_asset(
        asset_id=asset_id,
        item_name=data.get('item_name', ''),
        category=data.get('category', ''),
        serial_number=data.get('serial_number', ''),
        estimated_value=float(data.get('estimated_value', 0)),
        location=data.get('location', ''),
        notes=data.get('notes', ''),
        purchase_price=float(purchase_price) if purchase_price is not None else None,
        purchase_date=data.get('purchase_date'),
        warranty_expiration=data.get('warranty_expiration'),
        condition=data.get('condition', 'Good'),
        brand=data.get('brand', ''),
        model_number=data.get('model_number', ''),
        tags=data.get('tags', '')
    )
    if success:
        return jsonify({'success': True, 'message': message})
    return jsonify({'success': False, 'error': message}), 400


@app.route('/api/assets/<int:asset_id>', methods=['DELETE'])
@rate_limit
@csrf.exempt
def api_delete_asset(asset_id):
    success, message = asset_service.delete_asset(asset_id)
    if success:
        return jsonify({'success': True, 'message': message})
    return jsonify({'success': False, 'error': message}), 404


@app.route('/api/summary', methods=['GET'])
@rate_limit
def api_summary():
    summary = asset_service.get_summary()
    return jsonify({'success': True, 'data': summary})


@app.route('/api/export', methods=['GET'])
@rate_limit
def api_export():
    assets = asset_service.get_all_assets()
    return jsonify({
        'success': True,
        'exported_at': datetime.now().isoformat(),
        'count': len(assets),
        'assets': [a.to_dict() for a in assets]
    })


# =============================================================================
# Export Routes
# =============================================================================

@app.route('/export/json')
@rate_limit
def export_json():
    assets = asset_service.get_all_assets()
    summary = asset_service.get_summary()
    export_data = {
        'export_info': {
            'exported_at': datetime.now().isoformat(),
            'total_items': summary['total_items'],
            'total_value': summary['total_value']
        },
        'assets': [a.to_dict() for a in assets]
    }
    response = make_response(jsonify(export_data))
    response.headers['Content-Disposition'] = \
        f'attachment; filename=asset_inventory_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    response.headers['Content-Type'] = 'application/json'
    return response


@app.route('/export/csv')
@rate_limit
def export_csv():
    assets = asset_service.get_all_assets()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'ID', 'Item Name', 'Category', 'Brand', 'Model', 'Serial Number',
        'Estimated Value', 'Purchase Price', 'Purchase Date',
        'Warranty Expiration', 'Condition', 'Location', 'Tags',
        'Notes', 'Created At', 'Updated At'
    ])
    for asset in assets:
        writer.writerow([
            asset.id, asset.item_name, asset.category,
            asset.brand or '', asset.model_number or '',
            asset.serial_number or '',
            f'{asset.estimated_value:.2f}',
            f'{asset.purchase_price:.2f}' if asset.purchase_price else '',
            asset.purchase_date or '', asset.warranty_expiration or '',
            asset.condition, asset.location, asset.tags or '',
            asset.notes or '',
            asset.created_at.strftime('%Y-%m-%d %H:%M:%S') if asset.created_at else '',
            asset.updated_at.strftime('%Y-%m-%d %H:%M:%S') if asset.updated_at else ''
        ])
    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition':
                             f'attachment; filename=asset_inventory_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'})


@app.route('/export/pdf')
@rate_limit
def export_pdf():
    """Export assets as downloadable PDF file."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    except ImportError:
        flash('PDF export requires reportlab library', 'error')
        return redirect(url_for('index'))

    assets = asset_service.get_all_assets()
    summary = asset_service.get_summary()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                            rightMargin=0.5*inch, leftMargin=0.5*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'],
                                 fontSize=18, spaceAfter=12, alignment=1)
    elements.append(Paragraph('Home Asset Inventory Report', title_style))

    summary_style = ParagraphStyle('Summary', parent=styles['Normal'],
                                   fontSize=10, spaceAfter=6, alignment=1)
    elements.append(Paragraph(
        f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | '
        f'Total Items: {summary["total_items"]} | '
        f'Total Value: ${summary["total_value"]:,.2f}',
        summary_style
    ))
    elements.append(Spacer(1, 0.25*inch))

    if assets:
        table_data = [['Item Name', 'Category', 'Brand', 'Serial Number',
                       'Value', 'Condition', 'Location']]
        for asset in assets:
            table_data.append([
                asset.item_name[:30], asset.category[:20],
                (asset.brand or 'N/A')[:15],
                (asset.serial_number or 'N/A')[:20],
                f'${asset.estimated_value:,.2f}',
                asset.condition[:10], asset.location[:20],
            ])

        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6366f1')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f5f9')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('ALIGN', (4, 0), (4, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph('No assets in inventory.', styles['Normal']))

    doc.build(elements)
    buffer.seek(0)
    return Response(buffer.getvalue(), mimetype='application/pdf',
                    headers={'Content-Disposition':
                             f'attachment; filename=asset_inventory_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'})


# =============================================================================
# Error Handlers
# =============================================================================

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Not found'}), 404
    return render_template('error.html', error='Page not found', code=404), 404


@app.errorhandler(413)
def file_too_large(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'File too large (max 16MB)'}), 413
    flash('File too large. Maximum size is 16MB.', 'error')
    return redirect(request.referrer or url_for('index'))


@app.errorhandler(429)
def rate_limited(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Rate limit exceeded'}), 429
    return render_template('error.html', error='Too many requests', code=429), 429


@app.errorhandler(500)
def server_error(e):
    logger.error(f"Server error: {e}")
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
    return render_template('error.html', error='Internal server error', code=500), 500


# =============================================================================
# Health Check
# =============================================================================

@app.route('/health')
def health_check():
    try:
        asset_service.get_summary()
        return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500


# =============================================================================
# Main
# =============================================================================

if __name__ == '__main__':
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 9080))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    logger.info(f"Starting Asset Inventory on {host}:{port}")
    app.run(host=host, port=port, debug=debug)
