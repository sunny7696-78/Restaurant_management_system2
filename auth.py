"""Authentication module for IntelliPredict."""

import streamlit as st
import hashlib
from typing import Optional, Dict

# ── User Store (in production, replace with a real DB) ────────────────────────

USERS: Dict[str, Dict] = {
    "admin": {
        "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
        "role": "admin",
        "name": "Rajesh Kumar",
        "restaurant_access": "all",
        "avatar": "RK",
    },
    "manager": {
        "password_hash": hashlib.sha256("manager123".encode()).hexdigest(),
        "role": "manager",
        "name": "Priya Sharma",
        "restaurant_access": "R001",
        "avatar": "PS",
    },
    "staff": {
        "password_hash": hashlib.sha256("staff123".encode()).hexdigest(),
        "role": "staff",
        "name": "Amit Singh",
        "restaurant_access": "R002",
        "avatar": "AS",
    },
}

ROLE_PERMISSIONS = {
    "admin": ["dashboard", "forecast", "inventory", "weather", "revenue", "model_lab", "ai_insights", "user_management"],
    "manager": ["dashboard", "forecast", "inventory", "weather", "revenue", "ai_insights"],
    "staff": ["dashboard", "inventory"],
}

LOGIN_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;600;700&family=Space+Grotesk:wght@500;700&display=swap');

.login-container {
    max-width: 420px;
    margin: 60px auto;
    padding: 40px 36px;
    background: #1A1A24;
    border: 1px solid #2a2a3a;
    border-radius: 16px;
    font-family: 'IBM Plex Sans', sans-serif;
}

.login-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 26px;
    font-weight: 700;
    color: #FF6B35;
    text-align: center;
    margin-bottom: 4px;
}

.login-subtitle {
    font-size: 13px;
    color: #8A8696;
    text-align: center;
    margin-bottom: 28px;
}

.demo-box {
    background: #0F0F13;
    border: 1px solid #2a2a3a;
    border-radius: 10px;
    padding: 14px 16px;
    margin-top: 16px;
}

.demo-title {
    font-size: 11px;
    color: #8A8696;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 8px;
}

.demo-row {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    padding: 3px 0;
    color: #c0bcc8;
}

.demo-cred {
    color: #FF6B35;
    font-weight: 600;
    font-family: monospace;
}
</style>
"""


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def authenticate(username: str, password: str) -> Optional[Dict]:
    """Validate credentials and return user info or None."""
    user = USERS.get(username.lower().strip())
    if user and user["password_hash"] == hash_password(password):
        return {"username": username, **user}
    return None


def render_login_page():
    """Render the full-screen login page."""
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class='login-container'>
        <div style='text-align:center; font-size:48px; margin-bottom:12px'>🍽️</div>
        <div class='login-title'>IntelliPredict</div>
        <div class='login-subtitle'>Restaurant AI Management Platform</div>
    </div>
    """, unsafe_allow_html=True)

    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        with st.form("login_form"):
            username = st.text_input("👤 Username", placeholder="admin / manager / staff")
            password = st.text_input("🔒 Password", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Sign In →", use_container_width=True)

        if submitted:
            if not username or not password:
                st.error("Please enter both username and password.")
            else:
                user = authenticate(username, password)
                if user:
                    st.session_state["authenticated"] = True
                    st.session_state["user"] = user
                    st.success(f"Welcome back, {user['name']}! 🎉")
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials. Please try again.")

        st.markdown("""
        <div class='demo-box'>
            <div class='demo-title'>Demo Accounts</div>
            <div class='demo-row'><span>Admin (Full Access)</span><span class='demo-cred'>admin / admin123</span></div>
            <div class='demo-row'><span>Manager (Restaurant)</span><span class='demo-cred'>manager / manager123</span></div>
            <div class='demo-row'><span>Staff (Limited)</span><span class='demo-cred'>staff / staff123</span></div>
        </div>
        """, unsafe_allow_html=True)


def is_authenticated() -> bool:
    return st.session_state.get("authenticated", False)


def get_current_user() -> Optional[Dict]:
    return st.session_state.get("user", None)


def has_permission(page_key: str) -> bool:
    user = get_current_user()
    if not user:
        return False
    role = user.get("role", "staff")
    return page_key in ROLE_PERMISSIONS.get(role, [])


def logout():
    st.session_state["authenticated"] = False
    st.session_state["user"] = None
    st.rerun()
