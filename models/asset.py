"""
Asset model with validation and security best practices.
Extended with purchase tracking, warranty, condition, and photo support.
"""
import re
import html
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, Dict, Any, List


@dataclass
class AssetPhoto:
    """Represents a photo attached to an asset."""
    id: Optional[int] = None
    asset_id: Optional[int] = None
    filename: str = ""
    original_filename: str = ""
    is_primary: bool = False
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'asset_id': self.asset_id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'is_primary': self.is_primary,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


@dataclass
class ActivityLogEntry:
    """Represents an activity log entry."""
    id: Optional[int] = None
    asset_id: Optional[int] = None
    action: str = ""
    details: str = ""
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'asset_id': self.asset_id,
            'action': self.action,
            'details': self.details,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


@dataclass
class Asset:
    """
    Represents a single asset/item in the inventory.

    Includes input validation, sanitization, and extended fields
    for purchase tracking, warranty management, and condition assessment.
    """

    item_name: str
    category: str
    estimated_value: float
    location: str
    id: Optional[int] = None
    serial_number: str = ""
    notes: str = ""
    # New extended fields
    purchase_price: Optional[float] = None
    purchase_date: Optional[str] = None  # YYYY-MM-DD
    warranty_expiration: Optional[str] = None  # YYYY-MM-DD
    condition: str = "Good"
    brand: str = ""
    model_number: str = ""
    tags: str = ""  # Comma-separated
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Related data (not stored in assets table)
    photos: List[AssetPhoto] = field(default_factory=list)

    # Maximum field lengths for security
    MAX_NAME_LENGTH: int = field(default=200, repr=False, compare=False)
    MAX_CATEGORY_LENGTH: int = field(default=100, repr=False, compare=False)
    MAX_SERIAL_LENGTH: int = field(default=100, repr=False, compare=False)
    MAX_LOCATION_LENGTH: int = field(default=200, repr=False, compare=False)
    MAX_NOTES_LENGTH: int = field(default=1000, repr=False, compare=False)
    MAX_BRAND_LENGTH: int = field(default=100, repr=False, compare=False)
    MAX_MODEL_LENGTH: int = field(default=100, repr=False, compare=False)
    MAX_TAGS_LENGTH: int = field(default=500, repr=False, compare=False)
    MAX_VALUE: float = field(default=999999999.99, repr=False, compare=False)

    # Valid condition values
    VALID_CONDITIONS: tuple = field(
        default=("New", "Excellent", "Good", "Fair", "Poor"),
        repr=False, compare=False
    )

    # Category icon mapping
    CATEGORY_ICONS: dict = field(default_factory=lambda: {
        'Electronics': 'bi-laptop',
        'Furniture': 'bi-lamp',
        'Appliances': 'bi-plug',
        'Jewelry': 'bi-gem',
        'Clothing': 'bi-bag',
        'Tools': 'bi-tools',
        'Sports Equipment': 'bi-bicycle',
        'Musical Instruments': 'bi-music-note-beamed',
        'Art': 'bi-palette',
        'Collectibles': 'bi-star',
        'Vehicles': 'bi-car-front',
        'Books': 'bi-book',
        'Kitchenware': 'bi-cup-hot',
        'Outdoor': 'bi-tree',
        'Office': 'bi-briefcase',
        'Gaming': 'bi-controller',
        'Photography': 'bi-camera',
        'Audio': 'bi-headphones',
        'Other': 'bi-box-seam',
    }, repr=False, compare=False)

    def __post_init__(self):
        """Validate and sanitize all fields after initialization."""
        self.item_name = self._sanitize_string(self.item_name, self.MAX_NAME_LENGTH)
        self.category = self._sanitize_string(self.category, self.MAX_CATEGORY_LENGTH)
        self.serial_number = self._sanitize_string(self.serial_number, self.MAX_SERIAL_LENGTH)
        self.location = self._sanitize_string(self.location, self.MAX_LOCATION_LENGTH)
        self.notes = self._sanitize_string(self.notes, self.MAX_NOTES_LENGTH)
        self.brand = self._sanitize_string(self.brand, self.MAX_BRAND_LENGTH)
        self.model_number = self._sanitize_string(self.model_number, self.MAX_MODEL_LENGTH)
        self.tags = self._sanitize_string(self.tags, self.MAX_TAGS_LENGTH)
        self.estimated_value = self._validate_value(self.estimated_value)

        if self.purchase_price is not None:
            self.purchase_price = self._validate_value(self.purchase_price)

        if self.condition and self.condition not in self.VALID_CONDITIONS:
            self.condition = "Good"

    @staticmethod
    def _sanitize_string(value: str, max_length: int) -> str:
        """Sanitize string input to prevent injection attacks."""
        if not value:
            return ""
        value = str(value)
        value = value.strip()
        value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)
        value = html.escape(value)
        if len(value) > max_length:
            value = value[:max_length]
        return value

    @staticmethod
    def _validate_value(value: float) -> float:
        """Validate monetary value."""
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValueError("Estimated value must be a valid number")
        if value < 0:
            raise ValueError("Estimated value cannot be negative")
        if value > 999999999.99:
            raise ValueError("Estimated value exceeds maximum allowed")
        return round(value, 2)

    def validate(self) -> tuple:
        """Validate that all required fields are present and valid."""
        if not self.item_name:
            return False, "Item name is required"
        if not self.category:
            return False, "Category is required"
        if not self.location:
            return False, "Location is required"
        if self.estimated_value < 0:
            return False, "Estimated value cannot be negative"
        return True, ""

    def get_category_icon(self) -> str:
        """Get the Bootstrap icon class for this asset's category."""
        return self.CATEGORY_ICONS.get(self.category, 'bi-box-seam')

    def get_tags_list(self) -> List[str]:
        """Get tags as a list."""
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(',') if t.strip()]

    def get_primary_photo(self) -> Optional[AssetPhoto]:
        """Get the primary photo, or first photo if none is primary."""
        if not self.photos:
            return None
        for photo in self.photos:
            if photo.is_primary:
                return photo
        return self.photos[0]

    @property
    def is_warranty_active(self) -> Optional[bool]:
        """Check if warranty is still active."""
        if not self.warranty_expiration:
            return None
        try:
            exp_date = datetime.strptime(self.warranty_expiration, '%Y-%m-%d').date()
            return exp_date >= date.today()
        except (ValueError, TypeError):
            return None

    @property
    def warranty_days_remaining(self) -> Optional[int]:
        """Get days remaining on warranty."""
        if not self.warranty_expiration:
            return None
        try:
            exp_date = datetime.strptime(self.warranty_expiration, '%Y-%m-%d').date()
            delta = exp_date - date.today()
            return delta.days
        except (ValueError, TypeError):
            return None

    @property
    def depreciation_percentage(self) -> Optional[float]:
        """Calculate simple depreciation based on purchase price vs current value."""
        if self.purchase_price and self.purchase_price > 0:
            return round(
                ((self.purchase_price - self.estimated_value) / self.purchase_price) * 100, 1
            )
        return None

    @property
    def condition_color(self) -> str:
        """Get a color class for the condition."""
        colors = {
            'New': 'success',
            'Excellent': 'success',
            'Good': 'primary',
            'Fair': 'warning',
            'Poor': 'danger',
        }
        return colors.get(self.condition, 'secondary')

    def to_dict(self) -> Dict[str, Any]:
        """Convert asset to dictionary for serialization."""
        result = {
            'id': self.id,
            'item_name': self.item_name,
            'category': self.category,
            'serial_number': self.serial_number,
            'estimated_value': self.estimated_value,
            'purchase_price': self.purchase_price,
            'purchase_date': self.purchase_date,
            'warranty_expiration': self.warranty_expiration,
            'condition': self.condition,
            'brand': self.brand,
            'model_number': self.model_number,
            'tags': self.tags,
            'location': self.location,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if self.photos:
            result['photos'] = [p.to_dict() for p in self.photos]
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Asset':
        """Create an Asset instance from a dictionary."""
        created_at = None
        updated_at = None

        if data.get('created_at'):
            if isinstance(data['created_at'], str):
                created_at = datetime.fromisoformat(data['created_at'])
            else:
                created_at = data['created_at']

        if data.get('updated_at'):
            if isinstance(data['updated_at'], str):
                updated_at = datetime.fromisoformat(data['updated_at'])
            else:
                updated_at = data['updated_at']

        return cls(
            id=data.get('id'),
            item_name=data.get('item_name', ''),
            category=data.get('category', ''),
            serial_number=data.get('serial_number', ''),
            estimated_value=float(data.get('estimated_value', 0)),
            purchase_price=float(data['purchase_price']) if data.get('purchase_price') is not None else None,
            purchase_date=data.get('purchase_date') or None,
            warranty_expiration=data.get('warranty_expiration') or None,
            condition=data.get('condition', 'Good') or 'Good',
            brand=data.get('brand', ''),
            model_number=data.get('model_number', ''),
            tags=data.get('tags', ''),
            location=data.get('location', ''),
            notes=data.get('notes', ''),
            created_at=created_at,
            updated_at=updated_at,
        )

    def __str__(self) -> str:
        """Return a formatted string representation of the asset."""
        lines = [
            f"Item: {self.item_name}",
            f"Category: {self.category}",
            f"Brand: {self.brand or 'N/A'}",
            f"Model: {self.model_number or 'N/A'}",
            f"Serial Number: {self.serial_number or 'N/A'}",
            f"Condition: {self.condition}",
            f"Estimated Value: ${self.estimated_value:,.2f}",
        ]
        if self.purchase_price is not None:
            lines.append(f"Purchase Price: ${self.purchase_price:,.2f}")
        if self.purchase_date:
            lines.append(f"Purchase Date: {self.purchase_date}")
        if self.warranty_expiration:
            lines.append(f"Warranty Expires: {self.warranty_expiration}")
        lines.extend([
            f"Location: {self.location}",
            f"Tags: {self.tags or 'None'}",
            f"Notes: {self.notes or 'None'}",
        ])
        if self.created_at:
            lines.append(f"Added: {self.created_at.strftime('%Y-%m-%d %H:%M')}")
        if self.updated_at:
            lines.append(f"Updated: {self.updated_at.strftime('%Y-%m-%d %H:%M')}")
        lines.append("-" * 40)
        return "\n".join(lines)
