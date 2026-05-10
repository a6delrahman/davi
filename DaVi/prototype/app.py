import streamlit as st
import pandas as pd
import plotly.express as px

# --- Konfiguration der Seite ---
st.set_page_config(
    page_title="Global Sales & Inventory Forecast",
    page_icon="📦",
    layout="wide"
)

# --- Phase 1: Data Loading ---
@st.cache_data
def load_data():
    df = pd.read_csv('DaVi/prototype/samsung_global_sales_dataset.csv')
    df['sale_date'] = pd.to_datetime(df['sale_date'])
    return df

try:
    df = load_data()
except FileNotFoundError:
    st.error("Fehler: Die Datei 'samsung_global_sales_dataset.csv' wurde nicht gefunden. Bitte stellen Sie sicher, dass sie im selben Ordner wie app.py liegt.")
    st.stop()

# --- Header ---
st.title("📦 Global Sales & Inventory Forecasting")
st.markdown("""
**Vom reaktiven Reporting zur proaktiven Bestandssteuerung.** Dieses Dashboard dient Supply Chain Managern zur strategischen Entscheidungsfindung. Es identifiziert regionale Hotspots, saisonale Spitzen und Produkttrends, um die globale Lieferkette proaktiv zu optimieren.
""")

# --- Phase 2: Sidebar & Filter ---
st.sidebar.header("Filter & Steuerung")

# Kategorie-Filter
all_categories = df['category'].unique().tolist()
selected_categories = st.sidebar.multiselect(
    "Produktkategorie wählen:",
    options=all_categories,
    default=all_categories
)

# Datums-Filter
min_date = df['sale_date'].min().date()
max_date = df['sale_date'].max().date()

start_date, end_date = st.sidebar.date_input(
    "Zeitraum wählen:",
    value=[min_date, max_date],
    min_value=min_date,
    max_value=max_date
)

# DataFrame basierend auf Filtern aktualisieren
mask = (
    df['category'].isin(selected_categories) & 
    (df['sale_date'].dt.date >= start_date) & 
    (df['sale_date'].dt.date <= end_date)
)
filtered_df = df[mask]

# Abbruch, falls Filter zu streng sind
if filtered_df.empty:
    st.warning("Keine Daten für die gewählten Filter verfügbar. Bitte passen Sie die Auswahl in der Sidebar an.")
    st.stop()

# --- Phase 3: High-Level KPIs (Erweitert) ---
st.subheader("📊 Executive Summary")

total_revenue = filtered_df['revenue_usd'].sum()
total_units = filtered_df['units_sold'].sum()
avg_price_per_unit = total_revenue / total_units if total_units > 0 else 0
top_country = filtered_df.groupby('country')['revenue_usd'].sum().idxmax()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Gesamtumsatz (Revenue)", f"${total_revenue:,.0f}")
with col2:
    st.metric("Verkaufte Einheiten (Units)", f"{total_units:,}")
with col3:
    st.metric("Ø Preis pro Einheit", f"${avg_price_per_unit:,.2f}")
with col4:
    st.metric("Stärkster Markt", top_country)

st.divider()

# --- Phase 4 & Optimierung: Geografie & Produkttiefe ---
col_map, col_tree = st.columns(2)

with col_map:
    st.subheader("🌍 Geografische Umsatzverteilung")
    st.caption("Wo auf der Welt wird der meiste Umsatz generiert? (Grundlage für regionale Lagerallokation)")
    country_sales = filtered_df.groupby('country')['revenue_usd'].sum().reset_index()
    fig_map = px.choropleth(
        country_sales,
        locations='country',
        locationmode='country names',
        color='revenue_usd',
        color_continuous_scale='Blues',
        labels={'revenue_usd': 'Umsatz (USD)', 'country': 'Land'}
    )
    fig_map.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig_map, use_container_width=True)

with col_tree:
    st.subheader("📦 Produkt-Portfolio (Treemap)")
    st.caption("Welche spezifischen Modelle treiben den Umsatz? (Grundlage für Produktionspriorisierung)")
    fig_treemap = px.treemap(
        filtered_df, 
        path=[px.Constant("Alle Kategorien"), 'category', 'product_name'], 
        values='revenue_usd',
        color='revenue_usd',
        color_continuous_scale='Teal',
        labels={'revenue_usd': 'Umsatz (USD)'}
    )
    fig_treemap.update_traces(root_color="lightgrey")
    fig_treemap.update_layout(margin=dict(t=20, l=20, r=20, b=20))
    st.plotly_chart(fig_treemap, use_container_width=True)

st.divider()

# --- Phase 5: Zeitreihe & Heatmap (Der strategische Vorteil) ---
st.subheader("📈 Zeitreihenanalyse & Forecasting")
st.caption("Historische Verkaufsdaten kombiniert mit einem 3-Monats-Trend (Gleitender Durchschnitt) zur proaktiven Bestandserkennung.")

# Daten für Zeitreihe vorbereiten
time_df = filtered_df.copy()
time_df['YearMonth'] = time_df['sale_date'].dt.to_period('M')
monthly_sales = time_df.groupby('YearMonth')['revenue_usd'].sum().reset_index()
monthly_sales['YearMonth'] = monthly_sales['YearMonth'].dt.to_timestamp()

# 3-Monats Moving Average berechnen
monthly_sales['3-Month Trend (MA)'] = monthly_sales['revenue_usd'].rolling(window=3).mean()

# Line Chart erstellen
fig_line = px.line(
    monthly_sales, 
    x='YearMonth', 
    y=['revenue_usd', '3-Month Trend (MA)'],
    labels={'value': 'Umsatz (USD)', 'YearMonth': 'Zeitverlauf', 'variable': 'Metrik'},
    color_discrete_map={"revenue_usd": "#1f77b4", "3-Month Trend (MA)": "#ff7f0e"}
)
fig_line.update_layout(legend_title_text='')
st.plotly_chart(fig_line, use_container_width=True)

# Saisonalitäts-Heatmap (Darunter)
st.subheader("🗓️ Saisonalität & Bestellzyklen (Heatmap)")
st.caption("Nutzen Sie diese Ansicht, um wiederkehrende Nachfragespitzen in bestimmten Monaten frühzeitig zu erkennen.")

heatmap_df = filtered_df.copy()
heatmap_df['Monat'] = heatmap_df['sale_date'].dt.month
heatmap_data = heatmap_df.groupby(['category', 'Monat'])['units_sold'].sum().reset_index()

fig_heatmap = px.density_heatmap(
    heatmap_data, 
    x='Monat', 
    y='category', 
    z='units_sold',
    color_continuous_scale='Oranges',
    labels={'Monat': 'Monat (1-12)', 'category': 'Kategorie', 'units_sold': 'Verkaufte Einheiten'}
)
fig_heatmap.update_layout(xaxis=dict(dtick=1))
st.plotly_chart(fig_heatmap, use_container_width=True)

st.divider()

# --- Phase 6: Actionable Data & Fazit ---
col_table, col_fazit = st.columns([1.5, 1])

with col_table:
    st.subheader("🚨 Top 10 Logistik-Hotspots")
    st.caption("Diese Städte haben aktuell das höchste Absatzvolumen. Lagerbestände sollten hier priorisiert werden.")
    
    top_cities = filtered_df.groupby(['country', 'city'])[['units_sold', 'revenue_usd']].sum().reset_index()
    top_cities = top_cities.sort_values(by='units_sold', ascending=False).head(10)
    top_cities.index = range(1, 11) # Index von 1 bis 10 statt Original-Index
    
    st.dataframe(
        top_cities.style.background_gradient(subset=['units_sold'], cmap='Blues')
                        .format({'revenue_usd': '${:,.0f}'}),
        use_container_width=True
    )

with col_fazit:
    st.subheader("💡 Strategische Handlungsempfehlung")
    st.info("""
    **Vom Report zur Aktion:**
    1. **Fokus:** Identifizieren Sie im Treemap die Bestseller und allozieren Sie Budgets entsprechend.
    2. **Timing:** Nutzen Sie die Heatmap und den Trend-Indikator, um Bestellungen auszulösen, *bevor* die Nachfragespitze (Out-of-Stock) eintritt.
    3. **Routing:** Routen Sie Container-Schiffe priorisiert in die Top 10 Logistik-Hotspots, um Transportkosten für lokale Umverteilungen zu sparen.
    """)
