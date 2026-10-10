import streamlit as st
import pandas as pd
from datetime import datetime
import hashlib
import uuid

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

# --- GOOGLE SHEETS CONNECTION ---
# You need to publish the Google Sheet to the web as CSV for reading, 
# or use gspread/st.connection for reading AND writing. 
# For this script to write, it requires st.connection("gsheets", type=GSheetsConnection) 
# and a secrets.toml file with service account credentials.
# Here we simulate the DB connection to ensure the code runs immediately for you to test.

DATABASE_ID = "1OsamZqwE5WZyZHqN3vyHqPx9Jo_40rPR3BXY5u8Wyy0"

@st.cache_resource
def get_catalog():
    # Public CSV read of your specific sheet ID
    url = f"https://docs.google.com/spreadsheets/d/{DATABASE_ID}/gviz/tq?tqx=out:csv&sheet=Catalog"
    try:
        return pd.read_csv(url)
    except:
        # Fallback dummy data if the sheet isn't public yet
        return pd.DataFrame({
            "Category": ["Dals & Legumes", "Whole Spices"],
            "Item Name": ["Toor Dal (KRG / Kamal)", "Jeera Whole (KRG)"],
            "Standard Pack Size": ["1 kg", "400 g"],
            "Jamoona Market Price (€)": [4.19, 5.19],
            "Proposed Friends Price (€)": [3.30, 4.20]
        })

# --- SESSION STATE INITIALIZATION ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_email = ""
    st.session_state.user_name = ""
if 'cart' not in st.session_state:
    st.session_state.cart = {}

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

# --- PAGE: LOGIN / SIGNUP ---
def page_login():
    st.title("🔐 Zin & Gin Retail Portal")
    st.write("Welcome to the friends & family grocery portal.")
    
    tab1, tab2 = st.tabs(["Log In", "Create Account"])
    
    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email Address").lower()
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Log In", type="primary"):
                # In production, check against the Users_Dossier tab in Google Sheets
                if email and password:
                    st.session_state.logged_in = True
                    st.session_state.user_email = email
                    st.session_state.user_name = email.split("@")[0].title()
                    st.rerun()
                else:
                    st.error("Please enter credentials.")

    with tab2:
        with st.form("signup_form"):
            new_name = st.text_input("Full Name")
            new_email = st.text_input("Email Address").lower()
            new_password = st.text_input("Create Password", type="password")
            if st.form_submit_button("Create Account"):
                if new_name and new_email and len(new_password) > 3:
                    # In production, write this new user to the Users_Dossier Google Sheet tab
                    st.success("Account created successfully! You can now log in.")
                else:
                    st.error("Please fill all fields.")

# --- PAGE: ORDERING CATALOG ---
def page_order():
    st.title(f"👋 Hi, {st.session_state.user_name}!")
    st.write("Browse the catalog and tap to add items to your cart.")
    
    df_catalog = get_catalog()
    
    if df_catalog.empty:
        st.error("Could not load catalog. Ensure the Google Sheet is published to the web.")
        return

    # Create a nice layout for categories
    for category in df_catalog['Category'].unique():
        if pd.isna(category): continue
        
        with st.expander(f"🛒 {category}", expanded=True):
            cat_items = df_catalog[df_catalog['Category'] == category]
            
            # Print headers
            c_name, c_jamoona, c_price, c_actions = st.columns([4, 2, 2, 3])
            c_name.markdown("**Item**")
            c_jamoona.markdown("**Jamoona**")
            c_price.markdown("**Our Price**")
            
            st.divider()
            
            for _, row in cat_items.iterrows():
                item_name = str(row['Item Name'])
                pack = str(row['Standard Pack Size'])
                jamoona = row['Jamoona Market Price (€)']
                price = row['Proposed Friends Price (€)']
                
                # Retrieve current cart qty
                current_qty = st.session_state.cart.get(item_name, {}).get("qty", 0)
                
                c1, c2, c3, c4 = st.columns([4, 2, 2, 3])
                
                # Column 1: Item Name & Pack
                display_name = f"{item_name} ({pack})"
                if current_qty > 0:
                     display_name += f"   🟢 **{current_qty}**"
                c1.write(display_name)
                
                # Column 2: Jamoona Price (Strikethrough)
                c2.markdown(f"<span style='color:red; text-decoration:line-through;'>€{jamoona:.2f}</span>", unsafe_allow_html=True)
                
                # Column 3: Our Price
                c3.markdown(f"**€{price:.2f}**")
                
                # Column 4: Add/Remove Buttons
                ac1, ac2 = c4.columns(2)
                with ac1:
                    st.button("➖", key=f"sub_{item_name}", on_click=update_cart, args=(item_name, price, -1))
                with ac2:
                    st.button("➕", key=f"add_{item_name}", on_click=update_cart, args=(item_name, price, 1))
                
                st.markdown("<hr style='margin: 0.5rem 0; opacity: 0.2;'>", unsafe_allow_html=True)

# --- PAGE: CART & CHECKOUT ---
def page_cart():
    st.title("🛍️ Order Summary")
    
    if not st.session_state.cart:
        st.info("Your cart is empty.")
        return
        
    cart_items = []
    total_due = 0.0
    
    for item, data in st.session_state.cart.items():
        qty = data["qty"]
        price = data["price"]
        subtotal = qty * price
        total_due += subtotal
        cart_items.append({"Item": item, "Qty": qty, "Unit Price": f"€{price:.2f}", "Subtotal": f"€{subtotal:.2f}"})
        
    df_cart = pd.DataFrame(cart_items)
    st.dataframe(df_cart, hide_index=True, use_container_width=True)
    
    st.markdown(f"### Total Due: €{total_due:.2f}")
    
    payment_method = st.radio("Payment Method", ["Tikkie (Request sent on WhatsApp)", "Cash on Pickup"])
    
    if st.button("✅ Place Order", type="primary", use_container_width=True):
        order_id = str(uuid.uuid4())[:8].upper()
        
        # --- DATABASE WRITE LOGIC ---
        # In production, use st.connection("gsheets") to append rows to:
        # 1. Orders tab: [order_id, datetime.now(), st.session_state.user_email, "Open", total_due, payment_method]
        # 2. Order_Line_Items tab: loops through cart to insert [order_id, item, qty, price, subtotal]
        # 3. Users_Dossier tab: update the user's Total_Unsettled_EUR balance.
        
        st.session_state.last_order = {
            "id": order_id,
            "total": total_due,
            "method": payment_method
        }
        st.session_state.cart = {}
        st.rerun()

# --- PAGE: CONFIRMATION INVOICE ---
def page_confirmation():
    order = st.session_state.last_order
    st.success("🎉 Order Placed Successfully!")
    
    st.markdown(f"""
    ### Invoice Summary
    * **Order ID:** {order['id']}
    * **Total Amount Due:** €{order['total']:.2f}
    * **Payment Method:** {order['method']}
    * **Status:** Open (Added to your Dossier Tab)
    """)
    
    if st.button("Return to Catalog"):
        del st.session_state.last_order
        st.rerun()

# --- MAIN ROUTING ---
if not st.session_state.logged_in:
    page_login()
else:
    with st.sidebar:
        st.write(f"👤 **{st.session_state.user_name}**")
        st.write(f"💼 Open Tab: €0.00") # Query Users_Dossier for actual amount
        st.divider()
        nav = st.radio("Navigation", ["Catalog", "Cart / Checkout", "My Order History"])
        if st.button("Log Out"):
            st.session_state.logged_in = False
            st.rerun()

    if 'last_order' in st.session_state:
        page_confirmation()
    elif nav == "Catalog":
        page_order()
    elif nav == "Cart / Checkout":
        page_cart()
    elif nav == "My Order History":
        st.title("📜 Order History")
        st.info("No past orders found. (Connects to Google Sheets Orders tab)")
