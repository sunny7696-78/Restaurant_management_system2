# 🍽️ AI-Powered IntelliPredict
## Real-Time Restaurant Demand Forecasting & WasteZero Optimization Platform

A fully-functioning, multi-model AI platform for restaurant demand prediction, waste reduction, revenue optimization, and weather impact analysis — built with Streamlit and deployed for free.

---

## 🚀 Features

| Page | Description |
|------|-------------|
| 🏠 Dashboard | KPIs, demand trends, revenue breakdown |
| 📈 Demand Forecast | Prophet + XGBoost + LSTM + Ensemble |
| 📦 Inventory & Waste | Stock risk, reorder suggestions, waste trends |
| 🌦️ Weather & Events | Heatmaps, festival impact, day-of-week patterns |
| 💰 Revenue Optimizer | Price elasticity simulation, profit calculator |
| 🔬 Model Lab | Model comparison, residuals, feature importance |

---

## 🛠️ Local Setup

### Prerequisites
- Python 3.10 or 3.11
- pip

### Steps

```bash
# 1. Clone or download this project
git clone https://github.com/YOUR_USERNAME/intellipredict.git
cd intellipredict

# 2. Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
streamlit run app.py
```

The app will open at `http://localhost:8501`

---

## ☁️ Free Deployment on Streamlit Community Cloud

### Step 1 — Push to GitHub

```bash
# Initialize git in the project folder
git init
git add .
git commit -m "Initial commit — IntelliPredict"

# Create a repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/intellipredict.git
git branch -M main
git push -u origin main
```

### Step 2 — Deploy on Streamlit Cloud

1. Go to **[share.streamlit.io](https://share.streamlit.io)**
2. Sign in with your GitHub account
3. Click **"New app"**
4. Fill in:
   - **Repository**: `YOUR_USERNAME/intellipredict`
   - **Branch**: `main`
   - **Main file path**: `app.py`
5. Click **"Deploy!"**
6. Wait ~3–5 minutes for the build
7. Your app is live at: `https://YOUR_USERNAME-intellipredict-app-XXXX.streamlit.app`

### ⚠️ TensorFlow Note
TensorFlow is large (~600MB). If the Streamlit Cloud build times out or fails:
- The app **automatically falls back** to a Random Forest-based LSTM substitute
- Remove `tensorflow` from `requirements.txt` to speed up deployment
- The LSTM page will still work, just using RF internally

---

## 📁 File Structure

```
intellipredict/
├── app.py              # Main Streamlit application (6 pages)
├── data_generator.py   # Synthetic restaurant data generation
├── models.py           # Prophet, XGBoost, LSTM model implementations
├── utils.py            # Chart helpers, formatting, metrics
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

---

## 🧠 Models Used

- **Prophet (Meta)** — Captures seasonality, holidays, and trend changes
- **XGBoost** — Gradient boosting with lag features and weather inputs
- **LSTM** — Sequence-to-sequence deep learning via TensorFlow/Keras
- **Ensemble** — Averages all three for maximum accuracy

---

## 📊 Data

All data is **synthetically generated** inside `data_generator.py`. No external datasets needed.

Covers:
- 5 restaurants × 4 menu categories × 3 years of daily records
- Realistic seasonality (monsoon dip, festive peaks, weekends)
- Weather (temperature, rainfall) correlated with demand
- Indian festival calendar (Holi, Diwali, Independence Day, etc.)

---

## 🎓 Academic Use

**Project Title:** AI-Powered IntelliPredict: Real-Time Restaurant Demand Forecasting and WasteZero Optimization Platform

**Technologies:** Python, Streamlit, Prophet, XGBoost, TensorFlow/LSTM, Plotly, Scikit-learn

**Key Concepts:** Time-series forecasting, ensemble learning, price elasticity, sustainability analytics, feature importance/explainability

---

## 📜 License

MIT License — free to use for academic and personal projects.
