# app_v2_5_1.py
"""
ADUAVIR 2.5.1 — Diagnóstico Aduanal
Detectamos, advertimos y acompañamos

- Login por usuario
- Diagnóstico por búsqueda manual
- Upload de archivo .err
- Cruce contra catálogo
- Sin IA obligatoria
"""

import streamlit as st
import pandas as pd
import os
import re
import unicodedata
from dotenv import load_dotenv

# ---------------- CONFIG ----------------
st.set_page_config(page_title="ADUAVIR — Diagnóstico Aduanal", layout="wide")
load_dotenv()

CATALOG_PATH = "catalogo_errores_ADUAVIR_REGENERADO.xlsx"

USERS = {
    "aduavir_admin": {"pwd": "aduavir2025", "role": "admin"},
    "supervisora": {"pwd": "super2025", "role": "readonly"},
    "supervisor": {"pwd": "super2025", "role": "readonly"},
}

# ---------------- UTILS ----------------
def normalize_text(text):
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text).lower()
    return re.sub(r"\s+", " ", text).strip()

@st.cache_data
def load_catalog():
    df = pd.read_excel(CATALOG_PATH, dtype=str).fillna("")
    df.columns = [normalize_text(c).replace(" ", "") for c in df.columns]
    return df

def search_error(df, query):
    q = normalize_text(query)
    if not q:
        return df.iloc[0:0]

    mask = pd.Series(False, index=df.index)
    for col in df.columns:
        mask |= df[col].astype(str).apply(normalize_text).str.contains(q, na=False)

    return df[mask]

def parse_err_file(file_bytes):
    text = file_bytes.decode("latin-1", errors="ignore")
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    results = []

    for line in lines:
        nums = re.findall(r"\d+", line)
        if len(nums) >= 4:
            results.append(" ".join(nums[:4]))
        elif len(line) > 20:
            results.append(line)

    return list(dict.fromkeys(results))

# ---------------- LOGIN ----------------
def login():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if st.session_state.logged_in:
        return

    st.title("🔐 Acceso ADUAVIR")
    user = st.text_input("Usuario")
    pwd = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        if user in USERS and USERS[user]["pwd"] == pwd:
            st.session_state.logged_in = True
            st.session_state.user = user
            st.session_state.role = USERS[user]["role"]
            st.experimental_rerun()
        else:
            st.error("Usuario o contraseña incorrectos")

    st.stop()

# ---------------- APP ----------------
login()

st.title("🧭 ADUAVIR — Diagnóstico Aduanal")
st.caption("Detectamos, advertimos y acompañamos")

df = load_catalog()
st.success(f"Catálogo cargado ({len(df)} registros)")

# -------- Upload ERR --------
st.markdown("## 📄 Diagnóstico desde archivo del validador (.err)")
uploaded = st.file_uploader("Sube tu archivo .err", type=["err", "txt"])

if uploaded:
    queries = parse_err_file(uploaded.read())
    st.info(f"Se detectaron {len(queries)} posibles errores")

    selected = st.selectbox("Selecciona un error detectado", queries)
    if selected:
        results = search_error(df, selected)
        if results.empty:
            st.warning("No se encontraron coincidencias en el catálogo")
        else:
            st.dataframe(results, use_container_width=True)

st.markdown("---")

# -------- Búsqueda Manual --------
st.markdown("## 🔎 Búsqueda manual")
query = st.text_input("Código, registro, campo o texto del error")

if st.button("Buscar"):
    results = search_error(df, query)
    if results.empty:
        st.warning("Sin coincidencias")
    else:
        st.dataframe(results, use_container_width=True)

st.caption("ADUAVIR © 2025 — Diagnóstico Aduanal")