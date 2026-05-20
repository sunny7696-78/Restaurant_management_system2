"""User Management view — admin-only panel for IntelliPredict."""

import streamlit as st
import hashlib
from datetime import datetime
from config import PALETTE
from auth import USERS, ROLE_PERMISSIONS, hash_password
from data_generator import RESTAURANTS


def render_user_management():
    """Renders the admin-only user management page."""

    st.markdown("# 👥 User Management")
    st.markdown(
        "<small style='color:#8A8696'>Admin-only: manage user accounts, roles, and restaurant access</small>",
        unsafe_allow_html=True,
    )
    st.divider()

    # ── Summary KPIs ──────────────────────────────────────────────────────────
    total = len(USERS)
    admins   = sum(1 for u in USERS.values() if u["role"] == "admin")
    managers = sum(1 for u in USERS.values() if u["role"] == "manager")
    staff    = sum(1 for u in USERS.values() if u["role"] == "staff")

    c1, c2, c3, c4 = st.columns(4)
    for col, label, val, color in [
        (c1, "Total Users",    total,    PALETTE["primary"]),
        (c2, "Admins",         admins,   PALETTE["danger"]),
        (c3, "Managers",       managers, PALETTE["secondary"]),
        (c4, "Staff",          staff,    PALETTE["success"]),
    ]:
        col.markdown(f"""
        <div class='kpi-card'>
            <div class='kpi-label'>{label}</div>
            <div class='kpi-value' style='color:{color}'>{val}</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ── User Table ────────────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>All Users</div>", unsafe_allow_html=True)

    role_colors = {
        "admin":   (PALETTE["danger"],   "🔴"),
        "manager": (PALETTE["secondary"],"🟡"),
        "staff":   (PALETTE["success"],  "🟢"),
    }

    # Init session state for user list
    if "user_list" not in st.session_state:
        st.session_state["user_list"] = {
            k: {**v, "status": "active", "last_login": "N/A"}
            for k, v in USERS.items()
        }

    users = st.session_state["user_list"]

    # Header row
    h_cols = st.columns([1.5, 2, 1.5, 2, 1.5, 1.5, 1])
    for col, label in zip(h_cols, ["Avatar", "Name / Username", "Role", "Restaurant Access", "Status", "Last Login", "Action"]):
        col.markdown(f"<small style='color:{PALETTE['muted']};font-weight:700;text-transform:uppercase;letter-spacing:.06em'>{label}</small>", unsafe_allow_html=True)
    st.markdown(f"<hr style='border-color:{PALETTE['border']};margin:6px 0 12px'>", unsafe_allow_html=True)

    for uname, udata in users.items():
        color, dot = role_colors.get(udata["role"], (PALETTE["muted"], "⚪"))
        restaurant = RESTAURANTS.get(udata.get("restaurant_access", ""), "All Restaurants") if udata.get("restaurant_access") != "all" else "All Restaurants"
        status_color = PALETTE["success"] if udata["status"] == "active" else PALETTE["danger"]

        row = st.columns([1.5, 2, 1.5, 2, 1.5, 1.5, 1])
        row[0].markdown(f"""
        <div style='width:38px;height:38px;border-radius:50%;background:{color}33;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;color:{color}'>
            {udata.get("avatar","??")}</div>""", unsafe_allow_html=True)
        row[1].markdown(f"**{udata['name']}**<br><small style='color:{PALETTE['muted']}'>{uname}</small>", unsafe_allow_html=True)
        row[2].markdown(f"<span style='color:{color};font-weight:700;font-size:12px;background:{color}22;border:1px solid {color}44;border-radius:5px;padding:2px 8px'>{dot} {udata['role']}</span>", unsafe_allow_html=True)
        row[3].markdown(f"<small style='color:{PALETTE['text']}'>{restaurant}</small>", unsafe_allow_html=True)
        row[4].markdown(f"<span style='color:{status_color};font-weight:700;font-size:12px'>{'● Active' if udata['status'] == 'active' else '○ Inactive'}</span>", unsafe_allow_html=True)
        row[5].markdown(f"<small style='color:{PALETTE['muted']}'>{udata['last_login']}</small>", unsafe_allow_html=True)

        btn_label = "Deactivate" if udata["status"] == "active" else "Activate"
        if row[6].button(btn_label, key=f"toggle_{uname}", use_container_width=True):
            st.session_state["user_list"][uname]["status"] = (
                "inactive" if udata["status"] == "active" else "active"
            )
            st.rerun()

        st.markdown(f"<hr style='border-color:{PALETTE['border']}44;margin:8px 0'>", unsafe_allow_html=True)

    st.divider()

    # ── Add New User ──────────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>➕ Add New User</div>", unsafe_allow_html=True)

    with st.expander("Create New User Account", expanded=False):
        with st.form("add_user_form"):
            f1, f2 = st.columns(2)
            new_name     = f1.text_input("Full Name", placeholder="e.g. Sunita Patel")
            new_username = f2.text_input("Username", placeholder="e.g. sunita_p")

            f3, f4, f5 = st.columns(3)
            new_role     = f3.selectbox("Role", ["staff", "manager", "admin"])
            new_rest     = f4.selectbox("Restaurant Access", ["all"] + list(RESTAURANTS.keys()),
                                        format_func=lambda x: "All Restaurants" if x == "all" else RESTAURANTS.get(x, x))
            new_password = f5.text_input("Password", type="password", placeholder="Min 6 chars")

            submitted = st.form_submit_button("✅ Create User", use_container_width=True)

        if submitted:
            if not new_name or not new_username or not new_password:
                st.error("All fields are required.")
            elif len(new_password) < 6:
                st.error("Password must be at least 6 characters.")
            elif new_username in st.session_state["user_list"]:
                st.error(f"Username '{new_username}' already exists.")
            else:
                initials = "".join(w[0].upper() for w in new_name.split()[:2])
                st.session_state["user_list"][new_username] = {
                    "password_hash": hash_password(new_password),
                    "role": new_role,
                    "name": new_name,
                    "restaurant_access": new_rest,
                    "avatar": initials,
                    "status": "active",
                    "last_login": "Never",
                }
                st.success(f"✅ User '{new_name}' created successfully!")
                st.rerun()

    st.divider()

    # ── Role Permissions Reference ────────────────────────────────────────────
    st.markdown("<div class='section-header'>🔐 Role Permissions</div>", unsafe_allow_html=True)

    all_pages = ["dashboard", "forecast", "inventory", "weather", "revenue", "model_lab", "ai_insights", "user_management"]
    page_labels = {
        "dashboard": "🏠 Dashboard",
        "forecast": "📈 Demand Forecast",
        "inventory": "📦 Inventory & Waste",
        "weather": "🌦️ Weather & Events",
        "revenue": "💰 Revenue Optimizer",
        "model_lab": "🔬 Model Lab",
        "ai_insights": "🤖 AI Insights",
        "user_management": "👥 User Management",
    }

    header = st.columns([2, 1, 1, 1])
    header[0].markdown(f"<small style='color:{PALETTE['muted']};font-weight:700'>PAGE</small>", unsafe_allow_html=True)
    for i, role in enumerate(["admin", "manager", "staff"]):
        color, _ = role_colors[role]
        header[i + 1].markdown(f"<small style='color:{color};font-weight:700;text-transform:uppercase'>{role}</small>", unsafe_allow_html=True)

    success_color = PALETTE["success"]
    danger_color = PALETTE["danger"]
    text_color = PALETTE["text"]
    for page in all_pages:
        row = st.columns([2, 1, 1, 1])
        row[0].markdown(f"<small style='color:{text_color}'>{page_labels[page]}</small>", unsafe_allow_html=True)
        for i, role in enumerate(["admin", "manager", "staff"]):
            has = page in ROLE_PERMISSIONS.get(role, [])
            icon_html = f"<span style='color:{success_color}'>✅</span>" if has else f"<span style='color:{danger_color}'>✗</span>"
            row[i + 1].markdown(icon_html, unsafe_allow_html=True)
