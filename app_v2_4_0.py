# app_v2_4_0.py
"""
ADUAVIR 2.4.0 — Copilot Aduanal
- Búsqueda por columnas (registro, campo, tipo/codigo, secuencias numéricas)
- Multiusuario: admin (completo) + SUPERVISORA + SUPERVISOR (solo búsqueda)
- Bitácora de consultas (CSV descargable)
- Integración opcional con OpenAI (COPILOT) para generar razonamientos/interpretaciones
- Tema oscuro, logo fijo y marca (logo superpuesto, no como texto)
"""

import streamlit as st
import pandas as pd
import os
import re
import unicodedata
from datetime import datetime
from dotenv import load_dotenv
import io

# Opcional: OpenAI (solo si lo agregas a requirements)
try:
    import openai
except Exception:
    openai = None

# ==========================
# CONFIG
# ==========================
APP_TITLE = "🧭 ADUAVIR 2.4.0 — Copilot Aduanal"
PAGE_ICON = "🧭"
LAYOUT = "wide"

st.set_page_config(page_title=APP_TITLE, page_icon=PAGE_ICON, layout=LAYOUT)
load_dotenv()

# Si quieres que el Copilot funcione, coloca tu OPENAI_API_KEY en .env
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")  # puedes cambiarlo

if openai and OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# Usuarios: admin tiene privilegios (podrá descargar bitácora),
# supervisor y supervisora solo pueden buscar (no descargar)
USERS = {
    "aduavir_admin": {"pwd": "aduavir2025", "role": "admin"},
    "supervisora": {"pwd": "super2025", "role": "readonly"},
    "supervisor": {"pwd": "super2025", "role": "readonly"},
}

# Rutas / recursos
CATALOG_PATH = "catalogo_errores_unificado_CORREGIDO.xlsx"
LOG_PATH = "consultas_log.csv"
LOGO_URL = "https://raw.githubusercontent.com/vvilla940401-netizen/aduavir-web/main/assets/logo_aduavir.png"

# ==========================
# UI: estilo (dark theme + logo superpuesto)
# ==========================
st.markdown(
    f"""
    <style>
      :root {{
        --bg: #0b0b0d;
        --panel: #0f1720;
        --accent: #c21b2b; /* rojo del logo */
        --muted: #9aa6b2;
        color-scheme: dark;
      }}
      .app-container {{
        background-color: var(--bg) !important;
        color: #e6eef6;
      }}
      .block {{
        background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
        padding:18px; border-radius:12px; box-shadow: 0 6px 20px rgba(0,0,0,0.6);
      }}
      /* Header */
      .header {{ display:flex; align-items:center; gap:18px; padding:6px 0 18px 0; }}
      .header img {{ height:72px; border-radius:8px; box-shadow:0 4px 18px rgba(0,0,0,0.6); }}
      .app-title {{ font-size:22px; margin:0; color:var(--accent); }}
      .app-sub {{ margin:0; color:var(--muted); font-size:13px; }}

      /* Watermark/logo fixed (solo imagen, sin texto superpuesto) */
      .bg-logo {{
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        opacity: 0.20; /* ajustable (0.05 - 0.30) */
        width: 60%;
        max-width: 1200px;
        z-index: 0;
        pointer-events: none;
        filter: grayscale(0%) contrast(1);
      }}

      /* Result card */
      .result-card {{ background: rgba(255,255,255,0.03); padding:16px; border-radius:10px; margin-bottom:12px; z-index:1; }}
      .small-muted {{ color:var(--muted); font-size:13px; }}

      /* Aumentar ancho de dataframes para ocupar pantalla */
      .stDataFrame table {{ width:100% !important; }}

      /* Botones */
      .big-btn .stButton>button {{ padding:10px 12px; font-weight:600; background:linear-gradient(90deg,var(--accent),#ff6b6b); border: none; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# logo superpuesto (marca de agua como imagen fija, sin texto encima)
st.markdown(f'<img class="bg-logo" src="{LOGO_URL}" alt="logo">', unsafe_allow_html=True)

# Header visible
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

# ==========================
# UTIL: cargar catálogo y normalizar columnas
# ==========================
@st.cache_data
def load_catalog(path=CATALOG_PATH):
    """Carga catálogo y devuelve (df_normalizado, mapa_original_a_normalizado)"""
    try:
        df = pd.read_excel(path, dtype=str).fillna("")
    except FileNotFoundError:
        st.error(f"⚠️ No encontré el archivo de catálogo: {path}. Sube el Excel corregido.")
        return pd.DataFrame(), {}

    orig_map = {}

    def _norm_col(c):
        s = str(c).strip()
        s_norm = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("ASCII")
        s_norm = re.sub(r"[^A-Za-z0-9]", "", s_norm).lower()
        orig_map[s_norm] = c
        return s_norm

    df.columns = [_norm_col(c) for c in df.columns]
    return df, orig_map


def normalize_text(t):
    if not isinstance(t, str):
        return ""
    s = t.lower()
    s = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("ASCII")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ==========================
# BÚSQUEDA: detección de filtros y lógica
# ==========================
def detect_column_filter(q):
    """Detecta queries del tipo 'registro 701', 'campo 3', 'tipo 1', 'codigo 2'."""
    qnorm = q.lower()
    col_aliases = {
        "registro": ["registro", "reg"],
        "campo": ["campo", "cam"],
        "codigo": ["codigo", "cod"],
        "tipo": ["tipo", "clase"],
    }
    for key, aliases in col_aliases.items():
        for a in aliases:
            # coincide 'registro 701' o 'registro:701' o 'registro=701'
            m = re.search(rf"\b{re.escape(a)}\b\W*(\d+)\b", qnorm)
            if m:
                return key, m.group(1)
    return None, None


def parse_numeric_sequence(q):
    """Intenta extraer secuencias 1 3 353 6 o '133536' y mapear a codigo,tipo,registro,campo."""
    nums = re.findall(r"\d+", q)
    if len(nums) >= 4:
        return {"codigo": nums[0], "tipo": nums[1], "registro": nums[2], "campo": nums[3]}
    joined = re.sub(r"\D", "", q)
    if len(joined) == 6:
        return {
            "codigo": joined[0],
            "tipo": joined[1],
            "registro": joined[2:5],
            "campo": joined[5],
        }
    return {}


def search_error(df, query, limit=50):
    """
    Lógica de búsqueda:
    - Si detecta secuencia numérica de 4 -> filtra por esas columnas exactamente.
    - Si detecta 'registro 701' -> filtro en la columna registro exacto.
    - En búsquedas libres -> busca en columnas de DESCRIPCION DE ERROR, SOLUCION, OBSERVACION/EJEMPLO (prioritarias).
    """
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
            if p in df.columns:
                return p
        return None

    # 1) secuencia compuesta
    if seq:
        mask = pd.Series([True] * len(df), index=df.index)
        for k, v in seq.items():
            c = find_col([expected.get(k, k), k, "clase" if k == "tipo" else None])
            if c:
                mask &= df[c].astype(str).str.strip() == str(v)
        return df[mask].head(limit)

    # 2) filtro por columna explícita
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
        else:
            # columna no encontrada en catálogo -> devolver vacío
            return df.iloc[0:0]

    # 3) búsqueda libre en columnas prioritarias
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
            # search normalized text
            mask |= df[c].astype(str).apply(normalize_text).str.contains(qnorm, na=False)
        except Exception:
            try:
                mask |= df[c].astype(str).str.contains(q, na=False, regex=False)
            except Exception:
                pass

    # también buscar números sueltos (e.g., "701") dentro de candidate_cols si el texto es numérico
    nums = re.findall(r"\d+", q)
    for n in nums:
        for c in candidate_cols:
            try:
                mask |= df[c].astype(str).str.contains(n, na=False, regex=False)
            except Exception:
                pass

    return df[mask].head(limit)


# ==========================
# BITÁCORA / LOG
# ==========================
def log_query(user: str, columna: str, consulta: str, resultados: int):
    row = {
        "fecha_hora": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "usuario": user,
        "columna_filtrada": columna or "",
        "consulta": consulta,
        "resultados": int(resultados),
    }
    df_row = pd.DataFrame([row])
    # crear/append
    if not os.path.exists(LOG_PATH):
        df_row.to_csv(LOG_PATH, index=False, encoding="utf-8-sig")
    else:
        df_row.to_csv(LOG_PATH, index=False, mode="a", header=False, encoding="utf-8-sig")


def get_log_bytesio():
    if not os.path.exists(LOG_PATH):
        return None
    with open(LOG_PATH, "rb") as f:
        return io.BytesIO(f.read())


# ==========================
# COPILOT: llamada a OpenAI (opcional)
# ==========================
def copilot_interpretation(prompt_text: str, max_tokens: int = 512):
    """
    Llama a OpenAI para obtener un razonamiento / explicación breve.
    Si openai o OPENAI_API_KEY no están disponibles, devuelve None.
    """
    if not openai or not OPENAI_API_KEY:
        return None

    system_prompt = (
        "Eres un asistente experto en aduanas y comercio exterior (México). "
        "Oferta una respuesta compacta y práctica: (1) Interpretación técnica breve, "
        "(2) Explicación en lenguaje operativo, (3) Referencia normativa si aplica. "
        "Sé conciso y directo (máximo 6 frases)."
    )

    try:
        # usar Chat Completions (compatibilidad amplia)
        resp = openai.ChatCompletion.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt_text},
            ],
            max_tokens=max_tokens,
            temperature=0.2,
        )
        # acceder respuesta
        content = resp.choices[0].message.content.strip()
        return content
    except Exception as e:
        # no fallar la app por la falla del Copilot
        st.warning(f"⚠️ Copilot no disponible: {e}")
        return None


# ==========================
# LOGIN MULTIUSUARIO SIMPLE
# ==========================
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
            st.experimental_rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


login_widget()

# ==========================
# MAIN APP
# ==========================
st.markdown("<div class='block'>", unsafe_allow_html=True)
with st.spinner("Cargando catálogo..."):
    df_catalog, orig_map = load_catalog()
    # guardar mapping en session para usar nombres originales
    st.session_state["orig_map"] = orig_map

if df_catalog.empty:
    st.error("Catálogo vacío o no encontrado; verifica el archivo.")
    st.stop()

st.success(f"Catálogo cargado ({len(df_catalog)} filas).")
st.markdown("### Buscar error o consulta normativa")

# input
query = st.text_input(
    "Ingrese código, registro, campo o descripción:",
    placeholder="Ejemplo: 1 3 353 6 | registro 701 | campo 3 | tipo 1 | texto del error",
)

# layout: búsqueda + botones
col_search, col_action, col_log = st.columns([4, 1, 1])

with col_action:
    buscar = st.button("🔍 Buscar", key="buscar_btn")

with col_log:
    # Admin puede descargar bitácora; readonly no.
    if st.session_state.get("role") == "admin":
        log_bio = get_log_bytesio()
        if log_bio:
            st.download_button(
                "📥 Descargar bitácora (CSV)",
                data=log_bio,
                file_name="consultas_log.csv",
                mime="text/csv",
            )
        else:
            st.info("Aún no hay registros en la bitácora.")
    else:
        st.caption("Usuario: " + (st.session_state.get("user") or ""))

# cuando el usuario presiona buscar
if buscar:
    user_now = st.session_state.get("user", "anon")
    results = search_error(df_catalog, query or "", limit=50)

    # determinar columna filtrada para log
    detected_col, detected_val = detect_column_filter(query or "")
    seq = parse_numeric_sequence(query or "")
    col_for_log = ""
    if detected_col:
        col_for_log = f"{detected_col}:{detected_val}"
    elif seq:
        col_for_log = ",".join([f"{k}:{v}" for k, v in seq.items()])

    st.markdown('<div class="result-card">', unsafe_allow_html=True)

    if results is not None and not results.empty:
        # mostrar solo campos solicitados por ti (orden fijo)
        prefer = ["tipo", "registro", "campo", "descripciondeerror", "solucion", "observacionejemplo", "ejemplo", "llenadoobservaciones"]
        show_cols = [c for c in prefer if c in results.columns]
        if not show_cols:
            # fallback: primeras 6 columnas
            show_cols = list(results.columns[:6])

        # renombrar columnas a encabezados legibles usando orig_map (si disponible)
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
                # usar nombre original si existe, en mayúsculas limpias
                nice = orig.upper() if isinstance(orig, str) else c.upper()
            rename_map[c] = nice

        display_df = results[show_cols].reset_index(drop=True).rename(columns=rename_map)

        st.markdown(f"**Consulta:** {query}")
        st.write(f"Se encontraron **{len(results)}** coincidencias (mostrando hasta 50).")

        # mostrar en toda la pantalla (dataframe ancho)
        st.dataframe(display_df, use_container_width=True, height=700)

        # si Copilot disponible y la consulta es específica (p.e. secuencia completa o una fila única), pedir interpretación
        copilot_out = None
        # heurística: si la búsqueda devolvió 1 fila EXACTA para un registro/campo/codigo -> pedir razonamiento
        if (len(results) == 1) or (seq and len(results) <= 5):
            # construir prompt con contexto (primera fila o las filas)
            sample = results.iloc[0].to_dict()
            # mapear nombres originales para leer mejor
            sample_readable = {st.session_state.get("orig_map", {}).get(k, k): v for k, v in sample.items()}
            prompt_lines = ["Consulta enviada: " + (query or ""), "", "Fila encontrada (campos relevantes):"]
            for k, v in sample_readable.items():
                prompt_lines.append(f"- {k}: {v}")
            prompt_lines.append("")
            prompt_lines.append("Proporciona: (1) interpretación técnica breve, (2) explicación para el operador, (3) pasos sugeridos (máximo 5) y (4) referencia normativa si aplica.")
            prompt_text = "\n".join(prompt_lines)
            copilot_out = copilot_interpretation(prompt_text, max_tokens=300)

            if copilot_out:
                st.markdown("### 🤖 Interpretación (Copilot Aduanal)")
                st.write(copilot_out)

        # registrar en log
        log_query(user_now, col_for_log, query or "", len(results))

    else:
        st.warning("⚠️ No se encontraron coincidencias para la consulta.")
        log_query(user_now, col_for_log, query or "", 0)

    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")
st.caption("ADUAVIR — Plataforma interna © 2025 — Copilot Aduanal (integración OpenAI opcional)")