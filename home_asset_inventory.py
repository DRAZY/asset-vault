#!/usr/bin/env python3
"""
Home Asset Inventory CLI - Terminal application for asset management.

Features:
- Full CRUD operations (Create, Read, Update, Delete)
- SQLite database with secure parameterized queries
- Search and filter functionality
- Input validation and sanitization
- Data backup and CSV export

Author: Asset Inventory Team
"""
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.asset_service import AssetService


class AssetInventoryCLI:
    """
    Terminal application for managing household asset inventory.

    Uses the shared AssetService for database operations with proper
    input validation and security measures.
    """

    def __init__(self):
        """Initialize the CLI application."""
        self.service = AssetService()
        self._check_migration()

    def _check_migration(self):
        """Check for and handle CSV migration."""
        if self.service.has_pending_migration:
            print("\nFound existing CSV data (assets.csv).")
            response = input("Would you like to import it into the database? (y/n): ").strip().lower()
            if response == 'y':
                successful, failed = self.service.migrate_from_csv()
                print(f"Imported {successful} assets. Failed: {failed}")

    def display_menu(self):
        """Display the main menu options."""
        print("\n" + "=" * 55)
        print("           HOME ASSET INVENTORY")
        print("=" * 55)
        print("1. Add new asset")
        print("2. View all assets")
        print("3. Search assets")
        print("4. Edit asset")
        print("5. Delete asset")
        print("6. View summary")
        print("7. Export to CSV")
        print("8. Backup database")
        print("9. Exit")
        print("-" * 55)

    def get_valid_input(self, prompt: str, input_type: type = str,
                        allow_empty: bool = False, min_value: float = None) -> any:
        """
        Get validated input from the user.

        Args:
            prompt: The prompt to display
            input_type: Expected type (str, float, int)
            allow_empty: Whether empty input is allowed
            min_value: Minimum value for numeric types

        Returns:
            The validated input
        """
        while True:
            try:
                user_input = input(prompt).strip()

                if not user_input and allow_empty:
                    return "" if input_type == str else 0.0

                if not user_input:
                    print("This field cannot be empty. Please try again.")
                    continue

                if input_type == float:
                    value = float(user_input)
                    if min_value is not None and value < min_value:
                        print(f"Value must be at least {min_value}.")
                        continue
                    return value
                elif input_type == int:
                    value = int(user_input)
                    if min_value is not None and value < min_value:
                        print(f"Value must be at least {min_value}.")
                        continue
                    return value
                else:
                    return user_input

            except ValueError:
                if input_type == float:
                    print("Please enter a valid number (e.g., 25.99)")
                elif input_type == int:
                    print("Please enter a valid whole number")

    def add_asset(self):
        """Add a new asset to the inventory."""
        print("\n" + "=" * 35)
        print("      ADD NEW ASSET")
        print("=" * 35)

        item_name = self.get_valid_input("Enter item name: ")
        category = self.get_valid_input("Enter category: ")
        serial_number = self.get_valid_input("Enter serial number (optional): ", allow_empty=True)
        estimated_value = self.get_valid_input("Enter estimated value ($): ", float, min_value=0)
        location = self.get_valid_input("Enter location: ")
        notes = self.get_valid_input("Enter notes (optional): ", allow_empty=True)

        success, message, asset_id = self.service.add_asset(
            item_name=item_name,
            category=category,
            serial_number=serial_number,
            estimated_value=estimated_value,
            location=location,
            notes=notes
        )

        if success:
            print(f"\n[OK] {message} (ID: {asset_id})")
        else:
            print(f"\n[ERROR] {message}")

    def view_all_assets(self):
        """Display all assets in the inventory."""
        print("\n" + "=" * 35)
        print("      ALL ASSETS")
        print("=" * 35)

        assets = self.service.get_all_assets()

        if not assets:
            print("No assets in inventory yet.")
            return

        summary = self.service.get_summary()
        print(f"Total items: {summary['total_items']}")
        print(f"Total value: ${summary['total_value']:,.2f}")
        print("\n")

        for i, asset in enumerate(assets, 1):
            print(f"ASSET #{i} (ID: {asset.id})")
            print(asset)
            print()

    def search_assets(self):
        """Search for assets with filters."""
        print("\n" + "=" * 35)
        print("      SEARCH ASSETS")
        print("=" * 35)

        print("\nSearch options:")
        print("1. Search by name")
        print("2. Filter by category")
        print("3. Filter by location")
        print("4. Filter by value range")

        choice = self.get_valid_input("\nEnter option (1-4): ")

        assets = []

        if choice == '1':
            query = self.get_valid_input("Enter search term: ")
            assets = self.service.search_assets(query=query)
        elif choice == '2':
            categories = self.service.get_categories()
            if categories:
                print("\nAvailable categories:")
                for i, cat in enumerate(categories, 1):
                    print(f"  {i}. {cat}")
                category = self.get_valid_input("\nEnter category: ")
                assets = self.service.search_assets(category=category)
            else:
                print("No categories found.")
                return
        elif choice == '3':
            locations = self.service.get_locations()
            if locations:
                print("\nAvailable locations:")
                for i, loc in enumerate(locations, 1):
                    print(f"  {i}. {loc}")
                location = self.get_valid_input("\nEnter location: ")
                assets = self.service.search_assets(location=location)
            else:
                print("No locations found.")
                return
        elif choice == '4':
            min_val = self.get_valid_input("Enter minimum value ($): ", float, allow_empty=True, min_value=0)
            max_val = self.get_valid_input("Enter maximum value ($): ", float, allow_empty=True, min_value=0)
            min_val = min_val if min_val else None
            max_val = max_val if max_val else None
            assets = self.service.search_assets(min_value=min_val, max_value=max_val)
        else:
            print("Invalid option.")
            return

        if not assets:
            print("\nNo assets found matching your criteria.")
            return

        print(f"\nFound {len(assets)} asset(s):\n")
        for asset in assets:
            print(f"ID: {asset.id} | {asset.item_name} | {asset.category} | ${asset.estimated_value:,.2f} | {asset.location}")

    def edit_asset(self):
        """Edit an existing asset."""
        print("\n" + "=" * 35)
        print("      EDIT ASSET")
        print("=" * 35)

        # Show all assets first
        assets = self.service.get_all_assets()
        if not assets:
            print("No assets to edit.")
            return

        print("\nCurrent assets:")
        for asset in assets:
            print(f"  ID: {asset.id} - {asset.item_name}")

        asset_id = self.get_valid_input("\nEnter asset ID to edit: ", int)

        asset = self.service.get_asset(asset_id)
        if not asset:
            print("Asset not found.")
            return

        print(f"\nEditing: {asset.item_name}")
        print("(Press Enter to keep current value)\n")

        # Get new values (or keep existing)
        new_name = input(f"Item name [{asset.item_name}]: ").strip()
        new_name = new_name if new_name else asset.item_name

        new_category = input(f"Category [{asset.category}]: ").strip()
        new_category = new_category if new_category else asset.category

        new_serial = input(f"Serial number [{asset.serial_number or 'N/A'}]: ").strip()
        new_serial = new_serial if new_serial else (asset.serial_number or "")

        value_input = input(f"Estimated value [${asset.estimated_value:.2f}]: ").strip()
        if value_input:
            try:
                new_value = float(value_input)
                if new_value < 0:
                    print("Value cannot be negative. Keeping original value.")
                    new_value = asset.estimated_value
            except ValueError:
                print("Invalid value. Keeping original value.")
                new_value = asset.estimated_value
        else:
            new_value = asset.estimated_value

        new_location = input(f"Location [{asset.location}]: ").strip()
        new_location = new_location if new_location else asset.location

        new_notes = input(f"Notes [{asset.notes or 'None'}]: ").strip()
        new_notes = new_notes if new_notes else (asset.notes or "")

        # Update the asset
        success, message = self.service.update_asset(
            asset_id=asset_id,
            item_name=new_name,
            category=new_category,
            serial_number=new_serial,
            estimated_value=new_value,
            location=new_location,
            notes=new_notes
        )

        if success:
            print(f"\n[OK] {message}")
        else:
            print(f"\n[ERROR] {message}")

    def delete_asset(self):
        """Delete an asset from the inventory."""
        print("\n" + "=" * 35)
        print("      DELETE ASSET")
        print("=" * 35)

        # Show all assets first
        assets = self.service.get_all_assets()
        if not assets:
            print("No assets to delete.")
            return

        print("\nCurrent assets:")
        for asset in assets:
            print(f"  ID: {asset.id} - {asset.item_name} (${asset.estimated_value:,.2f})")

        asset_id = self.get_valid_input("\nEnter asset ID to delete: ", int)

        asset = self.service.get_asset(asset_id)
        if not asset:
            print("Asset not found.")
            return

        # Confirm deletion
        print(f"\nYou are about to delete: {asset.item_name}")
        confirm = input("Are you sure? This cannot be undone. (y/n): ").strip().lower()

        if confirm == 'y':
            success, message = self.service.delete_asset(asset_id)
            if success:
                print(f"\n[OK] {message}")
            else:
                print(f"\n[ERROR] {message}")
        else:
            print("Deletion cancelled.")

    def view_summary(self):
        """Display inventory summary statistics."""
        print("\n" + "=" * 35)
        print("      INVENTORY SUMMARY")
        print("=" * 35)

        summary = self.service.get_summary()

        print(f"\nTotal Assets: {summary['total_items']}")
        print(f"Total Value: ${summary['total_value']:,.2f}")

        if summary['categories']:
            print("\nValue by Category:")
            print("-" * 40)
            for cat in summary['categories']:
                print(f"  {cat['category']}: {cat['count']} items, ${cat['value']:,.2f}")

    def export_csv(self):
        """Export assets to a CSV file."""
        print("\n" + "=" * 35)
        print("      EXPORT TO CSV")
        print("=" * 35)

        default_path = os.path.join(os.path.dirname(__file__), "assets_export.csv")
        path = input(f"Enter file path [{default_path}]: ").strip()
        path = path if path else default_path

        success, message, count = self.service.export_to_csv(path)

        if success:
            print(f"\n[OK] {message}")
        else:
            print(f"\n[ERROR] {message}")

    def backup_database(self):
        """Create a database backup."""
        print("\n" + "=" * 35)
        print("      BACKUP DATABASE")
        print("=" * 35)

        try:
            backup_path = self.service.backup_database()
            print(f"\n[OK] Database backed up to: {backup_path}")
        except Exception as e:
            print(f"\n[ERROR] Backup failed: {e}")

    def run(self):
        """Main application loop."""
        print("\nWelcome to Home Asset Inventory!")
        print("Using SQLite database for secure data storage.")

        while True:
            self.display_menu()

            try:
                choice = input("Enter your choice (1-9): ").strip()

                if choice == '1':
                    self.add_asset()
                elif choice == '2':
                    self.view_all_assets()
                elif choice == '3':
                    self.search_assets()
                elif choice == '4':
                    self.edit_asset()
                elif choice == '5':
                    self.delete_asset()
                elif choice == '6':
                    self.view_summary()
                elif choice == '7':
                    self.export_csv()
                elif choice == '8':
                    self.backup_database()
                elif choice == '9':
                    print("\nThank you for using Home Asset Inventory!")
                    print("Goodbye!")
                    break
                else:
                    print("\n[WARNING] Invalid choice. Please enter 1-9.")

            except KeyboardInterrupt:
                print("\n\nExiting application...")
                break
            except Exception as e:
                print(f"\n[ERROR] An error occurred: {e}")
                print("Please try again.")


def main():
    """Main entry point for the CLI application."""
    app = AssetInventoryCLI()
    app.run()


if __name__ == "__main__":
    main()
