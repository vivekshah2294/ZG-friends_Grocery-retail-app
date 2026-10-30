import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import uuid
from datetime import datetime, date
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
import time
import plotly.express as px

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Zin & Gin Retail | Friends Grocery", layout="wide", initial_sidebar_state="collapsed")

# --- MOBILE UI OPTIMIZATION CSS ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 2rem; padding-left: 0.75rem; padding-right: 0.75rem; }
    
    div[data-testid="stButton"] button, div[data-testid="stPopover"] button {
        height: 2.8rem; font-weight: bold; border-radius: 6px; width: 100%;
    }
    
    /* Aggressive Mobile Flexbox to stop horizontal scroll */
    @media (max-width: 576px) {
        [data-testid="stHorizontalBlock"] {
            flex-direction: row !important; flex-wrap: nowrap !important; align-items: center !important; gap: 0.2rem !important;
        }
        [data-testid="column"] {
            width: auto !important; flex: 1 1 0% !important; min-width: 0 !important; padding: 0 !important;
        }
        div[data-testid="stMarkdownContainer"] p {
            white-space: normal !important;
            font-size: 0.85rem !important;
            line-height: 1.2 !important;
            margin-bottom: 0 !important;
        }
    }
    </style>
""", unsafe_allow_html=True)

# --- LOCAL DATABASE INITIALIZATION ---
DB_PATH = "retail_orders.db"

@st.cache_resource
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    
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
        CREATE TABLE IF NOT EXISTS DraftCarts (
            user_email TEXT,
            item_name TEXT,
            qty INTEGER,
            price REAL,
            remarks TEXT DEFAULT '',
            PRIMARY KEY (user_email, item_name)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Orders (
            order_id TEXT PRIMARY KEY,
            date TEXT,
            user_email TEXT,
            total_amount REAL,
            payment_method TEXT,
            status TEXT,
            keep_note TEXT DEFAULT ''
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
            remarks TEXT DEFAULT '',
            FOREIGN KEY(order_id) REFERENCES Orders(order_id)
        )
    """)
    
    # Ensure Admin Account exists
    admin_email = "zinandgin@gmail.com"
    admin_pass = hashlib.sha256("admin123".encode()).hexdigest()
    cur = conn.cursor()
    cur.execute("SELECT email FROM Users WHERE email = ?", (admin_email,))
    if not cur.fetchone():
        conn.execute("INSERT INTO Users (email, name, password_hash, role) VALUES (?, ?, ?, ?)", 
                     (admin_email, "Admin", admin_pass, "Admin"))
        conn.commit()
    
    # Populate Full 40-Item Catalog if empty
    if pd.read_sql("SELECT COUNT(*) FROM Catalog", conn).iloc[0,0] == 0:
        full_catalog = [
            ("Flours & Grains", "Aashirwaad Atta", "10 kg", 15.79, 14.50),
            ("Flours & Grains", "Basmati Rice (Premium / India Gate)", "5 kg", 17.49, 15.25),
            ("Flours & Grains", "Sona Masoori Rice", "5 kg", 10.99, 9.20),
            ("Flours & Grains", "Idli Rice", "5 kg", 9.99, 8.50),
            ("Flours & Grains", "Besan (Gram Flour)", "1 kg", 3.19, 2.60),
            ("Flours & Grains", "Sooji (Rava / Semolina)", "1 kg", 2.69, 2.25),
            ("Dals & Legumes", "Toor Dal", "1 kg", 4.19, 3.45),
            ("Dals & Legumes", "Moong Dal Yellow", "1 kg", 3.99, 3.30),
            ("Dals & Legumes", "Moong Whole Green", "1 kg", 3.69, 3.05),
            ("Dals & Legumes", "Urid Dal Whole", "1 kg", 4.29, 3.55),
            ("Dals & Legumes", "Urid Dal Split / Chilka", "1 kg", 3.99, 3.35),
            ("Dals & Legumes", "Chana Dal", "1 kg", 3.49, 2.85),
            ("Dals & Legumes", "Chickpeas (Kabuli Chana)", "1 kg", 3.59, 2.95),
            ("Dals & Legumes", "Kaala Chana (Black Chickpeas)", "1 kg", 3.29, 2.70),
            ("Dals & Legumes", "Yellow Peas Ragda (Vatana)", "1 kg", 2.89, 2.35),
            ("Whole Spices", "Jeera Whole (Cumin Seeds)", "400 g", 5.19, 4.25),
            ("Whole Spices", "Mustard Seeds (Rai)", "400 g", 3.49, 2.85),
            ("Whole Spices", "Black Pepper Whole", "100 g", 2.99, 2.35),
            ("Whole Spices", "Cardamom Green (Elaichi)", "50 g", 6.79, 5.20),
            ("Whole Spices", "Cloves (Laung)", "50 g", 2.59, 2.00),
            ("Whole Spices", "Ajwain (Carom Seeds)", "100 g", 1.99, 1.55),
            ("Whole Spices", "Hing (Asafoetida - Vandevi/LG)", "50 g", 2.49, 1.90),
            ("Whole Spices", "Saffron (Kesar)", "1 g", 7.49, 5.75),
            ("Spice Powders", "Turmeric Powder (Haldi)", "400 g", 3.29, 2.60),
            ("Spice Powders", "Red Chilli Powder (Extra Hot / Kashmiri)", "400 g", 4.89, 3.80),
            ("Spice Powders", "Coriander Powder (Dhaniya)", "400 g", 3.49, 2.70),
            ("Spice Powders", "Jeera Powder (Cumin Powder)", "400 g", 4.99, 3.90),
            ("Blended Masalas", "Garam Masala (MDH/Everest)", "100 g", 2.69, 2.10),
            ("Blended Masalas", "Pav Bhaji Masala (MDH/Everest)", "100 g", 2.69, 2.10),
            ("Blended Masalas", "Biryani Masala (Shan/MDH)", "100 g", 2.79, 2.20),
            ("Blended Masalas", "Chhole Masala (MDH/Everest)", "100 g", 2.69, 2.10),
            ("Blended Masalas", "Chaat Masala (MDH Chunky Chat)", "100 g", 2.49, 1.90),
            ("Fresh & Perishables", "Fresh Green Chilli", "500 g", 4.99, 4.75),
            ("Fresh & Perishables", "Fresh Curry Leaves", "50 g", 1.89, 1.55),
            ("Fresh & Perishables", "Fresh Idli/Dosa Batter", "1 kg", 5.19, 4.45),
            ("Fresh & Perishables", "Paneer Block", "1 kg", 13.38, 11.50),
            ("Pantry & Specialty", "Ghee (GRB / Khanum / TRS / Amul)", "1 L / 1 kg", 22.89, 20.50),
            ("Pantry & Specialty", "Cashew Nuts Broken (Kaju Tukda)", "500 g", 8.49, 6.90),
            ("Pantry & Specialty", "Sev (Nylon / Ratlami)", "400 g", 3.79, 2.95),
            ("Pantry & Specialty", "Chai Patti (Wagh Bakri / Red Label)", "1 kg", 13.49, 10.95)
        ]
        conn.executemany("INSERT INTO Catalog (category, item_name, pack_size, jamoona_price, friends_price) VALUES (?, ?, ?, ?, ?)", full_catalog)
        conn.commit()
        
    return conn

conn = get_db_connection()

# --- AUTOMATED BACKUP CHECK (Runs globally on any app wake-up / HTTP ping) ---
def automated_db_backup(db_path=DB_PATH, backup_interval_hours=48):
    try:
        tracker_file = "last_retail_backup.txt"
        current_time = time.time()
        
        if os.path.exists(tracker_file):
            with open(tracker_file, "r") as f:
                last_backup = float(f.read().strip())
            if (current_time - last_backup) < (backup_interval_hours * 3600):
                return
        
        if "email" in st.secrets and os.path.exists(db_path):
            sender = st.secrets["email"]["sender"]
            pwd = st.secrets["email"]["password"]
            receiver = "zinandgin@gmail.com"
            
            msg = MIMEMultipart()
            msg["Subject"] = f"Zin & Gin Retail DB Backup - {date.today()}"
            msg["From"] = f"Zin & Gin Retail <{sender}>"
            msg["To"] = receiver
            
            body = MIMEText("Attached is your automated Zin & Gin Retail database backup.")
            msg.attach(body)
            
            with open(db_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(db_path)}")
            msg.attach(part)
            
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(sender, pwd)
                server.send_message(msg)
                
            with open(tracker_file, "w") as f:
                f.write(str(current_time))
    except Exception:
        pass

automated_db_backup()

# --- HELPER FUNCTIONS ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def update_draft_cart(email, item_name, price, delta, remark=""):
    cur = conn.cursor()
    cur.execute("SELECT qty, remarks FROM DraftCarts WHERE user_email=? AND item_name=?", (email, item_name))
    row = cur.fetchone()
    
    current_qty = row[0] if row else 0
    current_remark = row[1] if row else remark
    new_qty = max(0, current_qty + delta)
    
    if new_qty == 0:
        cur.execute("DELETE FROM DraftCarts WHERE user_email=? AND item_name=?", (email, item_name))
    else:
        cur.execute("""
            INSERT INTO DraftCarts (user_email, item_name, qty, price, remarks) 
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_email, item_name) DO UPDATE SET qty=excluded.qty, remarks=excluded.remarks
        """, (email, item_name, new_qty, price, current_remark))
    
    conn.commit()

def save_draft_remark(email, item_name, price, remark):
    cur = conn.cursor()
    cur.execute("SELECT qty FROM DraftCarts WHERE user_email=? AND item_name=?", (email, item_name))
    row = cur.fetchone()
    qty = row[0] if row else 0
    
    cur.execute("""
        INSERT INTO DraftCarts (user_email, item_name, qty, price, remarks) 
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_email, item_name) DO UPDATE SET remarks=excluded.remarks
    """, (email, item_name, qty, price, remark))
    conn.commit()

def generate_keep_note(order_id, user_name, date_str, line_items):
    msg = f"🛒 Zin & Gin Order {order_id} - {date_str}\nUser: {user_name}\n\n"
    for _, row in line_items.iterrows():
        rem_text = f" [{row['remarks']}]" if row['remarks'] and str(row['remarks']).strip() else ""
        msg += f"    {row['qty']}x {row['item_name']}{rem_text}\n"
    return msg

def send_admin_email_alert(order_id, user_name, total_amount, method, keep_note_text):
    try:
        if "email" in st.secrets:
            sender = st.secrets["email"]["sender"]
            pwd = st.secrets["email"]["password"]
            receiver = "zinandgin@gmail.com"
            
            body = f"An order was finalized for {user_name}.\n\nOrder ID: {order_id}\nTotal: €{total_amount:.2f}\nMethod: {method}\n\n📋 Order Breakdown:\n{keep_note_text}"
            msg = MIMEText(body)
            msg["Subject"] = f"✅ Finalized Retail Order: €{total_amount:.2f}"
            msg["From"] = f"Zin & Gin Retail <{sender}>"
            msg["To"] = receiver
            
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(sender, pwd)
                server.send_message(msg)
    except Exception as e:
        print(f"Email skipped: {e}")

# --- SESSION STATE INITIALIZATION ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_email = ""
    st.session_state.user_name = ""
    st.session_state.user_role = ""

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
    st.write("Browse the catalog below. **Tap on any item name to add it to your order.**")
    
    df_catalog = pd.read_sql("SELECT * FROM Catalog", conn)
    df_draft = pd.read_sql("SELECT item_name, qty, remarks FROM DraftCarts WHERE user_email=?", conn, params=(st.session_state.user_email,))
    draft_dict = df_draft.set_index('item_name').to_dict('index')

    for category in df_catalog['category'].unique():
        with st.expander(f"🛒 {category}", expanded=False):
            cat_items = df_catalog[df_catalog['category'] == category]
            
            for _, row in cat_items.iterrows():
                item_name = str(row['item_name'])
                pack = str(row['pack_size'])
                jamoona = row['jamoona_price']
                price = row['friends_price']
                item_id = row['id']
                
                draft_data = draft_dict.get(item_name, {})
                current_qty = draft_data.get("qty", 0)
                current_remark = draft_data.get("remarks", "")
                
                btn_label = f"{item_name} ({pack}) | €{price:.2f}"
                if current_qty > 0:
                     btn_label += f"   🟢 {current_qty}"
                
                c_main, c_sub = st.columns([6, 1])
                with c_main:
                    st.button(btn_label, key=f"add_{item_id}", on_click=update_draft_cart, args=(st.session_state.user_email, item_name, price, 1), use_container_width=True)
                with c_sub:
                    st.button("➖", key=f"sub_{item_id}", on_click=update_draft_cart, args=(st.session_state.user_email, item_name, price, -1), use_container_width=True)
                
                # Remarks Pop-out
                with st.expander(f"💬 Add Remark", expanded=False):
                    new_remark = st.text_input("Special instructions (e.g., ripe, urgent)", value=current_remark, key=f"rem_{item_id}", label_visibility="collapsed")
                    if new_remark != current_remark:
                        save_draft_remark(st.session_state.user_email, item_name, price, new_remark)
                        st.rerun()

# --- PAGE: CUSTOMER CART & CHECKOUT ---
def page_cart():
    st.title("🛍️ Order Summary")
    
    df_cart = pd.read_sql("SELECT item_name, qty, price, remarks FROM DraftCarts WHERE user_email=?", conn, params=(st.session_state.user_email,))
    
    if df_cart.empty:
        st.info("Your cart is empty.")
        return
        
    df_cart['subtotal'] = df_cart['qty'] * df_cart['price']
    total_due = df_cart['subtotal'].sum()
    
    st.dataframe(df_cart[['item_name', 'qty', 'price', 'subtotal', 'remarks']], hide_index=True, use_container_width=True)
    st.markdown(f"### Total Due: €{total_due:.2f}")
    
    payment_method = st.radio("Payment Method", ["Add to my Tab (Settle End of Month)", "Tikkie / Pay Now"])
    
    if st.button("📤 Save Draft & Send to Manager", type="primary", use_container_width=True):
        order_id = str(uuid.uuid4())[:8].upper()
        order_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn.execute("INSERT INTO Orders (order_id, date, user_email, total_amount, payment_method, status) VALUES (?, ?, ?, ?, ?, ?)",
                     (order_id, order_date, st.session_state.user_email, total_due, payment_method, "Draft"))
        
        for _, row in df_cart.iterrows():
            conn.execute("INSERT INTO OrderLineItems (order_id, item_name, qty, unit_price, subtotal, remarks) VALUES (?, ?, ?, ?, ?, ?)",
                         (order_id, row["item_name"], row["qty"], row["price"], row["subtotal"], row["remarks"]))
        
        conn.execute("DELETE FROM DraftCarts WHERE user_email=?", (st.session_state.user_email,))
        conn.commit()
        
        st.success("🎉 Draft Saved! The manager will review and finalize your order shortly.")
        st.session_state.last_order = {"id": order_id, "status": "Draft Review Pending"}

# --- PAGE: MY PAST ORDERS (CUSTOMER VIEW) ---
def page_customer_orders():
    st.title("📜 My Past Orders")
    st.write("Review your finalized purchases.")
    
    df_orders = pd.read_sql("SELECT order_id, date, total_amount, status, keep_note FROM Orders WHERE user_email=? AND status != 'Draft' ORDER BY date DESC", conn, params=(st.session_state.user_email,))
    
    if df_orders.empty:
        st.info("No finalized orders found.")
        return
        
    for _, order in df_orders.iterrows():
        status_icon = "🟢" if order['status'] == "Settled" else "🔴"
        with st.expander(f"📦 Order {order['order_id']} | {order['date']} | €{order['total_amount']:.2f} {status_icon}"):
            st.text_area("Google Keep Note", value=order['keep_note'], height=150, disabled=True, key=f"gk_cust_{order['order_id']}")

# --- PAGE: ADMIN DASHBOARD (DRAFT REVIEW) ---
def page_admin():
    st.title("🛡️ Admin Dashboard")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Pending Drafts", "Past Orders & Ledgers", "Analytics", "Catalog & System"])
    
    with tab1:
        st.subheader("Review Pending Orders")
        df_drafts = pd.read_sql("SELECT order_id, date, user_email, total_amount, payment_method FROM Orders WHERE status='Draft' ORDER BY date DESC", conn)
        
        if df_drafts.empty:
            st.info("No pending drafts.")
        else:
            for _, draft in df_drafts.iterrows():
                o_id = draft['order_id']
                with st.expander(f"⏳ Draft: {o_id} | {draft['user_email']} | €{draft['total_amount']:.2f}"):
                    df_items = pd.read_sql("SELECT line_id, item_name, qty, unit_price, subtotal, remarks FROM OrderLineItems WHERE order_id=?", conn, params=(o_id,))
                    edited_items = st.data_editor(df_items, key=f"edit_{o_id}", hide_index=True, use_container_width=True)
                    
                    if st.button("✅ Finalize Order & Update Stock", key=f"fin_{o_id}", type="primary"):
                        new_total = 0.0
                        for _, row in edited_items.iterrows():
                            subt = row['qty'] * row['unit_price']
                            new_total += subt
                            conn.execute("UPDATE OrderLineItems SET qty=?, subtotal=?, remarks=? WHERE line_id=?", (row['qty'], subt, row['remarks'], row['line_id']))
                        
                        keep_txt = generate_keep_note(o_id, draft['user_email'], draft['date'], edited_items)
                        
                        conn.execute("UPDATE Orders SET status='Open', total_amount=?, keep_note=? WHERE order_id=?", (new_total, keep_txt, o_id))
                        conn.execute("UPDATE Users SET balance = balance + ? WHERE email = ?", (new_total, draft['user_email']))
                        conn.commit()
                        
                        send_admin_email_alert(o_id, draft['user_email'], new_total, draft['payment_method'], keep_txt)
                        st.success(f"Order {o_id} Finalized!")
                        st.rerun()

    with tab2:
        st.subheader("Ledgers & History")
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
                    
        st.write("### Past Orders")
        df_orders = pd.read_sql("SELECT order_id, date, user_email, total_amount, status, keep_note FROM Orders WHERE status != 'Draft' ORDER BY date DESC", conn)
        for _, order in df_orders.iterrows():
            with st.expander(f"📦 {order['order_id']} | {order['user_email']} | €{order['total_amount']:.2f}"):
                st.text_area("Keep Note", value=order['keep_note'], height=150, disabled=True, key=f"gk_adm_{order['order_id']}")
                if st.button("🗑️ Delete Test Order (Reverses Balance)", key=f"del_{order['order_id']}"):
                    if order['status'] != 'Settled':
                        conn.execute("UPDATE Users SET balance = balance - ? WHERE email = ?", (order['total_amount'], order['user_email']))
                    conn.execute("DELETE FROM OrderLineItems WHERE order_id=?", (order['order_id'],))
                    conn.execute("DELETE FROM Orders WHERE order_id=?", (order['order_id'],))
                    conn.commit()
                    st.rerun()

    with tab3:
        st.subheader("Retail Sales Analytics")
        query = """
            SELECT o.date, c.category, o.user_email, l.qty, l.subtotal 
            FROM Orders o 
            JOIN OrderLineItems l ON o.order_id = l.order_id
            JOIN Catalog c ON l.item_name = c.item_name
            WHERE o.status != 'Draft'
        """
        try:
            df_analytics = pd.read_sql(query, conn)
            if not df_analytics.empty:
                df_analytics["Date"] = pd.to_datetime(df_analytics["date"]).dt.date
                
                c_fig1, c_fig2 = st.columns(2)
                with c_fig1:
                    fig1 = px.pie(df_analytics, values="subtotal", names="category", title="Revenue by Category", hole=0.4)
                    st.plotly_chart(fig1, use_container_width=True)
                with c_fig2:
                    fig2 = px.pie(df_analytics, values="subtotal", names="user_email", title="Revenue by Customer", hole=0.4)
                    st.plotly_chart(fig2, use_container_width=True)
                
                st.write("**Daily Sales Trend**")
                daily_sales = df_analytics.groupby("Date")["subtotal"].sum().reset_index()
                fig3 = px.bar(daily_sales, x="Date", y="subtotal", title="Total Retail Sales (€) Over Time")
                st.plotly_chart(fig3, use_container_width=True)
            else:
                st.info("Not enough order data to display analytics yet.")
        except Exception as e:
            st.error(f"Analytics error: {e}")

    with tab4:
        st.subheader("Manage Catalog")
        df_cat = pd.read_sql("SELECT * FROM Catalog", conn)
        edited_cat = st.data_editor(df_cat, num_rows="dynamic", use_container_width=True, hide_index=True)
        if st.button("Save Catalog Changes"):
            edited_cat.to_sql("Catalog", conn, if_exists="replace", index=False)
            st.success("Catalog updated!")
            
        st.divider()
        st.write("### 💾 System Database Backup & Restore")
        c_down, c_up = st.columns(2)
        with c_down:
            if os.path.exists(DB_PATH):
                with open(DB_PATH, "rb") as f:
                    st.download_button(label="⬇️ Backup Data (.db)", data=f, file_name="retail_orders.db", mime="application/octet-stream", use_container_width=True)
        with c_up:
            uploaded_db = st.file_uploader("Restore Data", type=["db"], label_visibility="collapsed")
            if uploaded_db is not None:
                if st.button("⬆️ Restore System Now", type="primary", use_container_width=True):
                    with open(DB_PATH, "wb") as f:
                        f.write(uploaded_db.getbuffer())
                    st.success("Database restored successfully! The app will now reload.")
                    st.rerun()

# --- MAIN ROUTING ---
if not st.session_state.logged_in:
    page_login()
else:
    with st.sidebar:
        st.write(f"👤 **{st.session_state.user_name}**")
        
        if st.session_state.user_role == "Customer":
            user_balance = pd.read_sql("SELECT balance FROM Users WHERE email=?", conn, params=(st.session_state.user_email,)).iloc[0,0]
            st.write(f"💼 Open Tab: **€{user_balance:.2f}**")
            st.divider()
            nav = st.radio("Navigation", ["Catalog", "Cart / Checkout", "My Past Orders"])
        else:
            st.write("🛡️ **Admin Account**")
            st.divider()
            nav = st.radio("Navigation", ["Admin Dashboard", "Catalog", "Cart / Checkout"])

        if st.button("Log Out"):
            st.session_state.logged_in = False
            if 'last_order' in st.session_state:
                del st.session_state.last_order
            st.rerun()

    if nav == "Catalog":
        page_order()
    elif nav == "Cart / Checkout":
        if 'last_order' in st.session_state:
            st.success("🎉 Draft Saved! The manager will review your order shortly.")
            if st.button("Return to Catalog"):
                del st.session_state.last_order
                st.rerun()
        else:
            page_cart()
    elif nav == "My Past Orders":
        page_customer_orders()
    elif nav == "Admin Dashboard":
        page_admin()
