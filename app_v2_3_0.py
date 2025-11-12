# app_v2_3_0.py
import streamlit as st
import pandas as pd
import os
import re
import unicodedata
from datetime import datetime
from dotenv import load_dotenv
import io

# ===========================
# CONFIGURACIÓN INICIAL
# ===========================
st.set_page_config(page_title="ADUAVIR 2.3.0", page_icon="🧭", layout="wide")
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

SINGLE_USER = {"user": "aduavir_admin", "password": "aduavir2025"}
CATALOG_PATH = "catalogo_errores_unificado_CORREGIDO.xlsx"
LOG_PATH = "consultas_log.csv"
LOGO_URL = "https://raw.githubusercontent.com/vvilla940401-netizen/aduavir-web/main/assets/logo_aduavir.png"

# ===========================
# ESTILOS Y COLORES
# ===========================
st.markdown(f"""
<style>
:root {{
  --main-blue: #00aaff;
  --muted: #a9b8c7;
  --bg-black: #000;
}}
[data-testid="stAppViewContainer"] {{
  background-color: var(--bg-black);
  background-image: url('{LOGO_URL}');
  background-repeat: no-repeat;
  background-position: center;
  background-size: 70%;
  opacity: 0.06;
}}
.header {{
  display:flex; align-items:center; gap:18px; padding:8px 0;
}}
.header img {{
  height:72px; border-radius:6px;
}}
.app-title {{
  color:var(--main-blue); font-size:28px; margin:0;
}}
.app-sub {{
  color:var(--muted); margin:0; font-size:14px;
}}
.block {{
  background: rgba(10,10,10,0.92);
  padding:20px;
  border-radius:12px;
  box-shadow:0 6px 18px rgba(0,0,0,0.6);
  color:white;
}}
.result-card {{
  background: rgba(18,18,18,0.95);
  padding:16px;
  border-radius:10px;
  margin-bottom:12px;
  color:white;
}}
.stButton>button {{
  background-color: var(--main-blue);
  color: white;
  border:none;
  padding:10px 18px;
  border-radius:8px;
  font-weight:bold;
}}
.stButton>button:hover {{
  background-color:#007acc;
}}
.stTextInput>div>div>input {{
  background-color: #121212;
  color: white;
  border:1px solid #00aaff;
  border-radius:6px;
}}
[data-testid="stDataFrame"] div div div table {{
  color: white !important;
  background-color: #111 !important;
}}
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="header">
  <img src="{LOGO_URL}" alt="logo">
  <div>
    <h1 class="app-title">🧭 ADUAVIR 2.3.0</h1>
    <div class="app-sub">Su aliado en el cumplimiento</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ===========================
# CARGA DE CATÁLOGO
# ===========================
@st.cache_data
def load_catalog(path=CATALOG_PATH):
    df = pd.read_excel(path, dtype=str).fillna("")
    orig_map = {}
    def _norm_col(c):
        s = str(c).strip()
        s_norm = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("ASCII")
        s_norm = re.sub(r"[^A-Za-z0-9]", "", s_norm).lower()
        orig_map[s_norm] = c
        return s_norm
    df.columns = [_norm_col(c) for c in df.columns]
    return df, orig_map

def normalize_text(text):
    if not isinstance(text, str):
        return ""
    s = text.lower()
    s = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("ASCII")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

# ===========================
# DETECCIÓN DE CONSULTAS
# ===========================
def detect_column_filter(q):
    qnorm = q.lower()
    col_aliases = {
        "registro": ["registro", "reg"],
        "campo": ["campo", "cam"],
        "codigo": ["codigo", "cod"],
        "tipo": ["tipo", "clase"],
    }
    for key, aliases in col_aliases.items():
        for a in aliases:
            m = re.search(rf"\b{re.escape(a)}\b\W*(\d+)\b", qnorm)
            if m:
                return key, m.group(1)
    return None, None

def parse_numeric_sequence(q):
    nums = re.findall(r"\d+", q)
    if len(nums) >= 4:
        return {"codigo": nums[0], "tipo": nums[1], "registro": nums[2], "campo": nums[3]}
    joined = re.sub(r"\D", "", q)
    if len(joined) == 6:
        return {"codigo": joined[0], "tipo": joined[1], "registro": joined[2:5], "campo": joined[5]}
    return {}

# ===========================
# BÚSQUEDA PRINCIPAL
# ===========================
def search_error(df, query, limit=25):
    if df.empty or not query.strip():
        return df.iloc[0:0]
    q = query.strip()
    qnorm = normalize_text(q)
    expected = {
        "codigo": "codigo", "tipo": "tipo", "registro": "registro", "campo": "campo",
        "descripcion": "descripciondeerror", "solucion": "solucion", "observacion": "observacionejemplo",
    }
    col_key, col_val = detect_column_filter(q)
    seq = parse_numeric_sequence(q)
    def find_col(possible):
        for p in possible:
            if p in df.columns:
                return p
        return None
    if seq:
        mask = pd.Series([True] * len(df))
        for k, v in seq.items():
            c = find_col([expected.get(k, k), k])
            if c:
                mask &= df[c].astype(str).str.strip() == str(v)
        return df[mask].head(limit)
    if col_key:
        c = find_col([expected[col_key], col_key])
        if c:
            mask = df[c].astype(str).str.strip() == str(col_val)
            return df[mask].head(limit)
    candidate_cols = [c for c in ["descripciondeerror", "solucion", "observacionejemplo", "ejemplo", "llenadoobservaciones"] if c in df.columns]
    mask = pd.Series([False] * len(df))
    for c in candidate_cols:
        mask |= df[c].astype(str).apply(normalize_text).str.contains(qnorm, na=False)
    return df[mask].head(limit)

# ===========================
# BITÁCORA
# ===========================
def log_query(user, columna, consulta, resultados):
    row = {
        "fecha_hora": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "usuario": user, "columna_filtrada": columna or "",
        "consulta": consulta, "resultados": int(resultados),
    }
    df_row = pd.DataFrame([row])
    df_row.to_csv(LOG_PATH, index=False, mode="a", header=not os.path.exists(LOG_PATH), encoding="utf-8-sig")

def get_log_bytesio():
    if not os.path.exists(LOG_PATH): return None
    with open(LOG_PATH, "rb") as f: return io.BytesIO(f.read())

# ===========================
# LOGIN
# ===========================
def simple_login():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if st.session_state.logged_in:
        return True
    st.markdown("<div class='block'>", unsafe_allow_html=True)
    st.write("**Acceso restringido — área de pruebas**")
    user = st.text_input("Usuario")
    pwd = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        if user == SINGLE_USER["user"] and pwd == SINGLE_USER["password"]:
            st.session_state.logged_in = True
            st.session_state.user = user
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ===========================
# APP PRINCIPAL
# ===========================
simple_login()
st.markdown("<div class='block'>", unsafe_allow_html=True)
with st.spinner("Cargando catálogo..."):
    df_catalog, orig_map = load_catalog()
st.session_state["orig_map"] = orig_map

if df_catalog.empty:
    st.error("No se pudo cargar el catálogo.")
    st.stop()

st.success(f"Catálogo cargado ({len(df_catalog)} filas).")

query = st.text_input(
    "Ingrese código, registro o descripción:",
    placeholder="Ejemplo: 1 3 353 6 | registro 701 | tipo 1 | describir el error"
)

col1, col2, col3 = st.columns([3, 1, 1])
with col2:
    if st.button("Buscar"):
        current_user = st.session_state.get("user", SINGLE_USER["user"])
        results = search_error(df_catalog, query, limit=25)
        detected_col, detected_val = detect_column_filter(query)
        seq = parse_numeric_sequence(query)
        col_for_log = f"{detected_col}:{detected_val}" if detected_col else ",".join([f"{k}:{v}" for k,v in seq.items()]) if seq else ""
        st.markdown('<div class="result-card">', unsafe_allow_html=True)
        if not results.empty:
            prefer = ["tipo", "registro", "campo", "descripciondeerror", "solucion", "observacionejemplo"]
            show_cols = [c for c in prefer if c in results.columns]
            rename_map = {c: orig_map.get(c, c).upper() for c in show_cols}
            display_df = results[show_cols].reset_index(drop=True).rename(columns=rename_map)
            st.markdown(f"**Consulta:** {query}")
            st.write(f"Se encontraron **{len(results)}** coincidencias (mostrando hasta 25).")
            st.dataframe(display_df, use_container_width=True, height=720)
            log_query(current_user, col_for_log, query, len(results))
        else:
            st.warning("No se encontraron coincidencias.")
            log_query(current_user, col_for_log, query, 0)
        st.markdown("</div>", unsafe_allow_html=True)

with col3:
    log_bio = get_log_bytesio()
    if log_bio:
        st.download_button("📥 Descargar bitácora (CSV)", data=log_bio, file_name="consultas_log.csv", mime="text/csv")
    else:
        st.info("Aún no hay registros.")

st.markdown("---")
st.caption("ADUAVIR — Plataforma interna de consulta © 2025")