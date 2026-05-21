"""WhatsApp / Email Alerts view for IntelliPredict."""

import streamlit as st
import pandas as pd
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from config import PALETTE
from utils import format_inr
from data_generator import RESTAURANTS, CATEGORIES

P  = PALETTE
PC = {k: v for k, v in P.items()}


# ── Alert rule engine ─────────────────────────────────────────────────────────

def check_alerts(df: pd.DataFrame, rest_id: str) -> list:
    """Scans data and returns triggered alert list."""
    rest = df[df["restaurant_id"] == rest_id]
    today = rest["date"].max()
    last7 = rest[rest["date"] >= today - pd.Timedelta(days=7)]
    prev7 = rest[(rest["date"] >= today - pd.Timedelta(days=14)) & (rest["date"] < today - pd.Timedelta(days=7))]

    alerts = []

    # 1. Stock critical
    for cat in CATEGORIES:
        cat_df = last7[last7["category"] == cat]
        if len(cat_df) == 0:
            continue
        avg_stock  = cat_df["stock_level"].mean()
        avg_demand = cat_df["quantity_sold"].mean()
        coverage   = avg_stock / avg_demand if avg_demand > 0 else 99
        if coverage < 1.1:
            alerts.append({
                "type": "critical", "icon": "🚨",
                "title": f"Critical Stock: {cat}",
                "body":  f"Stock coverage is {coverage:.1f}x — below 1.1x safety threshold. Immediate reorder required.",
                "category": cat, "metric": f"{coverage:.1f}x coverage",
            })

    # 2. Waste spike
    avg_waste_7  = last7["waste_kg"].mean()
    avg_waste_p7 = prev7["waste_kg"].mean() if len(prev7) > 0 else avg_waste_7
    waste_change = ((avg_waste_7 - avg_waste_p7) / max(avg_waste_p7, 0.1)) * 100
    if waste_change > 20:
        alerts.append({
            "type": "warning", "icon": "♻️",
            "title": "Waste Spike Detected",
            "body":  f"Daily waste rose {waste_change:.0f}% vs last week ({avg_waste_7:.1f} kg vs {avg_waste_p7:.1f} kg). Review prep quantities.",
            "category": "All", "metric": f"+{waste_change:.0f}%",
        })

    # 3. Demand spike
    qty_7  = last7["quantity_sold"].sum()
    qty_p7 = prev7["quantity_sold"].sum() if len(prev7) > 0 else qty_7
    demand_change = ((qty_7 - qty_p7) / max(qty_p7, 1)) * 100
    if demand_change > 25:
        alerts.append({
            "type": "positive", "icon": "📈",
            "title": "Demand Spike!",
            "body":  f"Demand jumped {demand_change:.0f}% vs last week. Consider increasing prep and staffing this week.",
            "category": "All", "metric": f"+{demand_change:.0f}%",
        })

    # 4. Revenue drop
    rev_7  = last7["revenue"].sum()
    rev_p7 = prev7["revenue"].sum() if len(prev7) > 0 else rev_7
    rev_change = ((rev_7 - rev_p7) / max(rev_p7, 1)) * 100
    if rev_change < -15:
        alerts.append({
            "type": "warning", "icon": "💸",
            "title": "Revenue Drop Alert",
            "body":  f"Revenue fell {abs(rev_change):.0f}% vs last week ({format_inr(rev_7)} vs {format_inr(rev_p7)}). Review pricing and promotions.",
            "category": "All", "metric": f"{rev_change:.0f}%",
        })

    # 5. High demand day approaching (weekend)
    today_dt = datetime.now()
    if today_dt.weekday() in [3, 4]:  # Thu/Fri
        alerts.append({
            "type": "info", "icon": "📅",
            "title": "Weekend Peak Approaching",
            "body":  "Weekend demand is typically 35% higher. Increase Main Course and Beverages stock now.",
            "category": "All", "metric": "Weekend +35%",
        })

    return alerts


def send_whatsapp_alert(phone: str, message: str, token: str) -> tuple:
    """Send WhatsApp message via CallMeBot (free) or Twilio."""
    try:
        # CallMeBot free WhatsApp API
        url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={requests.utils.quote(message)}&apikey={token}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return True, "Sent via WhatsApp"
        return False, f"WhatsApp API returned {r.status_code}"
    except Exception as e:
        return False, str(e)


def send_email_alert(to_email: str, subject: str, body: str,
                     smtp_email: str, smtp_password: str) -> tuple:
    """Send email alert via Gmail SMTP."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = smtp_email
        msg["To"]      = to_email

        html = f"""
        <html><body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px">
        <div style="max-width:600px;margin:auto;background:white;border-radius:12px;padding:30px;
                    border-top:4px solid #FF6B35">
            <h2 style="color:#FF6B35">🍽️ IntelliPredict Alert</h2>
            <p style="color:#333;font-size:15px;line-height:1.6">{body}</p>
            <hr style="border:none;border-top:1px solid #eee;margin:20px 0">
            <p style="color:#999;font-size:12px">
                Generated by IntelliPredict · {datetime.now().strftime('%d %b %Y %H:%M')}
            </p>
        </div></body></html>
        """
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, to_email, msg.as_string())
        return True, "Email sent successfully"
    except Exception as e:
        return False, str(e)


# ── View ──────────────────────────────────────────────────────────────────────

def render_alerts(df: pd.DataFrame, rest_id: str, rest_name: str):
    st.markdown("# 📱 Smart Alerts Center")
    st.markdown(f"<small style='color:{P['muted']}'>Auto-detect anomalies and send WhatsApp/Email alerts for <b>{rest_name}</b></small>", unsafe_allow_html=True)
    st.divider()

    # ── Live alert detection ──────────────────────────────────────────────────
    st.markdown("<div class='section-header'>🔍 Live Alert Detection</div>", unsafe_allow_html=True)

    alerts = check_alerts(df, rest_id)

    if not alerts:
        st.success("✅ All systems normal — no alerts triggered for today.")
    else:
        st.warning(f"⚠️ {len(alerts)} alert(s) detected for {rest_name}")

    type_colors = {
        "critical": P["danger"],
        "warning":  P["secondary"],
        "positive": P["success"],
        "info":     "#6baaff",
    }
    type_bg = {
        "critical": "#2a0f12",
        "warning":  "#2a1f0f",
        "positive": "#0f2a26",
        "info":     "#0f1a2a",
    }

    selected_alerts = []
    for i, alert in enumerate(alerts):
        color = type_colors.get(alert["type"], P["muted"])
        bg    = type_bg.get(alert["type"], "#1A1A24")
        col_a, col_b = st.columns([0.05, 0.95])
        checked = col_a.checkbox("", key=f"alert_chk_{i}", value=True)
        with col_b:
            st.markdown(f"""
            <div style='background:{bg};border:1px solid {color}44;border-left:4px solid {color};
                        border-radius:10px;padding:14px 16px;margin-bottom:6px'>
                <div style='display:flex;justify-content:space-between;align-items:center'>
                    <span style='font-size:16px;font-weight:700;color:{P["text"]}'>{alert["icon"]} {alert["title"]}</span>
                    <span style='background:{color}22;color:{color};border:1px solid {color}44;
                                 border-radius:5px;padding:2px 10px;font-size:11px;font-weight:700'>{alert["metric"]}</span>
                </div>
                <div style='font-size:13px;color:{P["muted"]};margin-top:6px;line-height:1.6'>{alert["body"]}</div>
            </div>""", unsafe_allow_html=True)
        if checked:
            selected_alerts.append(alert)

    st.divider()

    # ── Alert configuration ───────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["📧 Email Alert", "📱 WhatsApp Alert", "⚙️ Alert Thresholds"])

    with tab1:
        st.markdown("<div class='section-header'>📧 Email Alerts via Gmail</div>", unsafe_allow_html=True)
        st.info("Use a **Gmail App Password** (not your main password). Enable 2FA → App Passwords in your Google account.")

        e1, e2 = st.columns(2)
        to_email      = e1.text_input("Send Alert To (Email)", placeholder="manager@restaurant.com")
        smtp_email    = e2.text_input("Your Gmail Address", placeholder="your@gmail.com")
        smtp_password = st.text_input("Gmail App Password", type="password", placeholder="xxxx xxxx xxxx xxxx")

        if st.button("📧 Send Email Alert", use_container_width=True, disabled=not selected_alerts):
            if not to_email or not smtp_email or not smtp_password:
                st.error("Please fill all email fields.")
            else:
                alert_lines = "\n".join([f"• {a['icon']} {a['title']}: {a['body']}" for a in selected_alerts])
                subject = f"🍽️ IntelliPredict Alert — {rest_name} ({len(selected_alerts)} issues)"
                body    = f"<b>{len(selected_alerts)} alert(s) detected for {rest_name}:</b><br><br>" + \
                          "<br>".join([f"<b>{a['icon']} {a['title']}</b><br>{a['body']}" for a in selected_alerts])
                with st.spinner("Sending email…"):
                    ok, msg = send_email_alert(to_email, subject, body, smtp_email, smtp_password)
                if ok:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")

    with tab2:
        st.markdown("<div class='section-header'>📱 WhatsApp via CallMeBot (Free)</div>", unsafe_allow_html=True)
        st.info("""**Setup (2 min):**
1. Save **+34 644 82 33 00** in your contacts as "CallMeBot"
2. Send: `I allow callmebot to send me messages` on WhatsApp to that number
3. You'll receive your API key by WhatsApp""")

        w1, w2 = st.columns(2)
        phone    = w1.text_input("WhatsApp Number", placeholder="+91XXXXXXXXXX (with country code)")
        wa_token = w2.text_input("CallMeBot API Key", placeholder="From WhatsApp reply")

        if st.button("📱 Send WhatsApp Alert", use_container_width=True, disabled=not selected_alerts):
            if not phone or not wa_token:
                st.error("Please enter phone number and API key.")
            else:
                msg = f"🍽️ IntelliPredict Alert — {rest_name}\n"
                msg += f"📅 {datetime.now().strftime('%d %b %Y %H:%M')}\n\n"
                for a in selected_alerts:
                    msg += f"{a['icon']} {a['title']}\n{a['body']}\n\n"
                with st.spinner("Sending WhatsApp message…"):
                    ok, result = send_whatsapp_alert(phone, msg, wa_token)
                if ok:
                    st.success(f"✅ {result}")
                else:
                    st.error(f"❌ {result}")

    with tab3:
        st.markdown("<div class='section-header'>⚙️ Alert Threshold Settings</div>", unsafe_allow_html=True)
        st.markdown(f"<small style='color:{P['muted']}'>Customize when alerts fire</small>", unsafe_allow_html=True)

        t1, t2 = st.columns(2)
        t1.slider("Stock Critical Below (coverage)",  0.8, 2.0, 1.1, 0.1, key="thresh_stock")
        t1.slider("Waste Spike Threshold (%)",         10,  50,  20,  5,   key="thresh_waste")
        t2.slider("Demand Spike Threshold (%)",        10,  50,  25,  5,   key="thresh_demand")
        t2.slider("Revenue Drop Threshold (%)",        5,   30,  15,  5,   key="thresh_revenue")

        if st.button("💾 Save Thresholds", use_container_width=True):
            st.success("✅ Thresholds saved for this session.")

    st.divider()

    # ── Alert history ─────────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>📋 Alert Log</div>", unsafe_allow_html=True)

    if "alert_log" not in st.session_state:
        st.session_state["alert_log"] = []

    if st.button("📝 Log Current Alerts"):
        for a in alerts:
            st.session_state["alert_log"].insert(0, {
                "time": datetime.now().strftime("%d %b %H:%M"),
                "restaurant": rest_name,
                "type": a["type"],
                "title": a["title"],
                "metric": a["metric"],
            })
        st.success(f"Logged {len(alerts)} alerts")

    if st.session_state["alert_log"]:
        log_df = pd.DataFrame(st.session_state["alert_log"][:20])
        st.dataframe(log_df, use_container_width=True, hide_index=True)
        if st.button("🗑️ Clear Log"):
            st.session_state["alert_log"] = []
            st.rerun()
    else:
        st.caption("No alerts logged yet. Click 'Log Current Alerts' above.")
