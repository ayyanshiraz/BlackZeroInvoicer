import webview
import webbrowser
import sys
import os
import json
from pathlib import Path
from flask import Flask, render_template, request, make_response, send_file, jsonify, redirect, url_for
from fpdf import FPDF
from datetime import datetime

app = Flask(__name__)

# --- Company Constants ---
COMPANY_NAME = "BLACK ZERO"
COMPANY_SUBTITLE = "Marketing and IT Solutions Company"
COMPANY_ADDRESS_1 = "50-52, E - III, Al Fateh Ln."
COMPANY_ADDRESS_2 = "Commercial Area Gulberg III, Lahore."
COMPANY_LOGO_PATH = "templates/logo.png"
TERMS = "50% advance payment is required to commence the project. The remaining 50% is due upon project completion, prior to final delivery. This is not refundable after 24 hours."

# --- State Files (Modified for Executable) ---
# Find the user's home directory
HOME_DIR = Path.home()
# Create a dedicated folder for our app's data
DATA_DIR = HOME_DIR / ".BlackZeroInvoicer"

# Create the directory if it doesn't exist
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except Exception as e:
    print(f"Warning: Could not create data directory at {DATA_DIR}: {e}")

# Point state files to this new directory
CLIENT_FILE = DATA_DIR / "clients.json"
COUNTER_FILE = DATA_DIR / "invoice_counter.json"
INVOICES_DB_FILE = DATA_DIR / "invoices.json"

# --- Bank Account Details ---
BANK_ACCOUNTS = {
    "hashim_mcb": { "name": "M Hashim Haroon", "bank": "MCB BANK", "number": "1570096861011575" },
    "ayyan_meezan": { "name": "Ayyan Shiraz", "bank": "Meezan Bank", "number": "0256-0107101539" },
    "blackzero_faysal": { "name": "Black Zero", "bank": "Faysal Bank", "number": "3424301000004754" }
}

# --- Dynamic Footer Line Profiles ---
CONTACT_PROFILES = {
    "Main Hashim Haroon": {
        "line": "M Hashim Haroon | CEO | +92 324 4333267 | info@blackzero.org | www.blackzero.org"
    },
    "Ayyan Shiraz": {
        "line": "Ayyan Shiraz | Marketing and IT Manager | +92 333 4888324 | marketinghead@blackzero.org | www.blackzero.org"
    }
}

# --- Helper Functions for JSON Data ---
def load_json(filename, default_data):
    if not os.path.exists(filename):
        save_json(filename, default_data)
        return default_data
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
            if not data: # Handle empty file
                return default_data
            return data
    except (json.JSONDecodeError, FileNotFoundError):
        return default_data

def save_json(filename, data):
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
    except IOError as e:
        print(f"Error saving JSON file {filename}: {e}")

# --- Helper Function for Invoice Number ---
def get_next_invoice_num(client_name):
    clients_data = load_json(CLIENT_FILE, {})
    counter_data = load_json(COUNTER_FILE, {"last_client_id": 0})
    
    client_name = client_name.strip()
    client_data = clients_data.get(client_name)
    
    if not client_data:
        # FIX: Use .get() for safety
        last_id = counter_data.get('last_client_id', 0)
        client_id_str = f"{last_id + 1:04d}"
        invoice_count = 1
    else:
        client_id_str = client_data.get('client_id', '0000')
        invoice_count = client_data.get('invoice_count', 0) + 1
        
    return f"{client_id_str}-{invoice_count:02d}"

# --- PDF Class (Footer is Rebuilt) ---
class PDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.payment_status = ""
        self.selected_bank_details = {}
        self.footer_line = ""

    def header(self):
        # Header is drawn manually
        pass

    # --- FIX: Rebuilt Footer ---
    def footer(self):
        self.set_y(-70) # Position 70mm from bottom
        start_y = self.get_y()
        
        # --- 1. Calculate Heights (Draw text invisibly) ---
        # Store current X, Y
        temp_x = self.get_x()
        temp_y = self.get_y()

        # Left Box Height
        self.set_text_color(255, 255, 255) # Make text invisible
        self.set_font('Arial', 'B', 10)
        self.cell(85, 8, 'Payable To', 0, 1, 'L')
        self.set_font('Arial', '', 9)
        self.cell(85, 5, "Line 2", 0, 1, 'L') 
        self.set_font('Arial', 'B', 10)
        self.cell(85, 5, 'Bank Details', 0, 1, 'L')
        self.set_font('Arial', '', 9)
        self.cell(85, 5, "Line 4", 0, 1, 'L')
        self.set_font('Arial', 'B', 10)
        self.cell(85, 5, 'Payment Status', 0, 1, 'L')
        self.set_font('Arial', 'B', 10) 
        self.cell(85, 6, "Line 6", 0, 1, 'L')
        left_y_end = self.get_y()
        left_box_height = left_y_end - start_y
        
        # Right Box Height
        self.set_xy(105, start_y) # Set X, Y
        self.set_font('Arial', 'B', 10)
        self.cell(95, 8, 'Terms and conditions:', 0, 1, 'L')
        self.set_font('Arial', '', 9)
        self.set_x(105) # Reset X for multi-cell
        self.multi_cell(95, 5, TERMS, 0, 'L')
        right_y_end = self.get_y()
        right_box_height = right_y_end - start_y
        
        # Reset text color and position
        self.set_text_color(0, 0, 0)
        self.set_xy(temp_x, temp_y)
        
        # Get max height + padding
        box_height = max(left_box_height, right_box_height) + 2
        
        # --- 2. Draw Grey Boxes ---
        self.set_fill_color(230, 230, 230)
        self.rect(10, start_y, 85, box_height, 'F') # Left box
        self.rect(105, start_y, 95, box_height, 'F') # Right box
        
        # --- 3. Draw Text ON TOP ---
        # Left Box Text
        self.set_xy(10, start_y)
        self.set_font('Arial', 'B', 10)
        self.cell(85, 8, 'Payable To', 0, 1, 'L')
        self.set_font('Arial', '', 9)
        self.cell(85, 5, self.selected_bank_details.get('name', ''), 0, 1, 'L') 
        self.set_font('Arial', 'B', 10)
        self.cell(85, 5, 'Bank Details', 0, 1, 'L')
        self.set_font('Arial', '', 9)
        self.cell(85, 5, f"{self.selected_bank_details.get('bank', '')} | {self.selected_bank_details.get('number', '')}", 0, 1, 'L')
        self.set_font('Arial', 'B', 10)
        self.cell(85, 5, 'Payment Status', 0, 1, 'L')
        self.set_font('Arial', 'B', 10) 
        self.cell(85, 6, self.payment_status.upper(), 0, 1, 'L')

        # Right Box Text
        self.set_xy(105, start_y)
        self.set_font('Arial', 'B', 10)
        self.cell(95, 8, 'Terms and conditions:', 0, 1, 'L')
        self.set_font('Arial', '', 9)
        self.set_x(105) # Reset X for multi-cell
        self.multi_cell(95, 5, TERMS, 0, 'L')

        # --- Single-Line Footer Bar ---
        self.set_y(-15) # 15mm from bottom
        self.set_fill_color(50, 50, 50)
        self.set_text_color(255, 255, 255)
        self.set_font('Arial', 'B', 8)
        self.cell(0, 8, self.footer_line, 0, 0, 'C', fill=True)


# --- Central PDF Creation Function ---
def create_pdf_from_data(invoice_data):
    default_profile = CONTACT_PROFILES['Main Hashim Haroon']
    selected_contact_profile = CONTACT_PROFILES.get(invoice_data['paid_to'], default_profile)
    selected_bank_details = BANK_ACCOUNTS.get(invoice_data['bank_key'], BANK_ACCOUNTS['hashim_mcb'])

    pdf = PDF('P', 'mm', 'A4')
    pdf.payment_status = invoice_data['payment_status']
    pdf.selected_bank_details = selected_bank_details
    pdf.footer_line = selected_contact_profile.get('line', '')
    pdf.add_page()
    
    # Draw Manual Header
    if os.path.exists(COMPANY_LOGO_PATH):
        pdf.image(COMPANY_LOGO_PATH, 10, 8, 28)
    pdf.set_y(13)
    pdf.set_x(0)
    pdf.set_font('Arial', 'B', 20)
    pdf.cell(0, 10, COMPANY_NAME, 0, 2, 'C')
    pdf.set_x(0)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 7, COMPANY_SUBTITLE, 0, 2, 'C')
    pdf.set_y(35) 
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 5, COMPANY_ADDRESS_1, 0, 1, 'L')
    pdf.cell(0, 5, COMPANY_ADDRESS_2, 0, 1, 'L')
    
    # Draw Client & Invoice Details Block (Parallel)
    y_start_block = 55
    pdf.set_y(y_start_block) 
    
    # --- Left Column (Bill To) ---
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(100, 8, f"Bill To: {invoice_data['client_name']}", 0, 1, 'L')
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(100, 5, f"Business: {invoice_data['client_business']}", 0, 1, 'L')
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(100, 5, "Address:", 0, 1, 'L')
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(100, 5, invoice_data['client_address'], 0, 'L')
    
    # --- FIX: Client Phone Layout ---
    pdf.set_x(10) # Set X to left margin
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(100, 5, f"Phone: {invoice_data['client_phone']}", 0, 1, 'L')
    y_after_left = pdf.get_y()

    # --- Right Column (Quotation) ---
    pdf.set_y(y_start_block)
    pdf.set_x(110)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(90, 8, "QUOTATION", 0, 1, 'R')
    pdf.set_font('Arial', '', 10)
    pdf.set_x(110)
    pdf.cell(90, 5, f"DATE: {invoice_data['date_str']}", 0, 1, 'R')
    pdf.set_x(110)
    pdf.cell(90, 5, f"TIME: {invoice_data['time_str']}", 0, 1, 'R')
    pdf.set_x(110)
    pdf.cell(90, 5, f"INVOICE #: {invoice_data['invoice_num']}", 0, 1, 'R')
    y_after_right = pdf.get_y()

    pdf.set_y(max(y_after_left, y_after_right) + 10)
    
    # Add Items Table
    pdf.set_font('Arial', 'B', 10)
    pdf.set_fill_color(34, 34, 34)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(95, 10, 'ITEM DESCRIPTION', 1, 0, 'L', fill=True)
    # --- NEW: Use qty_label ---
    pdf.cell(30, 10, invoice_data['qty_label'].upper(), 1, 0, 'C', fill=True)
    pdf.cell(35, 10, 'RATE', 1, 0, 'C', fill=True)
    pdf.cell(30, 10, 'PRICE', 1, 1, 'C', fill=True)
    
    pdf.set_fill_color(240, 240, 240)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', '', 10)
    
    subtotal = 0
    for item in invoice_data['line_items']:
        qty = item['qty']
        rate = item['rate']
        price = qty * rate
        subtotal += price
        
        if pdf.get_y() > 210:
            pdf.add_page()
        
        pdf.cell(95, 10, item['desc'], 1, 0, 'L', fill=True)
        pdf.cell(30, 10, f"{qty:,.2f}", 1, 0, 'C', fill=True)
        pdf.cell(35, 10, f"{rate:,.2f}", 1, 0, 'R', fill=True)
        pdf.cell(30, 10, f"{price:,.2f}", 1, 1, 'R', fill=True)
        
    # Add Totals Section
    pdf.ln(5) 
    tax_rate = 0.0 
    tax = subtotal * tax_rate
    grand_total = subtotal + tax
    paid_amount = invoice_data['paid_amount']
    remaining_due = grand_total - paid_amount
    
    pdf.set_font('Arial', 'B', 10)
    num_rows = 4 
    if tax > 0: num_rows = 5
    
    totals_y = pdf.get_y()
    if totals_y + (num_rows * 10) > 210:
        pdf.add_page()
        totals_y = pdf.get_y()

    pdf.set_fill_color(240, 240, 240)
    pdf.multi_cell(190, 10 * num_rows, "", 0, 'L', fill=True)
    pdf.set_y(totals_y) 

    pdf.cell(160, 10, 'SUBTOTAL', 0, 0, 'R')
    pdf.cell(30, 10, f"{subtotal:,.2f}", 0, 1, 'R')
    if tax > 0:
        pdf.cell(160, 10, f"TAX ({tax_rate * 100}%)", 0, 0, 'R')
        pdf.cell(30, 10, f"{tax:,.2f}", 0, 1, 'R')
    pdf.cell(160, 10, 'GRAND TOTAL', 0, 0, 'R')
    pdf.cell(30, 10, f"{grand_total:,.2f}", 0, 1, 'R')
    pdf.cell(160, 10, 'AMOUNT PAID', 0, 0, 'R')
    pdf.cell(30, 10, f"{paid_amount:,.2f}", 0, 1, 'R')
    pdf.cell(160, 10, 'REMAINING DUE', 0, 0, 'R')
    pdf.cell(30, 10, f"{remaining_due:,.2f}", 0, 1, 'R')
    
    # Generate and send the PDF
    output_filename = f"temp_invoice_{invoice_data['invoice_num']}.pdf"
    pdf.output(output_filename)
    
# ... at the end of create_pdf_from_data ...
    # Generate and save the PDF
    output_filename = f"temp_invoice_{invoice_data['invoice_num']}.pdf"
    pdf.output(output_filename)
    
    # Return the full, absolute path to the file
    return os.path.abspath(output_filename)
    

# --- Flask Routes (Updated) ---

@app.route('/')
def index():
    clients_data = load_json(CLIENT_FILE, {})
    client_data_by_name = {}
    client_data_by_business = {}
    
    for name, data in clients_data.items():
        address = data.get('address', '')
        business = data.get('business', '')
        phone = data.get('phone', '')
        client_data_by_name[name] = {"address": address, "business": business, "phone": phone}
        if business:
            client_data_by_business[business] = {"name": name, "address": address, "phone": phone}

    return render_template(
        'index.html', 
        client_data_by_name=client_data_by_name,
        client_data_by_business=client_data_by_business,
        client_data_by_name_json=json.dumps(client_data_by_name),
        client_data_by_business_json=json.dumps(client_data_by_business)
    )

@app.route('/get-next-invoice-num')
def get_invoice_num_route():
    client_name = request.args.get('client_name')
    if not client_name:
        return jsonify({"error": "No client name provided"}), 400
    
    try:
        invoice_num = get_next_invoice_num(client_name)
        return jsonify({"invoice_num": invoice_num})
    except Exception as e:
        print(f"Error in get_invoice_num_route: {e}")
        # Return an error JSON to the frontend
        return jsonify({"error": str(e)}), 500

@app.route('/generate-pdf', methods=['POST'])
def generate_pdf():
    try:
        form_data = request.form
        client_name = form_data['client_name'].strip()
        client_address = form_data['client_address']
        client_business = form_data.get('client_business', '')
        client_phone = form_data.get('client_phone', '')
        
        paid_to = form_data['paid_to']
        payment_status = form_data['payment_status']
        bank_key = form_data['bank_account']
        qty_label = form_data.get('qty_label', 'QTY') # NEW
        
        paid_amount_str = request.form.get('paid_amount', '0')
        paid_amount = float(paid_amount_str or 0) 

        descriptions = request.form.getlist('item_desc[]')
        quantities = request.form.getlist('item_qty[]')
        rates = request.form.getlist('item_rate[]')

        # Invoice Number Logic
        clients_data = load_json(CLIENT_FILE, {})
        counter_data = load_json(COUNTER_FILE, {"last_client_id": 0})
        client_data = clients_data.get(client_name)
        
        if not client_data:
            # FIX: Use .get() for safety
            last_id = counter_data.get('last_client_id', 0)
            new_client_id = last_id + 1
            client_id_str = f"{new_client_id:04d}"
            invoice_count = 1
            counter_data['last_client_id'] = new_client_id
            save_json(COUNTER_FILE, counter_data)
        else:
            client_id_str = client_data.get('client_id', '0000')
            invoice_count = client_data.get('invoice_count', 0) + 1
        
        invoice_num = f"{client_id_str}-{invoice_count:02d}"
        
        clients_data[client_name] = {
            "address": client_address,
            "business": client_business,
            "phone": client_phone,
            "client_id": client_id_str,
            "invoice_count": invoice_count
        }
        save_json(CLIENT_FILE, clients_data)

        # Compile all data
        line_items = []
        grand_total = 0
        for i in range(len(descriptions)):
            try: qty = float(quantities[i])
            except (ValueError, TypeError): qty = 0
            try: rate = float(rates[i])
            except (ValueError, TypeError): rate = 0
            grand_total += (qty * rate)
            line_items.append({"desc": descriptions[i], "qty": qty, "rate": rate})
            
        now = datetime.now()
        
        invoice_data = {
            "invoice_num": invoice_num,
            "client_name": client_name,
            "client_address": client_address,
            "client_business": client_business,
            "client_phone": client_phone,
            "paid_to": paid_to,
            "payment_status": payment_status,
            "bank_key": bank_key,
            "paid_amount": paid_amount,
            "line_items": line_items,
            "grand_total": grand_total,
            "qty_label": qty_label, # NEW
            "date_time_str": now.strftime('%m/%d/%Y %I:%M %p'),
            "date_str": now.strftime('%m/%d/%Y'),
            "time_str": now.strftime('%I:%M %p')
        }
        
        # Save to Invoice Database
        invoices_db = load_json(INVOICES_DB_FILE, [])
        invoices_db.append(invoice_data)
        save_json(INVOICES_DB_FILE, invoices_db)
        
        ## ... at the end of generate_pdf ...
        # Create the PDF and get its file path
        pdf_file_path = create_pdf_from_data(invoice_data)
        
        # Open the PDF in the default system viewer (e.g., Evince)
        # We use 'file://' to ensure it's treated as a local file URL
        webbrowser.open(f'file://{pdf_file_path}')
        
        # Redirect the webview back to the main page
        return redirect(url_for('index'))

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
        return "An internal server error occurred. Please check the terminal.", 500

# --- Routes for Searching and Viewing ---
@app.route('/search-invoices')
def search_invoices():
    query = request.args.get('query', '').lower()
    if not query:
        return jsonify([])
    
    invoices_db = load_json(INVOICES_DB_FILE, [])
    results = []
    
    for invoice in invoices_db:
        if (query in invoice['invoice_num'].lower() or
            query in invoice['client_name'].lower() or
            query in invoice['client_business'].lower() or
            query in invoice['client_phone'].lower()):
            
            results.append(invoice)
            
    results.reverse() # Show newest first
    return jsonify(results)

@app.route('/view-invoice/<invoice_num>')
def view_invoice(invoice_num):
    invoices_db = load_json(INVOICES_DB_FILE, [])
    
    for invoice in invoices_db:
        if invoice['invoice_num'] == invoice_num:
            # Create the PDF from data and get its path
            pdf_file_path = create_pdf_from_data(invoice)
            
            # Open it in the default system viewer
            webbrowser.open(f'file://{pdf_file_path}')
            
            # We can't redirect, but we must return a valid
            # response so the app doesn't crash.
            return "Opening PDF in external viewer..."
            
    return "Invoice not found.", 404


if __name__ == '__main__':
    # pywebview will create a new native window
    # It will load the 'app' (your Flask app)
    # This automatically handles starting/stopping the server
    window = webview.create_window(
        'Black Zero Invoicer',  # Window title
        app                     # Your Flask app
    )

    # Run the app. 
    # Set debug=False for the final build, but True is ok for testing.
    webview.start(debug=False)