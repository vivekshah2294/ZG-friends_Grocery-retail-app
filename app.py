import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import uuid
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
import os
import time
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Zin & Gin Retail", layout="wide", initial_sidebar_state="collapsed")

# --- CSS STYLING ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    div[data-testid="stButton"] button {
        height: 3rem; font-weight: bold; border-radius: 8px; width: 100%;
    }
    @media (max-width: 576px) {
        [data-testid="stHorizontalBlock"] {
            flex-direction: row !important; flex-wrap: nowrap !important; align-items: center !important; gap: 0.25rem !important;
        }
        [data-testid="column"] {
            width: auto !important; flex: 1 1 0% !important; min-width: 0 !important; padding: 0 !important;
        }
    }
    </style>
""", unsafe_allow_html=True)

# --- LOCAL DATABASE INITIALIZATION ---
@st.cache_resource
def get_db_connection():
    conn = sqlite3.connect("retail_orders.db", check_same_thread=False)
    
    # Create Tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Users (
            email TEXT PRIMARY KEY,
            name TEXT,
            password_hash TEXT,
            role TEXT,
            balance REAL DEFAULT 0.0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            item_name TEXT,
            pack_size TEXT,
            jamoona_price REAL,
            friends_price REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Orders (
            order_id TEXT PRIMARY KEY,
            date TEXT,
            user_email TEXT,
            total_amount REAL,
            payment_method TEXT,
            status TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS OrderLineItems (
            line_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT,
            item_name TEXT,
            qty INTEGER,
            unit_price REAL,
            subtotal REAL,
            FOREIGN KEY(order_id) REFERENCES Orders(order_id)
        )
    """)
    
    # Seed Admin User if not exists
    admin_email = "zinandgin@gmail.com"
    admin_pass = hashlib.sha256("admin123".encode()).hexdigest()
    conn.execute("INSERT OR IGNORE INTO Users (email, name, password_hash, role) VALUES (?, ?, ?, ?)", 
                 (admin_email, "Admin", admin_pass, "Admin"))
    
    # Seed Catalog if empty
    if pd.read_sql("SELECT COUNT(*) FROM Catalog", conn).iloc[0,0] == 0:
        dummy_catalog = [
            ("Dals & Legumes", "Toor Dal (KRG / Kamal)", "1 kg", 4.19, 3.30),
            ("Whole Spices", "Jeera Whole (KRG)", "400 g", 5.19, 4.20),
            ("Flours & Grains", "Aashirwaad Atta", "10 kg", 16.49, 15.65)
        ]
        conn.executemany("INSERT INTO Catalog (category, item_name, pack_size, jamoona_price, friends_price) VALUES (?, ?, ?, ?, ?)", dummy_catalog)
    
    conn.commit()
    return conn

conn = get_db_connection()

# --- HELPER FUNCTIONS ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def update_cart(item, price, delta):
    current = st.session_state.cart.get(item, {"qty": 0, "price": price})
    new_qty = max(0, current["qty"] + delta)
    if new_qty == 0:
        if item in st.session_state.cart:
            del st.session_state.cart[item]
    else:
        st.session_state.cart[item] = {"qty": new_qty, "price": price}

def send_admin_email_alert(order_id, user_name, total_amount, method):
    # Requires st.secrets to be configured with an app password
    try:
        if "email" in st.secrets:
            sender = st.secrets["email"]["sender"]
            pwd = st.secrets["email"]["password"]
            receiver = "zinandgin@gmail.com"
            
            body = f"New order placed by {user_name}!\n\nOrder ID: {order_id}\nTotal: €{total_amount:.2f}\nMethod: {method}\n\nLog into the Admin portal to view details."
            msg = MIMEText(body)
            msg["Subject"] = f"🛒 New Retail Order: €{total_amount:.2f}"
            msg["From"] = f"Zin & Gin Retail <{sender}>"
            msg["To"] = receiver
            
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(sender, pwd)
                server.send_message(msg)
    except Exception as e:
        print(f"Email failed: {e}")

def automated_db_backup(db_path="retail_orders.db", backup_interval_hours=48):
    """Silently emails the retail_orders.db file to the admin if 48 hours have passed."""
    try:
        tracker_file = "last_retail_backup.txt"
        current_time = time.time()
        
        # Check if enough time has passed since the last backup
        if os.path.exists(tracker_file):
            with open(tracker_file, "r") as f:
                last_backup = float(f.read().strip())
            if (current_time - last_backup) < (backup_interval_hours * 3600):
                return
        
        # Prepare and send the email with the database attached
        if "email" in st.secrets and os.path.exists(db_path):
            sender = st.secrets["email"]["sender"]
            pwd = st.secrets["email"]["password"]
            receiver = "zinandgin@gmail.com"
            
            msg = MIMEMultipart()
            msg["Subject"] = f"Zin & Gin Retail DB Backup - {datetime.today().strftime('%Y-%m-%d')}"
            msg["From"] = f"Zin & Gin Retail <{sender}>"
            msg["To"] = receiver
            
            body = MIMEText("Attached is your automated Zin & Gin Retail database backup. Keep this safe to restore your friends' balances and order history if the cloud server restarts.")
            msg.attach(MIMEText(body, 'plain'))
            
            with open(db_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(db_path)}")
            msg.attach(part)
            
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(sender, pwd)
                server.send_message(msg)
                
            # Log the successful backup time
            with open(tracker_file, "w") as f:
                f.write(str(current_time))
                
    except Exception:
        pass 

# --- SESSION STATE INITIALIZATION ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_email = ""
    st.session_state.user_name = ""
    st.session_state.user_role = ""
if 'cart' not in st.session_state:
    st.session_state.cart = {}
if 'nav_selection' not in st.session_state:
    st.session_state.nav_selection = "Catalog"

# --- PAGE: LOGIN / SIGNUP ---
def page_login():
    st.title("🔐 Zin & Gin Retail Portal")
    
    tab1, tab2 = st.tabs(["Log In", "Create Account"])
    
    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email Address").lower()
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Log In", type="primary"):
                hashed_pw = hash_password(password)
                user = pd.read_sql("SELECT * FROM Users WHERE email=? AND password_hash=?", conn, params=(email, hashed_pw))
                
                if not user.empty:
                    st.session_state.logged_in = True
                    st.session_state.user_email = user.iloc[0]['email']
                    st.session_state.user_name = user.iloc[0]['name']
                    st.session_state.user_role = user.iloc[0]['role']
                    st.session_state.nav_selection = "Catalog" if user.iloc[0]['role'] == "Customer" else "Admin Dashboard"
                    st.rerun()
                else:
                    st.error("Invalid credentials.")

    with tab2:
        with st.form("signup_form"):
            new_name = st.text_input("Full Name")
            new_email = st.text_input("Email Address").lower()
            new_password = st.text_input("Create Password", type="password")
            if st.form_submit_button("Create Account"):
                if new_name and new_email and len(new_password) > 3:
                    try:
                        conn.execute("INSERT INTO Users (email, name, password_hash, role) VALUES (?, ?, ?, ?)",
                                     (new_email, new_name, hash_password(new_password), "Customer"))
                        conn.commit()
                        st.success("Account created successfully! You can now log in.")
                    except sqlite3.IntegrityError:
                        st.error("An account with this email already exists.")
                else:
                    st.error("Please fill all fields.")

# --- PAGE: CUSTOMER ORDERING CATALOG ---
def page_order():
    st.title(f"👋 Hi, {st.session_state.user_name}!")
    st.write("Browse the catalog and tap to add items to your cart.")
    
    df_catalog = pd.read_sql("SELECT * FROM Catalog", conn)
    
    if df_catalog.empty:
        st.warning("Catalog is empty.")
        return

    for category in df_catalog['category'].unique():
        with st.expander(f"🛒 {category}", expanded=True):
            cat_items = df_catalog[df_catalog['category'] == category]
            
            c_name, c_jamoona, c_price, c_actions = st.columns([4, 2, 2, 3])
            c_name.markdown("**Item**")
            c_jamoona.markdown("**Jamoona**")
            c_price.markdown("**Our Price**")
            st.divider()
            
            for _, row in cat_items.iterrows():
                item_name = str(row['item_name'])
                pack = str(row['pack_size'])
                jamoona = row['jamoona_price']
                price = row['friends_price']
                
                current_qty = st.session_state.cart.get(item_name, {}).get("qty", 0)
                
                c1, c2, c3, c4 = st.columns([4, 2, 2, 3])
                
                display_name = f"{item_name} ({pack})"
                if current_qty > 0:
                     display_name += f"   🟢 **{current_qty}**"
                c1.write(display_name)
                c2.markdown(f"<span style='color:red; text-decoration:line-through;'>€{jamoona:.2f}</span>", unsafe_allow_html=True)
                c3.markdown(f"**€{price:.2f}**")
                
                ac1, ac2 = c4.columns(2)
                with ac1:
                    st.button("➖", key=f"sub_{item_name}", on_click=update_cart, args=(item_name, price, -1))
                with ac2:
                    st.button("➕", key=f"add_{item_name}", on_click=update_cart, args=(item_name, price, 1))
                
                st.markdown("<hr style='margin: 0.5rem 0; opacity: 0.2;'>", unsafe_allow_html=True)

    # --- DYNAMIC REVIEW CART BUTTON ---
    if st.session_state.cart:
        st.markdown("<br>", unsafe_allow_html=True)
        st.divider()
        
        cart_qty = sum(item["qty"] for item in st.session_state.cart.values())
        cart_total = sum(item["qty"] * item["price"] for item in st.session_state.cart.values())
        
        c_tot, c_btn = st.columns([1, 1])
        with c_tot:
            st.markdown(f"### 🛒 {cart_qty} items | €{cart_total:.2f}")
        with c_btn:
            if st.button("Review Cart & Checkout ➡️", type="primary", use_container_width=True):
                st.session_state.nav_selection = "Cart / Checkout"
                st.rerun()

# --- PAGE: CUSTOMER CART & CHECKOUT ---
def page_cart():
    st.title("🛍️ Order Summary")
    
    if not st.session_state.cart:
        st.info("Your cart is empty.")
        if st.button("⬅️ Back to Catalog"):
            st.session_state.nav_selection = "Catalog"
            st.rerun()
        return
        
    cart_items = []
    total_due = 0.0
    
    for item, data in st.session_state.cart.items():
        qty = data["qty"]
        price = data["price"]
        subtotal = qty * price
        total_due += subtotal
        cart_items.append({"item_name": item, "qty": qty, "unit_price": price, "subtotal": subtotal})
        
    st.dataframe(pd.DataFrame(cart_items), hide_index=True, use_container_width=True)
    st.markdown(f"### Total Due: €{total_due:.2f}")
    
    payment_method = st.radio("Payment Method", ["Add to my Tab (Settle End of Month)", "Tikkie / Pay Now"])
    
    if st.button("✅ Place Order", type="primary", use_container_width=True):
        order_id = str(uuid.uuid4())[:8].upper()
        order_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Write Order
        conn.execute("INSERT INTO Orders (order_id, date, user_email, total_amount, payment_method, status) VALUES (?, ?, ?, ?, ?, ?)",
                     (order_id, order_date, st.session_state.user_email, total_due, payment_method, "Open"))
        
        # Write Line Items
        for item in cart_items:
            conn.execute("INSERT INTO OrderLineItems (order_id, item_name, qty, unit_price, subtotal) VALUES (?, ?, ?, ?, ?)",
                         (order_id, item["item_name"], item["qty"], item["unit_price"], item["subtotal"]))
        
        # Update User Balance
        conn.execute("UPDATE Users SET balance = balance + ? WHERE email = ?", (total_due, st.session_state.user_email))
        conn.commit()
        
        send_admin_email_alert(order_id, st.session_state.user_name, total_due, payment_method)
        
        st.session_state.last_order = {"id": order_id, "total": total_due, "method": payment_method}
        st.session_state.cart = {}
        st.rerun()

def page_confirmation():
    order = st.session_state.last_order
    st.success("🎉 Order Placed Successfully!")
    st.markdown(f"### Invoice Summary\n* **Order ID:** {order['id']}\n* **Total Amount Due:** €{order['total']:.2f}\n* **Payment Method:** {order['method']}")
    if st.button("Return to Catalog"):
        del st.session_state.last_order
        st.session_state.nav_selection = "Catalog"
        st.rerun()

# --- PAGE: MY PAST ORDERS (CUSTOMER VIEW) ---
def page_customer_orders():
    st.title("📜 My Past Orders")
    st.write("Review your historical purchases.")
    
    df_orders = pd.read_sql("SELECT order_id, date, total_amount, status FROM Orders WHERE user_email=? ORDER BY date DESC", conn, params=(st.session_state.user_email,))
    
    if df_orders.empty:
        st.info("You haven't placed any orders yet.")
        return
        
    for _, order in df_orders.iterrows():
        status_icon = "🟢" if order['status'] == "Settled" else "🔴"
        with st.expander(f"📦 Order {order['order_id']} | {order['date']} | €{order['total_amount']:.2f} {status_icon}"):
            items = pd.read_sql("SELECT item_name, qty, unit_price, subtotal FROM OrderLineItems WHERE order_id=?", conn, params=(order['order_id'],))
            st.dataframe(items, hide_index=True, use_container_width=True)

# --- PAGE: ADMIN DASHBOARD ---
def page_admin():
    st.title("🛡️ Admin Dashboard")
    
    tab1, tab2, tab3 = st.tabs(["Friend Dossiers", "All Orders", "Catalog Manager"])
    
    with tab1:
        st.subheader("Open Tabs & User Balances")
        df_users = pd.read_sql("SELECT name, email, balance FROM Users WHERE role='Customer'", conn)
        st.dataframe(df_users, hide_index=True, use_container_width=True)
        
        with st.expander("Settle a Balance"):
            with st.form("settle_form"):
                user_to_settle = st.selectbox("Select Friend", df_users['email'].tolist())
                if st.form_submit_button("Mark Tab as Paid (Reset to €0)"):
                    conn.execute("UPDATE Users SET balance = 0.0 WHERE email = ?", (user_to_settle,))
                    conn.execute("UPDATE Orders SET status = 'Settled' WHERE user_email = ? AND status = 'Open'", (user_to_settle,))
                    conn.commit()
                    st.success("Balance settled!")
                    st.rerun()
                    
    with tab2:
        st.subheader("Order History")
        df_orders = pd.read_sql("SELECT order_id, date, user_email, total_amount, status FROM Orders ORDER BY date DESC", conn)
        st.dataframe(df_orders, hide_index=True, use_container_width=True)
        
    with tab3:
        st.subheader("Manage Catalog")
        df_cat = pd.read_sql("SELECT * FROM Catalog", conn)
        edited_cat = st.data_editor(df_cat, num_rows="dynamic", use_container_width=True, hide_index=True)
        if st.button("Save Catalog Changes"):
            edited_cat.to_sql("Catalog", conn, if_exists="replace", index=False)
            st.success("Catalog updated!")

# --- MAIN ROUTING ---
if not st.session_state.logged_in:
    page_login()
else:
    # Sidebar Profile & Navigation Setup
    if st.session_state.user_role == "Customer":
        nav_options = ["Catalog", "Cart / Checkout", "My Past Orders"]
    else:
        nav_options = ["Admin Dashboard", "Catalog", "Cart / Checkout"]

    # Security fallback in case state gets out of sync
    if st.session_state.nav_selection not in nav_options:
        st.session_state.nav_selection = nav_options[0]

    with st.sidebar:
        st.write(f"👤 **{st.session_state.user_name}**")
        
        if st.session_state.user_role == "Customer":
            user_balance = pd.read_sql("SELECT balance FROM Users WHERE email=?", conn, params=(st.session_state.user_email,)).iloc[0,0]
            st.write(f"💼 Open Tab: **€{user_balance:.2f}**")
        else:
            st.write("🛡️ **Admin Account**")
            automated_db_backup() # Silently fires backup if 48hrs passed
            
        st.divider()
        
        # Link radio button strictly to session state for programmatic navigation
        st.radio("Navigation", nav_options, key="nav_selection")

        if st.button("Log Out"):
            st.session_state.logged_in = False
            st.session_state.cart = {}
            if 'last_order' in st.session_state:
                del st.session_state.last_order
            st.rerun()

    # View Router uses the session state variable driven by both Sidebar OR Page Buttons
    active_nav = st.session_state.nav_selection

    if 'last_order' in st.session_state:
        page_confirmation()
    elif active_nav == "Catalog":
        page_order()
    elif active_nav == "Cart / Checkout":
        page_cart()
    elif active_nav == "My Past Orders":
        page_customer_orders()
    elif active_nav == "Admin Dashboard":
        page_admin()
