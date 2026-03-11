#!/usr/bin/env python3
"""
Feature tests for Asset Vault web application.

Tests cover the full CRUD lifecycle plus import functionality.
Each test class uses an isolated temp-file SQLite database so
production data (inventory.db) is never touched.
"""
import sys
import os
import json
import io
import tempfile
import unittest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as flask_app
from services.asset_service import AssetService


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def make_test_service():
    """Return an AssetService backed by a fresh temp-file SQLite database.
    The caller is responsible for cleanup (call cleanup_test_service)."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    return AssetService(path), path


def cleanup_test_service(db_path):
    """Remove the temp database file."""
    try:
        os.unlink(db_path)
    except OSError:
        pass


def _post_form(client, url, data, follow_redirects=True):
    """POST with WTF CSRF token injected via test client."""
    with client.application.test_request_context():
        from flask_wtf.csrf import generate_csrf
        token = generate_csrf()
    data['csrf_token'] = token
    return client.post(url, data=data, follow_redirects=follow_redirects)


def _add_asset(client, **overrides):
    """Helper to add a minimal valid asset; returns the response."""
    payload = {
        'item_name': 'Test TV',
        'category': 'Electronics',
        'estimated_value': '999.00',
        'location': 'Living Room',
        'condition': 'Good',
        'brand': '',
        'model_number': '',
        'serial_number': '',
        'purchase_price': '',
        'purchase_date': '',
        'warranty_expiration': '',
        'tags': '',
        'notes': '',
    }
    payload.update(overrides)
    return _post_form(client, '/add', payload)


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------

class TestDashboard(unittest.TestCase):
    def setUp(self):
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['WTF_CSRF_ENABLED'] = False
        flask_app.asset_service, self._db_path = make_test_service()
        self.client = flask_app.app.test_client()

    def tearDown(self):
        cleanup_test_service(self._db_path)

    def test_dashboard_loads(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Asset Vault', r.data)

    def test_dashboard_shows_empty_state(self):
        r = self.client.get('/')
        self.assertIn(b'0', r.data)  # $0 total value in summary


class TestAddAsset(unittest.TestCase):
    def setUp(self):
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['WTF_CSRF_ENABLED'] = False
        flask_app.asset_service, self._db_path = make_test_service()
        self.client = flask_app.app.test_client()

    def tearDown(self):
        cleanup_test_service(self._db_path)

    def test_add_page_loads(self):
        r = self.client.get('/add')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Add New Asset', r.data)

    def test_add_valid_asset(self):
        r = self.client.post('/add', data={
            'item_name': 'Samsung TV',
            'category': 'Electronics',
            'estimated_value': '1200.00',
            'location': 'Living Room',
            'condition': 'Excellent',
            'brand': 'Samsung',
            'model_number': 'QN65',
            'serial_number': 'SN123',
            'purchase_price': '1500.00',
            'purchase_date': '2023-01-15',
            'warranty_expiration': '2026-01-15',
            'tags': 'insured,high-value',
            'notes': 'Main TV in living room',
        }, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Samsung TV', r.data)

    def test_add_missing_required_fields_stays_on_form(self):
        r = self.client.post('/add', data={
            'item_name': '',
            'category': '',
            'estimated_value': '',
            'location': '',
            'condition': 'Good',
        }, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        # Should stay on add page (no redirect to detail)
        self.assertIn(b'Add New Asset', r.data)

    def test_add_negative_value_rejected(self):
        r = self.client.post('/add', data={
            'item_name': 'Bad Item',
            'category': 'Electronics',
            'estimated_value': '-100',
            'location': 'Garage',
            'condition': 'Good',
        }, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Add New Asset', r.data)


class TestUpdateAsset(unittest.TestCase):
    """Core regression: asset updates must persist."""

    def setUp(self):
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['WTF_CSRF_ENABLED'] = False
        flask_app.asset_service, self._db_path = make_test_service()
        self.client = flask_app.app.test_client()

        # Create one asset to edit
        success, _, self.asset_id = flask_app.asset_service.add_asset(
            item_name='Original Name',
            category='Furniture',
            serial_number='',
            estimated_value=500.0,
            location='Bedroom',
            condition='Good',
        )
        self.assertTrue(success, "Setup: failed to add test asset")

    def tearDown(self):
        cleanup_test_service(self._db_path)

    def test_edit_page_loads_with_existing_values(self):
        r = self.client.get(f'/edit/{self.asset_id}')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Original Name', r.data)

    def test_update_condition_persists(self):
        """Regression: changing condition from Good to Excellent must save."""
        r = self.client.post(f'/edit/{self.asset_id}', data={
            'item_name': 'Original Name',
            'category': 'Furniture',
            'estimated_value': '500.00',
            'location': 'Bedroom',
            'condition': 'Excellent',  # Changed
            'brand': '',
            'model_number': '',
            'serial_number': '',
            'purchase_price': '',
            'purchase_date': '',
            'warranty_expiration': '',
            'tags': '',
            'notes': '',
        }, follow_redirects=True)
        self.assertEqual(r.status_code, 200)

        updated = flask_app.asset_service.get_asset(self.asset_id)
        self.assertEqual(updated.condition, 'Excellent',
                         f"Condition not saved — got '{updated.condition}'")

    def test_update_value_persists(self):
        r = self.client.post(f'/edit/{self.asset_id}', data={
            'item_name': 'Original Name',
            'category': 'Furniture',
            'estimated_value': '750.00',
            'location': 'Bedroom',
            'condition': 'Good',
            'brand': '', 'model_number': '', 'serial_number': '',
            'purchase_price': '', 'purchase_date': '',
            'warranty_expiration': '', 'tags': '', 'notes': '',
        }, follow_redirects=True)
        self.assertEqual(r.status_code, 200)

        updated = flask_app.asset_service.get_asset(self.asset_id)
        self.assertAlmostEqual(updated.estimated_value, 750.0,
                               msg="Value not saved")

    def test_update_name_persists(self):
        r = self.client.post(f'/edit/{self.asset_id}', data={
            'item_name': 'Updated Sofa',
            'category': 'Furniture',
            'estimated_value': '500.00',
            'location': 'Living Room',
            'condition': 'Good',
            'brand': '', 'model_number': '', 'serial_number': '',
            'purchase_price': '', 'purchase_date': '',
            'warranty_expiration': '', 'tags': '', 'notes': '',
        }, follow_redirects=True)
        self.assertEqual(r.status_code, 200)

        updated = flask_app.asset_service.get_asset(self.asset_id)
        self.assertEqual(updated.item_name, 'Updated Sofa')

    def test_edit_nonexistent_asset_redirects(self):
        r = self.client.get('/edit/99999', follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Asset Vault', r.data)


class TestDeleteAsset(unittest.TestCase):
    def setUp(self):
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['WTF_CSRF_ENABLED'] = False
        flask_app.asset_service, self._db_path = make_test_service()
        self.client = flask_app.app.test_client()

        success, _, self.asset_id = flask_app.asset_service.add_asset(
            item_name='To Delete',
            category='Misc',
            serial_number='',
            estimated_value=10.0,
            location='Closet',
            condition='Fair',
        )
        self.assertTrue(success)

    def tearDown(self):
        cleanup_test_service(self._db_path)

    def test_delete_asset(self):
        r = self.client.post(f'/delete/{self.asset_id}',
                             follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(flask_app.asset_service.get_asset(self.asset_id),
                          "Asset should be gone after delete")


class TestAssetDetail(unittest.TestCase):
    def setUp(self):
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['WTF_CSRF_ENABLED'] = False
        flask_app.asset_service, self._db_path = make_test_service()
        self.client = flask_app.app.test_client()

        _, _, self.asset_id = flask_app.asset_service.add_asset(
            item_name='Detail Test Item',
            category='Books',
            serial_number='',
            estimated_value=25.0,
            location='Office',
            condition='New',
        )

    def tearDown(self):
        cleanup_test_service(self._db_path)

    def test_detail_page_loads(self):
        r = self.client.get(f'/asset/{self.asset_id}')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Detail Test Item', r.data)

    def test_detail_404_for_missing_asset(self):
        r = self.client.get('/asset/99999', follow_redirects=True)
        self.assertEqual(r.status_code, 200)  # redirect to index


class TestImport(unittest.TestCase):
    def setUp(self):
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['WTF_CSRF_ENABLED'] = False
        flask_app.asset_service, self._db_path = make_test_service()
        self.client = flask_app.app.test_client()

    def tearDown(self):
        cleanup_test_service(self._db_path)

    def test_import_page_loads(self):
        r = self.client.get('/import')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Import Assets', r.data)

    def test_import_csv_preview(self):
        csv_data = (
            'item_name,category,estimated_value,location\n'
            'Laptop,Electronics,1200,Office\n'
            'Chair,Furniture,300,Office\n'
        )
        data = {
            'action': 'preview',
            'file': (io.BytesIO(csv_data.encode()), 'test.csv'),
        }
        r = self.client.post('/import', data=data,
                             content_type='multipart/form-data',
                             follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Laptop', r.data)

    def test_import_json_preview(self):
        json_data = json.dumps({'assets': [
            {'item_name': 'Monitor', 'category': 'Electronics',
             'estimated_value': 400, 'location': 'Office'},
        ]})
        data = {
            'action': 'preview',
            'file': (io.BytesIO(json_data.encode()), 'test.json'),
        }
        r = self.client.post('/import', data=data,
                             content_type='multipart/form-data',
                             follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Monitor', r.data)

    def test_import_templates_download(self):
        r = self.client.get('/import/template/csv')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'item_name', r.data)

        r = self.client.get('/import/template/json')
        self.assertEqual(r.status_code, 200)
        payload = json.loads(r.data)
        self.assertIn('assets', payload)


class TestExport(unittest.TestCase):
    def setUp(self):
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['WTF_CSRF_ENABLED'] = False
        flask_app.asset_service, self._db_path = make_test_service()
        self.client = flask_app.app.test_client()
        flask_app.asset_service.add_asset(
            item_name='Export Item', category='Misc',
            serial_number='',
            estimated_value=50.0, location='Garage', condition='Good',
        )

    def tearDown(self):
        cleanup_test_service(self._db_path)

    def test_export_csv(self):
        r = self.client.get('/export/csv')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Item Name', r.data)
        self.assertIn(b'Export Item', r.data)

    def test_export_json(self):
        r = self.client.get('/export/json')
        self.assertEqual(r.status_code, 200)
        payload = json.loads(r.data)
        self.assertIn('assets', payload)
        names = [a['item_name'] for a in payload['assets']]
        self.assertIn('Export Item', names)


class TestErrorPages(unittest.TestCase):
    def setUp(self):
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['WTF_CSRF_ENABLED'] = False
        flask_app.asset_service, self._db_path = make_test_service()
        self.client = flask_app.app.test_client()

    def tearDown(self):
        cleanup_test_service(self._db_path)

    def test_404_page(self):
        r = self.client.get('/nonexistent-route-xyz')
        self.assertEqual(r.status_code, 404)


if __name__ == '__main__':
    unittest.main(verbosity=2)
