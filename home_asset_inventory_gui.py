#!/usr/bin/env python3
"""
Home Asset Inventory GUI - Modern Tkinter application for asset management.

Features:
- Full CRUD operations (Create, Read, Update, Delete)
- SQLite database with secure parameterized queries
- Search and filter functionality
- Sortable table view
- Input validation and sanitization
- Data backup and CSV export

Author: Asset Inventory Team
"""
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional

# Suppress macOS Tk deprecation warning
os.environ['TK_SILENCE_DEPRECATION'] = '1'

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.asset_service import AssetService


class AssetInventoryGUI:
    """
    Modern GUI application for managing household asset inventory.

    Features a Treeview table for displaying assets with full CRUD operations,
    search/filter functionality, and data export capabilities.
    """

    def __init__(self):
        """Initialize the GUI application."""
        # Initialize the service layer
        self.service = AssetService()

        # Track the currently selected asset for editing
        self.selected_asset_id: Optional[int] = None
        self.edit_mode = False

        # Create main window
        self.root = tk.Tk()
        self.root.title("Home Asset Inventory")
        self.root.geometry("1200x750")
        self.root.minsize(1000, 650)
        self.root.resizable(True, True)

        # Configure style
        self._configure_styles()

        # Center the window on screen
        self._center_window()

        # Create the GUI components
        self._create_widgets()

        # Check for CSV migration
        self._check_migration()

        # Load initial data
        self._refresh_display()

        # Bind keyboard shortcuts
        self._bind_shortcuts()

    def _configure_styles(self):
        """Configure ttk styles for a modern look."""
        style = ttk.Style()

        # Try to use a modern theme
        available_themes = style.theme_names()
        if 'clam' in available_themes:
            style.theme_use('clam')
        elif 'aqua' in available_themes:
            style.theme_use('aqua')

        # Configure Treeview style
        style.configure("Treeview",
                        rowheight=28,
                        font=('Arial', 11))
        style.configure("Treeview.Heading",
                        font=('Arial', 11, 'bold'))

        # Configure button styles
        style.configure("Action.TButton",
                        font=('Arial', 10),
                        padding=5)
        style.configure("Delete.TButton",
                        font=('Arial', 10),
                        padding=5)

    def _center_window(self):
        """Center the window on the screen."""
        self.root.update_idletasks()
        width = 1200
        height = 750
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def _bind_shortcuts(self):
        """Bind keyboard shortcuts."""
        self.root.bind('<Command-n>', lambda e: self._clear_form())
        self.root.bind('<Control-n>', lambda e: self._clear_form())
        self.root.bind('<Command-s>', lambda e: self._save_asset())
        self.root.bind('<Control-s>', lambda e: self._save_asset())
        self.root.bind('<Delete>', lambda e: self._delete_asset())
        self.root.bind('<Escape>', lambda e: self._cancel_edit())

    def _create_widgets(self):
        """Create and arrange all GUI widgets."""
        self.root.configure(padx=15, pady=10)

        # Title
        title_frame = ttk.Frame(self.root)
        title_frame.pack(fill=tk.X, pady=(0, 15))

        title_label = ttk.Label(title_frame, text="Home Asset Inventory",
                                font=('Arial', 18, 'bold'))
        title_label.pack(side=tk.LEFT)

        # Summary label (right side of title)
        self.summary_label = ttk.Label(title_frame, text="",
                                       font=('Arial', 12))
        self.summary_label.pack(side=tk.RIGHT)

        # Main container
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Left panel - Form
        left_panel = ttk.Frame(main_container, width=350)
        main_container.add(left_panel, weight=0)

        # Right panel - Table and search
        right_panel = ttk.Frame(main_container)
        main_container.add(right_panel, weight=1)

        # Build panels
        self._create_form_panel(left_panel)
        self._create_table_panel(right_panel)

        # Status bar
        self._create_status_bar()

    def _create_form_panel(self, parent):
        """Create the input form panel."""
        # Form frame
        form_frame = ttk.LabelFrame(parent, text="Asset Details", padding="15")
        form_frame.pack(fill=tk.BOTH, expand=True, padx=(0, 10))

        # Mode indicator
        self.mode_label = ttk.Label(form_frame, text="Add New Asset",
                                    font=('Arial', 12, 'bold'))
        self.mode_label.pack(anchor=tk.W, pady=(0, 15))

        # Input fields
        fields = [
            ("Item Name *", "item_name"),
            ("Category *", "category"),
            ("Serial Number", "serial"),
            ("Estimated Value ($) *", "value"),
            ("Location *", "location")
        ]

        for label_text, attr_name in fields:
            field_frame = ttk.Frame(form_frame)
            field_frame.pack(fill=tk.X, pady=5)

            label = ttk.Label(field_frame, text=label_text, width=18)
            label.pack(side=tk.LEFT)

            var = tk.StringVar()
            setattr(self, f"{attr_name}_var", var)
            entry = ttk.Entry(field_frame, textvariable=var, width=28)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
            setattr(self, f"{attr_name}_entry", entry)

        # Notes field (multiline)
        notes_frame = ttk.Frame(form_frame)
        notes_frame.pack(fill=tk.X, pady=5)

        notes_label = ttk.Label(notes_frame, text="Notes", width=18)
        notes_label.pack(side=tk.LEFT, anchor=tk.N)

        self.notes_text = tk.Text(notes_frame, width=28, height=4,
                                  font=('Arial', 11))
        self.notes_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        # Button frame
        button_frame = ttk.Frame(form_frame)
        button_frame.pack(fill=tk.X, pady=(20, 10))

        # Save button (Add/Update)
        self.save_button = ttk.Button(button_frame, text="Add Asset",
                                      command=self._save_asset,
                                      style="Action.TButton")
        self.save_button.pack(side=tk.LEFT, padx=(0, 5))

        # Cancel button (only visible in edit mode)
        self.cancel_button = ttk.Button(button_frame, text="Cancel",
                                        command=self._cancel_edit,
                                        style="Action.TButton")
        self.cancel_button.pack(side=tk.LEFT, padx=5)
        self.cancel_button.pack_forget()  # Hide initially

        # Clear button
        clear_button = ttk.Button(button_frame, text="Clear",
                                  command=self._clear_form,
                                  style="Action.TButton")
        clear_button.pack(side=tk.LEFT, padx=5)

        # Separator
        ttk.Separator(form_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)

        # Actions section
        actions_label = ttk.Label(form_frame, text="Actions",
                                  font=('Arial', 11, 'bold'))
        actions_label.pack(anchor=tk.W, pady=(0, 10))

        # Delete selected
        self.delete_button = ttk.Button(form_frame, text="Delete Selected",
                                        command=self._delete_asset,
                                        style="Delete.TButton",
                                        state=tk.DISABLED)
        self.delete_button.pack(fill=tk.X, pady=2)

        # Export to CSV
        export_button = ttk.Button(form_frame, text="Export to CSV",
                                   command=self._export_csv,
                                   style="Action.TButton")
        export_button.pack(fill=tk.X, pady=2)

        # Backup database
        backup_button = ttk.Button(form_frame, text="Backup Database",
                                   command=self._backup_database,
                                   style="Action.TButton")
        backup_button.pack(fill=tk.X, pady=2)

    def _create_table_panel(self, parent):
        """Create the table panel with search and Treeview."""
        # Search frame
        search_frame = ttk.LabelFrame(parent, text="Search & Filter", padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10))

        # Search row
        search_row = ttk.Frame(search_frame)
        search_row.pack(fill=tk.X)

        # Search entry
        ttk.Label(search_row, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self._on_search_change)
        search_entry = ttk.Entry(search_row, textvariable=self.search_var, width=25)
        search_entry.pack(side=tk.LEFT, padx=(5, 15))

        # Category filter
        ttk.Label(search_row, text="Category:").pack(side=tk.LEFT)
        self.category_filter_var = tk.StringVar(value="All")
        self.category_combo = ttk.Combobox(search_row,
                                           textvariable=self.category_filter_var,
                                           state='readonly', width=15)
        self.category_combo.pack(side=tk.LEFT, padx=(5, 15))
        self.category_combo.bind('<<ComboboxSelected>>', self._on_filter_change)

        # Location filter
        ttk.Label(search_row, text="Location:").pack(side=tk.LEFT)
        self.location_filter_var = tk.StringVar(value="All")
        self.location_combo = ttk.Combobox(search_row,
                                           textvariable=self.location_filter_var,
                                           state='readonly', width=15)
        self.location_combo.pack(side=tk.LEFT, padx=(5, 15))
        self.location_combo.bind('<<ComboboxSelected>>', self._on_filter_change)

        # Clear filters button
        clear_filters_btn = ttk.Button(search_row, text="Clear Filters",
                                       command=self._clear_filters)
        clear_filters_btn.pack(side=tk.RIGHT)

        # Table frame
        table_frame = ttk.LabelFrame(parent, text="Asset Inventory", padding="10")
        table_frame.pack(fill=tk.BOTH, expand=True)

        # Create Treeview with scrollbars
        tree_container = ttk.Frame(table_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)

        # Scrollbars
        y_scroll = ttk.Scrollbar(tree_container, orient=tk.VERTICAL)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        x_scroll = ttk.Scrollbar(tree_container, orient=tk.HORIZONTAL)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Treeview
        columns = ('id', 'item_name', 'category', 'serial_number',
                   'estimated_value', 'location', 'notes')
        self.tree = ttk.Treeview(tree_container, columns=columns,
                                 show='headings', selectmode='browse',
                                 yscrollcommand=y_scroll.set,
                                 xscrollcommand=x_scroll.set)

        # Configure scrollbars
        y_scroll.config(command=self.tree.yview)
        x_scroll.config(command=self.tree.xview)

        # Define column headings and widths
        column_config = {
            'id': ('ID', 50, tk.CENTER),
            'item_name': ('Item Name', 180, tk.W),
            'category': ('Category', 100, tk.W),
            'serial_number': ('Serial Number', 120, tk.W),
            'estimated_value': ('Value ($)', 100, tk.E),
            'location': ('Location', 120, tk.W),
            'notes': ('Notes', 200, tk.W)
        }

        for col, (heading, width, anchor) in column_config.items():
            self.tree.heading(col, text=heading,
                              command=lambda c=col: self._sort_column(c))
            self.tree.column(col, width=width, anchor=anchor, minwidth=50)

        self.tree.pack(fill=tk.BOTH, expand=True)

        # Bind selection event
        self.tree.bind('<<TreeviewSelect>>', self._on_tree_select)
        self.tree.bind('<Double-1>', self._on_tree_double_click)

        # Sorting state
        self.sort_column = 'id'
        self.sort_descending = True

    def _create_status_bar(self):
        """Create the status bar."""
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var,
                               relief=tk.SUNKEN, font=('Arial', 10))
        status_bar.pack(fill=tk.X, pady=(10, 0))

    def _check_migration(self):
        """Check for and handle CSV migration."""
        if self.service.has_pending_migration:
            response = messagebox.askyesno(
                "Import Data",
                "Found existing CSV data. Would you like to import it into the database?"
            )
            if response:
                successful, failed = self.service.migrate_from_csv()
                if successful > 0:
                    messagebox.showinfo(
                        "Import Complete",
                        f"Successfully imported {successful} assets.\n"
                        f"Failed: {failed}"
                    )
                    self._update_status(f"Imported {successful} assets from CSV")

    def _refresh_display(self):
        """Refresh the table display and filters."""
        self._update_filters()
        self._apply_filters()
        self._update_summary()

    def _update_filters(self):
        """Update category and location filter dropdowns."""
        categories = ['All'] + self.service.get_categories()
        locations = ['All'] + self.service.get_locations()

        self.category_combo['values'] = categories
        self.location_combo['values'] = locations

    def _update_summary(self):
        """Update the summary statistics."""
        summary = self.service.get_summary()
        total_items = summary['total_items']
        total_value = summary['total_value']
        self.summary_label.config(
            text=f"Total: {total_items} items | Value: ${total_value:,.2f}"
        )

    def _apply_filters(self):
        """Apply search and filter to refresh the table."""
        # Get filter values
        query = self.search_var.get().strip()
        category = self.category_filter_var.get()
        location = self.location_filter_var.get()

        # Convert "All" to None for the service
        category = None if category == "All" else category
        location = None if location == "All" else location

        # Get filtered assets
        assets = self.service.search_assets(
            query=query,
            category=category,
            location=location
        )

        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Add assets to tree
        for asset in assets:
            self.tree.insert('', tk.END, values=(
                asset.id,
                asset.item_name,
                asset.category,
                asset.serial_number or '',
                f"{asset.estimated_value:,.2f}",
                asset.location,
                asset.notes or ''
            ))

        self._update_status(f"Showing {len(assets)} assets")

    def _on_search_change(self, *args):
        """Handle search text change."""
        self._apply_filters()

    def _on_filter_change(self, event=None):
        """Handle filter dropdown change."""
        self._apply_filters()

    def _clear_filters(self):
        """Clear all search and filter fields."""
        self.search_var.set("")
        self.category_filter_var.set("All")
        self.location_filter_var.set("All")
        self._apply_filters()

    def _sort_column(self, column):
        """Sort table by column when header is clicked."""
        # Toggle sort direction if same column
        if column == self.sort_column:
            self.sort_descending = not self.sort_descending
        else:
            self.sort_column = column
            self.sort_descending = False

        # Get all items
        items = [(self.tree.set(item, column), item)
                 for item in self.tree.get_children('')]

        # Sort items
        try:
            # Try numeric sort for value column
            if column == 'estimated_value':
                items.sort(key=lambda x: float(x[0].replace(',', '')),
                           reverse=self.sort_descending)
            elif column == 'id':
                items.sort(key=lambda x: int(x[0]),
                           reverse=self.sort_descending)
            else:
                items.sort(key=lambda x: x[0].lower(),
                           reverse=self.sort_descending)
        except (ValueError, TypeError):
            items.sort(key=lambda x: x[0], reverse=self.sort_descending)

        # Rearrange items in sorted order
        for index, (_, item) in enumerate(items):
            self.tree.move(item, '', index)

    def _on_tree_select(self, event):
        """Handle tree selection change."""
        selection = self.tree.selection()
        if selection:
            self.delete_button.config(state=tk.NORMAL)
        else:
            self.delete_button.config(state=tk.DISABLED)
            self.selected_asset_id = None

    def _on_tree_double_click(self, event):
        """Handle double-click to edit asset."""
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            asset_id = int(item['values'][0])
            self._load_asset_for_edit(asset_id)

    def _load_asset_for_edit(self, asset_id: int):
        """Load an asset into the form for editing."""
        asset = self.service.get_asset(asset_id)
        if not asset:
            messagebox.showerror("Error", "Asset not found")
            return

        # Set edit mode
        self.edit_mode = True
        self.selected_asset_id = asset_id

        # Update UI for edit mode
        self.mode_label.config(text=f"Editing: {asset.item_name}")
        self.save_button.config(text="Update Asset")
        self.cancel_button.pack(side=tk.LEFT, padx=5)

        # Populate form fields
        self.item_name_var.set(asset.item_name)
        self.category_var.set(asset.category)
        self.serial_var.set(asset.serial_number or '')
        self.value_var.set(str(asset.estimated_value))
        self.location_var.set(asset.location)

        # Set notes
        self.notes_text.delete(1.0, tk.END)
        if asset.notes:
            self.notes_text.insert(1.0, asset.notes)

        # Focus on item name
        self.item_name_entry.focus()
        self._update_status(f"Editing asset: {asset.item_name}")

    def _cancel_edit(self):
        """Cancel edit mode and clear form."""
        self.edit_mode = False
        self.selected_asset_id = None
        self.mode_label.config(text="Add New Asset")
        self.save_button.config(text="Add Asset")
        self.cancel_button.pack_forget()
        self._clear_form()

    def _clear_form(self):
        """Clear all form fields."""
        self.item_name_var.set("")
        self.category_var.set("")
        self.serial_var.set("")
        self.value_var.set("")
        self.location_var.set("")
        self.notes_text.delete(1.0, tk.END)
        self.item_name_entry.focus()

        if not self.edit_mode:
            self._update_status("Form cleared")

    def _validate_form(self) -> tuple:
        """
        Validate form input.

        Returns:
            Tuple of (is_valid, error_message, form_data)
        """
        item_name = self.item_name_var.get().strip()
        category = self.category_var.get().strip()
        serial_number = self.serial_var.get().strip()
        value_str = self.value_var.get().strip()
        location = self.location_var.get().strip()
        notes = self.notes_text.get(1.0, tk.END).strip()

        # Check required fields
        if not item_name:
            return False, "Item name is required", None
        if not category:
            return False, "Category is required", None
        if not location:
            return False, "Location is required", None

        # Validate value
        try:
            estimated_value = float(value_str) if value_str else 0.0
            if estimated_value < 0:
                return False, "Estimated value cannot be negative", None
        except ValueError:
            return False, "Please enter a valid number for estimated value", None

        return True, "", {
            'item_name': item_name,
            'category': category,
            'serial_number': serial_number,
            'estimated_value': estimated_value,
            'location': location,
            'notes': notes
        }

    def _save_asset(self):
        """Save (add or update) an asset."""
        # Validate form
        is_valid, error_msg, form_data = self._validate_form()
        if not is_valid:
            messagebox.showerror("Validation Error", error_msg)
            return

        if self.edit_mode and self.selected_asset_id:
            # Update existing asset
            success, message = self.service.update_asset(
                asset_id=self.selected_asset_id,
                **form_data
            )
        else:
            # Add new asset
            success, message, _ = self.service.add_asset(**form_data)

        if success:
            messagebox.showinfo("Success", message)
            self._cancel_edit()  # Reset form
            self._refresh_display()
        else:
            messagebox.showerror("Error", message)

    def _delete_asset(self):
        """Delete the selected asset."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an asset to delete")
            return

        item = self.tree.item(selection[0])
        asset_id = int(item['values'][0])
        asset_name = item['values'][1]

        # Confirm deletion
        confirmed = messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete '{asset_name}'?\n\n"
            "This action cannot be undone."
        )

        if confirmed:
            success, message = self.service.delete_asset(asset_id)
            if success:
                # If we were editing this asset, cancel edit mode
                if self.selected_asset_id == asset_id:
                    self._cancel_edit()
                self._refresh_display()
                self._update_status(message)
            else:
                messagebox.showerror("Error", message)

    def _export_csv(self):
        """Export assets to CSV file."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="assets_export.csv",
            title="Export Assets to CSV"
        )

        if file_path:
            success, message, count = self.service.export_to_csv(file_path)
            if success:
                messagebox.showinfo("Export Complete", message)
                self._update_status(f"Exported {count} assets to CSV")
            else:
                messagebox.showerror("Export Error", message)

    def _backup_database(self):
        """Create a database backup."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".db",
            filetypes=[("SQLite Database", "*.db"), ("All files", "*.*")],
            initialfile="inventory_backup.db",
            title="Backup Database"
        )

        if file_path:
            try:
                backup_path = self.service.backup_database(file_path)
                messagebox.showinfo("Backup Complete",
                                    f"Database backed up to:\n{backup_path}")
                self._update_status("Database backup created")
            except Exception as e:
                messagebox.showerror("Backup Error", f"Failed to create backup: {e}")

    def _update_status(self, message: str):
        """Update the status bar message."""
        self.status_var.set(message)

    def run(self):
        """Start the GUI application."""
        self.root.mainloop()


def main():
    """Main entry point for the GUI application."""
    app = AssetInventoryGUI()
    app.run()


if __name__ == "__main__":
    main()
