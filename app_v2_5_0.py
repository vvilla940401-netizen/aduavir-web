# app_v2_5_1.py
"""
ADUAVIR 2.5.1 — Diagnóstico Aduanal
- Búsqueda manual por código / registro / campo
- Upload de archivo .err del validador
- Parsing automático de errores
- Diagnóstico desde catálogo
- Copilot opcional (si hay API Key)
"""

import streamlit as st
import pandas as pd
import os
import re
import unicodedata
from dotenv import load_dotenv

# ---------------- CONFIG ----------------
st.set_page_config(page_title="ADUAVIR 2.5.1", layout="wide")
load_dotenv()

CATALOG_PATH = "catalogo_errores_unificado_CORREGIDO.xlsx"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

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

def parse_err_file(file_bytes):
    text = file_bytes.decode("latin-1", errors="ignore")
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    queries = []

    for line in lines:
        nums = re.findall(r"\b\d+\b", line)
        if len(nums) >= 4:
            queries.append(" ".join(nums[:4]))
        elif len(line) > 15:
            queries.append(line)

    return list(dict.fromkeys(queries))

def search_error(df, query):
    q = normalize_text(query)
    mask = df.apply(lambda row: q in normalize_text(" ".join(row.values)), axis=1)
    return df[mask]

# ---------------- UI ----------------
st.title("🧭 ADUAVIR — Diagnóstico Aduanal")
st.caption("Detectamos, advertimos y acompañamos")

df = load_catalog()

# -------- Upload ERR --------
st.markdown("## 📄 Diagnóstico desde archivo del validador (.err)")
uploaded = st.file_uploader("Sube tu archivo .err", type=["err", "txt"])

if uploaded:
    queries = parse_err_file(uploaded.read())
    st.success(f"Se detectaron {len(queries)} posibles errores")

    selected = st.selectbox("Selecciona un error detectado", queries)
    if selected:
        results = search_error(df, selected)
        if results.empty:
            st.warning("No se encontraron coincidencias")
        else:
            st.dataframe(results, use_container_width=True)

st.markdown("---")

# -------- Búsqueda Manual --------
st.markdown("## 🔎 Búsqueda manual")
query = st.text_input("Ingresa código, registro, campo o texto del error")

if st.button("Buscar"):
    results = search_error(df, query)
    if results.empty:
        st.warning("Sin coincidencias")
    else:
        st.dataframe(results, use_container_width=True)

st.caption("ADUAVIR © 2025 — Diagnóstico Aduanal")