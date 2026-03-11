"""
Asset Service - Business logic layer for asset management.

Provides a clean API with validation, error handling, photo management,
activity logging, and QR code generation.
"""
import os
import uuid
import logging
from typing import List, Optional, Tuple
from pathlib import Path

from models.asset import Asset, AssetPhoto, ActivityLogEntry
from database.db_manager import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AssetService:
    """Business logic layer for asset management."""

    def __init__(self, db_path: str = None, upload_folder: str = None):
        self.db = DatabaseManager(db_path)
        self._check_for_csv_migration()

        if upload_folder is None:
            base_dir = Path(__file__).parent.parent
            upload_folder = str(base_dir / "static" / "uploads" / "photos")
        self.upload_folder = upload_folder
        self.thumbnail_folder = str(Path(upload_folder).parent / "thumbnails")

        os.makedirs(self.upload_folder, exist_ok=True)
        os.makedirs(self.thumbnail_folder, exist_ok=True)

    def _check_for_csv_migration(self):
        """Check for existing CSV data and offer migration."""
        base_dir = Path(__file__).parent.parent
        csv_path = base_dir / "assets.csv"

        if csv_path.exists():
            assets = self.db.get_all_assets()
            if not assets:
                logger.info("Found assets.csv - checking for migration")
                self._migration_pending = True
                self._csv_path = str(csv_path)
            else:
                self._migration_pending = False
        else:
            self._migration_pending = False

    @property
    def has_pending_migration(self) -> bool:
        return getattr(self, '_migration_pending', False)

    def migrate_from_csv(self) -> Tuple[int, int]:
        if not self.has_pending_migration:
            return 0, 0
        csv_path = getattr(self, '_csv_path', None)
        if csv_path:
            result = self.db.import_from_csv(csv_path)
            self._migration_pending = False
            return result
        return 0, 0

    # =========================================================================
    # Asset CRUD
    # =========================================================================

    def add_asset(self, item_name: str, category: str, serial_number: str,
                  estimated_value: float, location: str, notes: str = "",
                  purchase_price: float = None, purchase_date: str = None,
                  warranty_expiration: str = None, condition: str = "Good",
                  brand: str = "", model_number: str = "",
                  tags: str = "") -> Tuple[bool, str, Optional[int]]:
        """Add a new asset to the inventory."""
        try:
            asset = Asset(
                item_name=item_name, category=category,
                serial_number=serial_number, estimated_value=estimated_value,
                location=location, notes=notes,
                purchase_price=purchase_price, purchase_date=purchase_date,
                warranty_expiration=warranty_expiration, condition=condition,
                brand=brand, model_number=model_number, tags=tags
            )

            is_valid, error_msg = asset.validate()
            if not is_valid:
                return False, error_msg, None

            asset_id = self.db.add_asset(
                item_name=asset.item_name, category=asset.category,
                serial_number=asset.serial_number,
                estimated_value=asset.estimated_value,
                location=asset.location, notes=asset.notes,
                purchase_price=asset.purchase_price,
                purchase_date=asset.purchase_date,
                warranty_expiration=asset.warranty_expiration,
                condition=asset.condition, brand=asset.brand,
                model_number=asset.model_number, tags=asset.tags
            )

            self.db.log_activity(asset_id, "created",
                                 f"Added '{item_name}' to inventory")
            return True, f"Successfully added '{item_name}'", asset_id

        except ValueError as e:
            return False, str(e), None
        except Exception as e:
            logger.error(f"Error adding asset: {e}")
            return False, f"Database error: {str(e)}", None

    def get_asset(self, asset_id: int) -> Optional[Asset]:
        """Get a single asset by ID with photos."""
        data = self.db.get_asset(asset_id)
        if data:
            asset = Asset.from_dict(data)
            # Load photos
            photos_data = self.db.get_photos(asset_id)
            asset.photos = [
                AssetPhoto(
                    id=p['id'], asset_id=p['asset_id'],
                    filename=p['filename'],
                    original_filename=p['original_filename'],
                    is_primary=bool(p['is_primary']),
                    created_at=p['created_at']
                )
                for p in photos_data
            ]
            return asset
        return None

    def get_all_assets(self, order_by: str = "created_at",
                       descending: bool = True) -> List[Asset]:
        """Get all assets from the inventory."""
        assets_data = self.db.get_all_assets(order_by, descending)
        assets = []
        for data in assets_data:
            asset = Asset.from_dict(data)
            # Load primary photo only for list views
            photos = self.db.get_photos(asset.id)
            if photos:
                primary = next((p for p in photos if p['is_primary']), photos[0])
                asset.photos = [AssetPhoto(
                    id=primary['id'], asset_id=primary['asset_id'],
                    filename=primary['filename'],
                    original_filename=primary['original_filename'],
                    is_primary=True
                )]
            assets.append(asset)
        return assets

    def update_asset(self, asset_id: int, item_name: str, category: str,
                     serial_number: str, estimated_value: float,
                     location: str, notes: str = "",
                     purchase_price: float = None, purchase_date: str = None,
                     warranty_expiration: str = None, condition: str = "Good",
                     brand: str = "", model_number: str = "",
                     tags: str = "") -> Tuple[bool, str]:
        """Update an existing asset."""
        try:
            asset = Asset(
                id=asset_id, item_name=item_name, category=category,
                serial_number=serial_number, estimated_value=estimated_value,
                location=location, notes=notes,
                purchase_price=purchase_price, purchase_date=purchase_date,
                warranty_expiration=warranty_expiration, condition=condition,
                brand=brand, model_number=model_number, tags=tags
            )

            is_valid, error_msg = asset.validate()
            if not is_valid:
                return False, error_msg

            success = self.db.update_asset(
                asset_id=asset_id,
                item_name=asset.item_name, category=asset.category,
                serial_number=asset.serial_number,
                estimated_value=asset.estimated_value,
                location=asset.location, notes=asset.notes,
                purchase_price=asset.purchase_price,
                purchase_date=asset.purchase_date,
                warranty_expiration=asset.warranty_expiration,
                condition=asset.condition, brand=asset.brand,
                model_number=asset.model_number, tags=asset.tags
            )

            if success:
                self.db.log_activity(asset_id, "updated",
                                     f"Updated '{item_name}'")
                return True, f"Successfully updated '{item_name}'"
            else:
                return False, "Asset not found"

        except ValueError as e:
            return False, str(e)
        except Exception as e:
            logger.error(f"Error updating asset: {e}")
            return False, f"Database error: {str(e)}"

    def delete_asset(self, asset_id: int) -> Tuple[bool, str]:
        """Delete an asset and its photos."""
        try:
            asset = self.get_asset(asset_id)
            if not asset:
                return False, "Asset not found"

            # Delete photo files
            for photo in asset.photos:
                self._delete_photo_file(photo.filename)

            self.db.log_activity(asset_id, "deleted",
                                 f"Deleted '{asset.item_name}'")

            success = self.db.delete_asset(asset_id)
            if success:
                return True, f"Successfully deleted '{asset.item_name}'"
            else:
                return False, "Failed to delete asset"

        except Exception as e:
            logger.error(f"Error deleting asset: {e}")
            return False, f"Database error: {str(e)}"

    def search_assets(self, query: str = "", category: str = None,
                      location: str = None, min_value: float = None,
                      max_value: float = None) -> List[Asset]:
        """Search assets with filters."""
        assets_data = self.db.search_assets(
            query=query, category=category, location=location,
            min_value=min_value, max_value=max_value
        )
        assets = []
        for data in assets_data:
            asset = Asset.from_dict(data)
            photos = self.db.get_photos(asset.id)
            if photos:
                primary = next((p for p in photos if p['is_primary']), photos[0])
                asset.photos = [AssetPhoto(
                    id=primary['id'], asset_id=primary['asset_id'],
                    filename=primary['filename'],
                    original_filename=primary['original_filename'],
                    is_primary=True
                )]
            assets.append(asset)
        return assets

    def get_categories(self) -> List[str]:
        return self.db.get_categories()

    def get_locations(self) -> List[str]:
        return self.db.get_locations()

    def get_summary(self) -> dict:
        return self.db.get_summary()

    # =========================================================================
    # Photo Management
    # =========================================================================

    def add_photo(self, asset_id: int, file_data, original_filename: str) -> Tuple[bool, str, Optional[int]]:
        """
        Save and register a photo for an asset.
        file_data: file-like object with read() method.
        """
        try:
            from PIL import Image

            # Generate unique filename
            ext = os.path.splitext(original_filename)[1].lower()
            if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
                return False, "Invalid image format. Use JPG, PNG, GIF, or WebP.", None

            unique_name = f"{asset_id}_{uuid.uuid4().hex[:12]}{ext}"
            filepath = os.path.join(self.upload_folder, unique_name)
            thumb_path = os.path.join(self.thumbnail_folder, unique_name)

            # Save original
            file_data.save(filepath)

            # Create thumbnail (300x300 max, maintaining aspect ratio)
            try:
                with Image.open(filepath) as img:
                    # Convert RGBA to RGB for JPEG
                    if img.mode in ('RGBA', 'P') and ext in ('.jpg', '.jpeg'):
                        img = img.convert('RGB')
                    img.thumbnail((400, 400), Image.Resampling.LANCZOS)
                    img.save(thumb_path, quality=85)
            except Exception as e:
                logger.warning(f"Thumbnail creation failed: {e}")
                # Copy original as thumbnail fallback
                import shutil
                shutil.copy2(filepath, thumb_path)

            # Register in database
            photo_id = self.db.add_photo(asset_id, unique_name, original_filename)
            self.db.log_activity(asset_id, "photo_added",
                                 f"Added photo: {original_filename}")

            return True, "Photo uploaded successfully", photo_id

        except Exception as e:
            logger.error(f"Error adding photo: {e}")
            return False, f"Error uploading photo: {str(e)}", None

    def delete_photo(self, photo_id: int) -> Tuple[bool, str]:
        """Delete a photo by ID."""
        try:
            filename = self.db.delete_photo(photo_id)
            if filename:
                self._delete_photo_file(filename)
                return True, "Photo deleted successfully"
            return False, "Photo not found"
        except Exception as e:
            logger.error(f"Error deleting photo: {e}")
            return False, f"Error: {str(e)}"

    def set_primary_photo(self, asset_id: int, photo_id: int) -> Tuple[bool, str]:
        """Set a photo as the primary photo."""
        success = self.db.set_primary_photo(asset_id, photo_id)
        if success:
            return True, "Primary photo updated"
        return False, "Photo not found"

    def _delete_photo_file(self, filename: str):
        """Delete photo and thumbnail files from disk."""
        filepath = os.path.join(self.upload_folder, filename)
        thumb_path = os.path.join(self.thumbnail_folder, filename)
        for path in [filepath, thumb_path]:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError as e:
                logger.warning(f"Failed to delete file {path}: {e}")

    # =========================================================================
    # Activity Log
    # =========================================================================

    def get_activity_log(self, asset_id: int = None, limit: int = 50) -> List[ActivityLogEntry]:
        """Get activity log entries."""
        entries = self.db.get_activity_log(asset_id, limit)
        return [
            ActivityLogEntry(
                id=e['id'], asset_id=e['asset_id'],
                action=e['action'], details=e['details'],
                created_at=e['created_at']
            )
            for e in entries
        ]

    # =========================================================================
    # QR Code Generation
    # =========================================================================

    def generate_qr_code(self, asset_id: int, base_url: str) -> Optional[bytes]:
        """Generate a QR code PNG for an asset."""
        try:
            import qrcode
            from io import BytesIO

            asset = self.get_asset(asset_id)
            if not asset:
                return None

            url = f"{base_url}/asset/{asset_id}"
            qr = qrcode.QRCode(
                version=1, error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10, border=4
            )
            qr.add_data(url)
            qr.make(fit=True)

            img = qr.make_image(fill_color="#1e293b", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            return buffer.getvalue()

        except Exception as e:
            logger.error(f"QR code generation failed: {e}")
            return None

    # =========================================================================
    # Insurance Report
    # =========================================================================

    def generate_insurance_report(self, asset_ids: List[int] = None) -> Optional[bytes]:
        """Generate a professional insurance report PDF."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph,
                Spacer, PageBreak, Image as RLImage
            )
            from io import BytesIO
            from datetime import datetime

            if asset_ids:
                assets = [self.get_asset(aid) for aid in asset_ids]
                assets = [a for a in assets if a is not None]
            else:
                assets = self.get_all_assets()

            summary = self.get_summary()

            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer, pagesize=letter,
                rightMargin=0.75*inch, leftMargin=0.75*inch,
                topMargin=0.75*inch, bottomMargin=0.75*inch
            )

            elements = []
            styles = getSampleStyleSheet()

            # Title
            title_style = ParagraphStyle(
                'InsuranceTitle', parent=styles['Heading1'],
                fontSize=22, spaceAfter=6, textColor=colors.HexColor('#1e293b')
            )
            elements.append(Paragraph('Home Asset Insurance Report', title_style))

            subtitle_style = ParagraphStyle(
                'InsuranceSubtitle', parent=styles['Normal'],
                fontSize=11, spaceAfter=20, textColor=colors.HexColor('#64748b')
            )
            elements.append(Paragraph(
                f'Generated: {datetime.now().strftime("%B %d, %Y at %I:%M %p")}',
                subtitle_style
            ))

            # Summary box
            summary_data = [
                ['Total Items', 'Total Value', 'Average Value', 'Highest Value'],
                [
                    str(summary['total_items']),
                    f"${summary['total_value']:,.2f}",
                    f"${summary['avg_value']:,.2f}",
                    f"${summary['max_value']:,.2f}",
                ]
            ]
            summary_table = Table(summary_data, colWidths=[1.7*inch]*4)
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6366f1')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#f1f5f9')),
                ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 1), (-1, 1), 12),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('ROUNDEDCORNERS', [6, 6, 6, 6]),
            ]))
            elements.append(summary_table)
            elements.append(Spacer(1, 0.3*inch))

            # Item details
            item_header_style = ParagraphStyle(
                'ItemHeader', parent=styles['Heading2'],
                fontSize=14, spaceBefore=12, spaceAfter=6,
                textColor=colors.HexColor('#1e293b')
            )
            detail_style = ParagraphStyle(
                'Detail', parent=styles['Normal'],
                fontSize=9, textColor=colors.HexColor('#334155')
            )

            for i, asset in enumerate(assets):
                if i > 0 and i % 4 == 0:
                    elements.append(PageBreak())

                elements.append(Paragraph(
                    f'{i+1}. {asset.item_name}', item_header_style
                ))

                detail_data = [
                    ['Category', asset.category, 'Location', asset.location],
                    ['Estimated Value', f'${asset.estimated_value:,.2f}',
                     'Condition', asset.condition or 'N/A'],
                    ['Serial Number', asset.serial_number or 'N/A',
                     'Brand/Model', f'{asset.brand} {asset.model_number}'.strip() or 'N/A'],
                ]

                if asset.purchase_price is not None:
                    detail_data.append([
                        'Purchase Price', f'${asset.purchase_price:,.2f}',
                        'Purchase Date', asset.purchase_date or 'N/A'
                    ])

                if asset.warranty_expiration:
                    warranty_status = "Active" if asset.is_warranty_active else "Expired"
                    detail_data.append([
                        'Warranty Expires', asset.warranty_expiration,
                        'Warranty Status', warranty_status
                    ])

                detail_table = Table(detail_data, colWidths=[1.3*inch, 2.1*inch, 1.3*inch, 2.1*inch])
                detail_table.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#64748b')),
                    ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#64748b')),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('LINEBELOW', (0, -1), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ]))
                elements.append(detail_table)

                if asset.notes:
                    elements.append(Spacer(1, 4))
                    elements.append(Paragraph(
                        f'<i>Notes: {asset.notes[:200]}</i>', detail_style
                    ))
                elements.append(Spacer(1, 8))

            # Footer
            elements.append(Spacer(1, 0.3*inch))
            footer_style = ParagraphStyle(
                'Footer', parent=styles['Normal'],
                fontSize=8, textColor=colors.gray, alignment=1
            )
            elements.append(Paragraph(
                'This report was generated by Asset Inventory for insurance documentation purposes.',
                footer_style
            ))

            doc.build(elements)
            buffer.seek(0)
            return buffer.getvalue()

        except Exception as e:
            logger.error(f"Insurance report generation failed: {e}")
            return None

    # =========================================================================
    # Utility
    # =========================================================================

    def backup_database(self, backup_path: str = None) -> str:
        return self.db.backup_database(backup_path)
