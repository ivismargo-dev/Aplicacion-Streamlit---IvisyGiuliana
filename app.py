import streamlit as st
import pandas as pd
import requests

# --------------------------------------------------
# Configuración general
# --------------------------------------------------
st.set_page_config(
    page_title="Establecimientos de Salud en Chile",
    layout="wide"
)

# --------------------------------------------------
# Título
# --------------------------------------------------
st.title("🏥 Establecimientos de Salud en Chile")
st.write(
    """
    Aplicación desarrollada en **Python y Streamlit**, por Ivis Martínez y Giuliana Provoste, que analiza la distribución
    territorial de los establecimientos de salud en Chile, utilizando datos oficiales del portal **datos.gob.cl**.
    """
)

st.divider()

# --------------------------------------------------
# 1️⃣ Buscar dataset (CKAN)
# --------------------------------------------------
search_url = (
    "https://datos.gob.cl/api/3/action/package_search"
    "?q=establecimientos%20salud"
)

resp = requests.get(search_url).json()

if not resp.get("success") or resp["result"]["count"] == 0:
    st.error("No se pudo encontrar el dataset.")
    st.stop()

dataset = resp["result"]["results"][0]

# --------------------------------------------------
# 2️⃣ Obtener CSV
# --------------------------------------------------
csv_url = None
for r in dataset["resources"]:
    if r.get("format", "").lower() == "csv":
        csv_url = r["url"]
        break

if csv_url is None:
    st.error("El dataset no contiene CSV.")
    st.stop()

# --------------------------------------------------
# 3️⃣ Cargar CSV (robusto)
# --------------------------------------------------
df = pd.read_csv(
    csv_url,
    sep=";",
    encoding="latin-1",
    engine="python",
    on_bad_lines="skip"
)

df.columns = [c.strip().lower() for c in df.columns]

# --------------------------------------------------
# 4️⃣ Funciones auxiliares
# --------------------------------------------------
def buscar_columna(posibles):
    for col in df.columns:
        for p in posibles:
            if p in col:
                return col
    return None

def arreglar_tildes(texto):
    try:
        return texto.encode("latin-1").decode("utf-8")
    except:
        return texto

# --------------------------------------------------
# 5️⃣ Detectar columnas clave
# --------------------------------------------------
col_region_cod = buscar_columna(["regioncodigo"])
col_region_nom = buscar_columna(["regionglosa"])
col_comuna_nom = buscar_columna(["comunaglosa"])
col_estab_nom = buscar_columna(["establecimientoglosa"])

col_lat = buscar_columna(["latitud", "lat"])
col_lon = buscar_columna(["longitud", "lon"])

if not all([col_region_cod, col_region_nom, col_comuna_nom, col_estab_nom]):
    st.error("No se pudieron identificar columnas principales.")
    st.stop()

# --------------------------------------------------
# 6️⃣ Arreglar tildes
# --------------------------------------------------
for col in [col_region_nom, col_comuna_nom, col_estab_nom]:
    df[col] = df[col].astype(str).apply(arreglar_tildes)

# --------------------------------------------------
# 7️⃣ Ordenar regiones norte → sur
# --------------------------------------------------
regiones_df = (
    df[[col_region_cod, col_region_nom]]
    .drop_duplicates()
    .sort_values(col_region_cod)
)

regiones_ordenadas = regiones_df[col_region_nom].tolist()

# --------------------------------------------------
# 8️⃣ SIDEBAR
# --------------------------------------------------
st.sidebar.title("⚙️ Filtros")
region_sel = st.sidebar.selectbox(
    "Selecciona una región",
    regiones_ordenadas
)

df_region = df[df[col_region_nom] == region_sel]

# --------------------------------------------------
# 9️⃣ MÉTRICAS
# --------------------------------------------------
st.header("📌 Indicadores principales")

c1, c2 = st.columns(2)
c1.metric("Total de establecimientos", df_region.shape[0])
c2.metric("Tipos distintos", df_region[col_estab_nom].nunique())

st.divider()

# --------------------------------------------------
# 🔟 ANÁLISIS NACIONAL (ordenado)
# --------------------------------------------------
st.header("📊 Análisis Nacional")

conteo_region = (
    df.groupby(col_region_nom)
    .size()
    .reindex(regiones_ordenadas)
)

st.bar_chart(conteo_region)

st.divider()

# --------------------------------------------------
# 1️⃣1️⃣ ANÁLISIS REGIONAL
# --------------------------------------------------
st.header("🏥 Análisis Regional")

conteo_tipo = (
    df_region.groupby(col_estab_nom)
    .size()
    .sort_values(ascending=False)
)

st.bar_chart(conteo_tipo)

st.divider()

# --------------------------------------------------
# 1️⃣2️⃣ MAPA
# --------------------------------------------------
st.header("🗺️ Mapa de establecimientos")

if col_lat is not None and col_lon is not None:
    mapa_df = df_region[[col_lat, col_lon]].copy()

    # Convertir coordenadas a numérico
    mapa_df[col_lat] = pd.to_numeric(mapa_df[col_lat], errors="coerce")
    mapa_df[col_lon] = pd.to_numeric(mapa_df[col_lon], errors="coerce")

    # Eliminar filas inválidas
    mapa_df = mapa_df.dropna()

    # Renombrar columnas para Streamlit
    mapa_df = mapa_df.rename(columns={col_lat: "lat", col_lon: "lon"})

    if not mapa_df.empty:
        st.map(mapa_df)
    else:
        st.info("No hay coordenadas válidas para mostrar en el mapa.")
else:
    st.info("El dataset no contiene coordenadas geográficas.")

st.divider()


# --------------------------------------------------
# 1️⃣3️⃣ TABLA
# --------------------------------------------------
st.header("📋 Detalle de establecimientos")

st.dataframe(
    df_region[[col_comuna_nom, col_estab_nom]].reset_index(drop=True),
    use_container_width=True
)

# --------------------------------------------------
# 🔚 CONCLUSIÓN
# --------------------------------------------------
st.header("🧠 Conclusión")

st.markdown(
    f"""
    El análisis evidencia que la distribución de los establecimientos de salud
    en Chile presenta diferencias significativas entre regiones. En la región
    **{region_sel}**, se observa una concentración particular de ciertos tipos
    de establecimientos, lo que refleja la organización territorial del sistema
    de salud y posibles desigualdades en el acceso a servicios sanitarios.
    """
)
