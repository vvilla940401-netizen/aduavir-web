# app_v2_5_0.py
"""
ADUAVIR 2.5.0 — Copilot Aduanal Interactivo
- Búsqueda por columnas (registro, campo, tipo/codigo, secuencias numéricas)
- Multiusuario: admin (completo) + SUPERVISORA + SUPERVISOR (solo búsqueda)
- Bitácora de consultas (CSV descargable)
- Integración opcional con OpenAI (Copilot) — compatible con openai>=1.0.0 y versiones antiguas
- Tema oscuro, logo fijo y marca (logo superpuesto, sin texto encima)
- Selección de fila para invocar la interpretación de Copilot
"""
import streamlit as st
import pandas as pd
import os
import re
import unicodedata
from datetime import datetime
from dotenv import load_dotenv
import io
import traceback

# Intentar importar openai (opcional)
try:
    import openai
    from openai import OpenAI as OpenAIClient  # puede no existir en versiones antiguas
except Exception:
    openai = None
    OpenAIClient = None

# --------------------
# Configuración inicial
# --------------------
APP_TITLE = "🧭 ADUAVIR 2.5.0 — Copilot Aduanal"
st.set_page_config(page_title=APP_TITLE, page_icon="🧭", layout="wide")
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# Usuarios
USERS = {
    "aduavir_admin": {"pwd": "aduavir2025", "role": "admin"},
    "supervisora": {"pwd": "super2025", "role": "readonly"},
    "supervisor": {"pwd": "super2025", "role": "readonly"},
}

# Rutas
CATALOG_PATH = "catalogo_errores_unificado_CORREGIDO.xlsx"
LOG_PATH = "consultas_log.csv"
LOGO_URL = "https://raw.githubusercontent.com/vvilla940401-netizen/aduavir-web/main/assets/logo_aduavir.png"

# --------------------
# Estilos / UI (dark + logo)
# --------------------
st.markdown(
    f"""
    <style>
      :root {{
        --bg: #050506;
        --panel: #0f1113;
        --accent: #c21b2b;
        --muted: #9aa6b2;
        color-scheme: dark;
      }}
      .block {{ background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01)); padding:18px; border-radius:12px; box-shadow: 0 6px 20px rgba(0,0,0,0.6); z-index:2; }}
      .header {{ display:flex; align-items:center; gap:18px; padding:6px 0 18px 0; z-index:2; }}
      .header img {{ height:72px; border-radius:8px; box-shadow:0 6px 22px rgba(0,0,0,0.6); }}
      .app-title {{ font-size:22px; margin:0; color:var(--accent); }}
      .app-sub {{ margin:0; color:var(--muted); font-size:13px; }}
      .bg-logo {{
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        opacity: 0.20; /* ajustable */
        width: 70%;
        max-width: 1400px;
        z-index:0;
        pointer-events: none;
        filter: none;
      }}
      .result-card {{ background: rgba(255,255,255,0.03); padding:16px; border-radius:10px; margin-bottom:12px; z-index:2; }}
      .stDataFrame table {{ width:100% !important; }}
      .big-btn .stButton>button {{ padding:10px 12px; font-weight:600; background:linear-gradient(90deg,var(--accent),#ff6b6b); border: none; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# Logo de fondo (imagen, sin texto encima)
st.markdown(f'<img class="bg-logo" src="{LOGO_URL}" alt="logo">', unsafe_allow_html=True)

# Header
st.markdown(
    f"""
    <div class="header">
      <img src="{LOGO_URL}" alt="logo">
      <div>
        <div class="app-title">{APP_TITLE}</div>
        <div class="app-sub">Su aliado en el cumplimiento — Modo pruebas</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# --------------------
# Utilidades: carga/normalización
# --------------------
@st.cache_data
def load_catalog(path=CATALOG_PATH):
    """
    Carga el Excel, normaliza nombres de columnas a claves simples (sin espacios ni tildes)
    y devuelve (df_normalizado, mapa_original)
    Además remueve columnas vacías por completo.
    """
    try:
        df = pd.read_excel(path, dtype=str).fillna("")
    except FileNotFoundError:
        return pd.DataFrame(), {}

    orig_map = {}

    def _norm_col(c):
        s = str(c).strip()
        s_norm = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("ASCII")
        s_norm = re.sub(r"[^A-Za-z0-9]", "", s_norm).lower()
        orig_map[s_norm] = c
        return s_norm

    df.columns = [_norm_col(c) for c in df.columns]

    # eliminar columnas completamente vacías (después de normalizar)
    to_drop = [c for c in df.columns if df[c].astype(str).str.strip().eq("").all()]
    if to_drop:
        df = df.drop(columns=to_drop)

    return df, orig_map


def normalize_text(t):
    if not isinstance(t, str):
        return ""
    s = t.lower()
    s = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("ASCII")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# --------------------
# Detección de filtros y búsqueda
# --------------------
def detect_column_filter(q):
    qnorm = (q or "").lower()
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
    nums = re.findall(r"\d+", q or "")
    if len(nums) >= 4:
        return {"codigo": nums[0], "tipo": nums[1], "registro": nums[2], "campo": nums[3]}
    joined = re.sub(r"\D", "", q or "")
    if len(joined) == 6:
        return {"codigo": joined[0], "tipo": joined[1], "registro": joined[2:5], "campo": joined[5]}
    return {}


def search_error(df: pd.DataFrame, query: str, limit: int = 50) -> pd.DataFrame:
    if df is None or df.empty or not query or not str(query).strip():
        return df.iloc[0:0]
    q = query.strip()
    qnorm = normalize_text(q)
    seq = parse_numeric_sequence(q)
    col_key, col_val = detect_column_filter(q)

    expected = {
        "codigo": "codigo",
        "tipo": "tipo",
        "registro": "registro",
        "campo": "campo",
        "descripcion": "descripciondeerror",
        "solucion": "solucion",
        "observacion": "observacionejemplo",
    }

    def find_col(possible_list):
        for p in possible_list:
            if p and p in df.columns:
                return p
        return None

    # 1) Secuencia completa -> filtros exactos compuestos
    if seq:
        mask = pd.Series([True] * len(df), index=df.index)
        for k, v in seq.items():
            c = find_col([expected.get(k, k), k, "clase" if k == "tipo" else None])
            if c:
                mask &= df[c].astype(str).str.strip() == str(v)
        return df[mask].head(limit)

    # 2) Filtro por columna explícita (ej: "registro 701")
    if col_key:
        colmap = {
            "registro": [expected["registro"], "registro"],
            "campo": [expected["campo"], "campo"],
            "codigo": [expected["codigo"], "codigo"],
            "tipo": [expected["tipo"], "tipo", "clase"],
        }
        c = find_col(colmap[col_key])
        if c:
            mask = df[c].astype(str).str.strip() == str(col_val)
            return df[mask].head(limit)
        return df.iloc[0:0]

    # 3) Búsqueda libre en columnas prioritarias
    candidate_cols = [
        c
        for c in [
            "descripciondeerror",
            "errordescripcion",
            "solucion",
            "observacionejemplo",
            "ejemplo",
            "llenadoobservaciones",
        ]
        if c in df.columns
    ]
    if not candidate_cols:
        candidate_cols = list(df.columns)

    mask = pd.Series([False] * len(df), index=df.index)
    for c in candidate_cols:
        try:
            mask |= df[c].astype(str).apply(normalize_text).str.contains(qnorm, na=False)
        except Exception:
            try:
                mask |= df[c].astype(str).str.contains(q, na=False, regex=False)
            except Exception:
                pass

    # también buscar números sueltos
    nums = re.findall(r"\d+", q)
    for n in nums:
        for c in candidate_cols:
            try:
                mask |= df[c].astype(str).str.contains(n, na=False, regex=False)
            except Exception:
                pass

    return df[mask].head(limit)


# --------------------
# Bitácora
# --------------------
def log_query(user: str, columna: str, consulta: str, resultados: int):
    row = {
        "fecha_hora": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "usuario": user,
        "columna_filtrada": columna or "",
        "consulta": consulta,
        "resultados": int(resultados),
    }
    df_row = pd.DataFrame([row])
    if not os.path.exists(LOG_PATH):
        df_row.to_csv(LOG_PATH, index=False, encoding="utf-8-sig")
    else:
        df_row.to_csv(LOG_PATH, index=False, mode="a", header=False, encoding="utf-8-sig")


def get_log_bytesio():
    if not os.path.exists(LOG_PATH):
        return None
    with open(LOG_PATH, "rb") as f:
        return io.BytesIO(f.read())


# --------------------
# Copilot (OpenAI) — wrapper compatible
# --------------------
def copilot_interpretation(prompt_text: str, max_tokens: int = 512):
    if not OPENAI_API_KEY or not openai:
        return None, "Copilot no configurado (OPENAI_API_KEY faltante o paquete openai no instalado)."

    # intentar compatibilidad con openai>=1.0.0 (client style)
    try:
        # new client - si está disponible
        if OpenAIClient is not None:
            client = OpenAIClient(api_key=OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Eres un asistente experto en aduanas (México). Responde breve y práctico."},
                    {"role": "user", "content": prompt_text},
                ],
                max_tokens=max_tokens,
                temperature=0.2,
            )
            content = resp.choices[0].message.content.strip()
            return content, None
        # fallback: try old openai.ChatCompletion if available
        elif hasattr(openai, "ChatCompletion"):
            openai.api_key = OPENAI_API_KEY
            resp = openai.ChatCompletion.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Eres un asistente experto en aduanas (México). Responde breve y práctico."},
                    {"role": "user", "content": prompt_text},
                ],
                max_tokens=max_tokens,
                temperature=0.2,
            )
            content = resp.choices[0].message.content.strip()
            return content, None
        else:
            # último recurso: usar openai.Completion (antiguo)
            openai.api_key = OPENAI_API_KEY
            resp = openai.Completion.create(
                engine=OPENAI_MODEL,
                prompt=prompt_text,
                max_tokens=max_tokens,
                temperature=0.2,
            )
            content = resp.choices[0].text.strip()
            return content, None
    except Exception as e:
        # devolver mensaje de error útil para debug (pero no romper app)
        return None, f"Copilot no disponible: {str(e)}"


# --------------------
# Login simple (SIN llamadas experimentales)
# --------------------
def login_widget():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.role = None

    if st.session_state.logged_in:
        return True

    st.markdown("<div class='block'>", unsafe_allow_html=True)
    st.write("**Acceso**")
    user = st.text_input("Usuario", key="login_user")
    pwd = st.text_input("Contraseña", type="password", key="login_pwd")
    if st.button("Ingresar", key="login_btn"):
        if user in USERS and pwd == USERS[user]["pwd"]:
            st.session_state.logged_in = True
            st.session_state.user = user
            st.session_state.role = USERS[user]["role"]
            # No llamamos a st.experimental_rerun(); Streamlit ya re-ejecutará por el cambio en session_state
        else:
            st.error("Usuario o contraseña incorrectos.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


# --------------------
# Main
# --------------------
login_widget()

st.markdown("<div class='block'>", unsafe_allow_html=True)
with st.spinner("Cargando catálogo..."):
    df_catalog, orig_map = load_catalog()
    st.session_state["orig_map"] = orig_map

if df_catalog.empty:
    st.error("Catálogo vacío o no encontrado; verifica el archivo.")
    st.stop()

st.success(f"Catálogo cargado ({len(df_catalog)} filas).")
st.markdown("### Buscar error o consulta normativa")

# Entrada de búsqueda
query = st.text_input(
    "Ingrese código, registro, campo o descripción:",
    placeholder="Ejemplo: 1 3 353 6 | registro 701 | campo 3 | tipo 1 | texto del error",
)

col_search, col_action, col_log = st.columns([4, 1, 1])
with col_action:
    buscar = st.button("🔍 Buscar", key="buscar_btn")
with col_log:
    if st.session_state.get("role") == "admin":
        log_bio = get_log_bytesio()
        if log_bio:
            st.download_button("📥 Descargar bitácora (CSV)", data=log_bio, file_name="consultas_log.csv", mime="text/csv")
        else:
            st.info("Aún no hay registros en la bitácora.")
    else:
        st.caption("Usuario: " + (st.session_state.get("user") or ""))

# Ejecutar búsqueda al presionar Buscar
if buscar:
    user_now = st.session_state.get("user", "anon")
    results = search_error(df_catalog, query or "", limit=50)

    # Registrar metadatos de búsqueda
    detected_col, detected_val = detect_column_filter(query or "")
    seq = parse_numeric_sequence(query or "")
    col_for_log = ""
    if detected_col:
        col_for_log = f"{detected_col}:{detected_val}"
    elif seq:
        col_for_log = ",".join([f"{k}:{v}" for k, v in seq.items()])

    st.markdown('<div class="result-card">', unsafe_allow_html=True)

    if results is not None and not results.empty:
        # columnas preferidas a mostrar (asegurar que existan)
        prefer = ["tipo", "registro", "campo", "descripciondeerror", "solucion", "observacionejemplo"]
        show_cols = [c for c in prefer if c in results.columns]
        if not show_cols:
            show_cols = list(results.columns[:6])

        # renombrar usando orig_map (si está)
        rename_map = {}
        for c in show_cols:
            orig = st.session_state.get("orig_map", {}).get(c, c)
            if c == "descripciondeerror":
                nice = "DESCRIPCIÓN DE ERROR"
            elif c in ["observacionejemplo", "ejemplo"]:
                nice = "OBSERVACIÓN / EJEMPLO"
            elif c == "solucion":
                nice = "SOLUCIÓN"
            else:
                nice = orig.upper() if isinstance(orig, str) else c.upper()
            rename_map[c] = nice

        display_df = results[show_cols].reset_index(drop=True).rename(columns=rename_map)

        st.markdown(f"**Consulta:** {query}")
        st.write(f"Se encontraron **{len(results)}** coincidencias (mostrando hasta 50).")

        # Mostrar tabla (ancha)
        st.dataframe(display_df, use_container_width=True, height=700)

        # SELECT para escoger una fila y obtener interpretación
        # Construir lista de opciones tipo "fila_idx - TIPO | REGISTRO | CAMPO | primera parte de descripción"
        options = []
        for i, row in results[show_cols].reset_index(drop=True).iterrows():
            tipo = str(row.get("tipo", "")) if "tipo" in row.index else ""
            registro = str(row.get("registro", "")) if "registro" in row.index else ""
            campo = str(row.get("campo", "")) if "campo" in row.index else ""
            desc = str(row.get(rename_map.get("descripciondeerror","DESCRIPCIÓN DE ERROR"), "")) if "descripciondeerror" in show_cols else ""
            # reduce desc
            short = (desc[:80] + "...") if desc and len(desc) > 80 else desc
            label = f"{i} — tipo:{tipo} registro:{registro} campo:{campo} » {short}"
            options.append((label, i))

        st.markdown("**Selecciona una fila para obtener interpretación (Copilot):**")
        selected_label = st.selectbox("Selecciona fila", [o[0] for o in options], key="select_fila")
        selected_idx = None
        # buscar index
        for lbl, idx in options:
            if lbl == selected_label:
                selected_idx = idx
                break

        if selected_idx is not None:
            # obtener fila original del dataframe results (no renombrado)
            fila = results.reset_index(drop=True).iloc[selected_idx]
            # preparar prompt
            sample = fila.to_dict()
            sample_readable = {st.session_state.get("orig_map", {}).get(k, k): v for k, v in sample.items()}
            prompt_lines = ["Consulta enviada: " + (query or ""), "", "Fila encontrada (campos relevantes):"]
            for k, v in sample_readable.items():
                prompt_lines.append(f"- {k}: {v}")
            prompt_lines.append("")
            prompt_lines.append(
                "Proporciona: (1) interpretación técnica breve, (2) explicación para el operador, (3) pasos sugeridos (máximo 5) y (4) referencia normativa si aplica."
            )
            prompt_text = "\n".join(prompt_lines)

            # Llamar Copilot (si está configurado)
            copilot_out, copilot_err = copilot_interpretation(prompt_text, max_tokens=400)
            if copilot_out:
                st.markdown("### 🤖 Interpretación (Copilot Aduanal)")
                st.write(copilot_out)
            else:
                st.info("Copilot no disponible o no respondió. " + (copilot_err or ""))

        # log
        log_query(user_now, col_for_log, query or "", len(results))

    else:
        st.warning("No se encontraron coincidencias para la consulta.")
        log_query(user_now, col_for_log, query or "", 0)

    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")
st.caption("ADUAVIR — Plataforma interna © 2025 — Copilot Aduanal (OpenAI opcional)")