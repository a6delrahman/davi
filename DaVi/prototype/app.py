import streamlit as st
import pandas as pd
import plotly.express as px
import altair as alt

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
    st.error("Fehler: Die Datei 'samsung_global_sales_dataset.csv' wurde nicht gefunden.")
    st.stop()

# --- Header ---
st.title("📦 Global Sales & Inventory Forecasting")
st.markdown("""
**Vom reaktiven Reporting zur proaktiven Bestandssteuerung.** Dieses Dashboard dient Supply Chain Managern zur strategischen Entscheidungsfindung.
""")

# --- Phase 2: Optimierte Sidebar (Kaskadierende Filter) ---
st.sidebar.header("Filter & Steuerung")

# 1. Kategorie-Filter
all_categories = df['category'].unique().tolist()
selected_categories = st.sidebar.multiselect("Produktkategorie:", all_categories, default=all_categories)

# 2. Länder-Filter
all_countries = sorted(df['country'].unique().tolist())
selected_countries = st.sidebar.multiselect("Land (Hotspots):", all_countries, default=all_countries)

# 3. Kaskadierender Städte-Filter (zeigt nur Städte der gewählten Länder)
available_cities = sorted(df[df['country'].isin(selected_countries)]['city'].unique().tolist())
selected_cities = st.sidebar.multiselect("Stadt (Logistik-Hubs):", available_cities, default=available_cities)

# 4. Datums-Filter
min_date = df['sale_date'].min().date()
max_date = df['sale_date'].max().date()
start_date, end_date = st.sidebar.date_input("Zeitraum wählen:", value=[min_date, max_date], min_value=min_date, max_value=max_date)

# DataFrame filtern
mask = (
    df['category'].isin(selected_categories) & 
    df['country'].isin(selected_countries) &
    df['city'].isin(selected_cities) &
    (df['sale_date'].dt.date >= start_date) & 
    (df['sale_date'].dt.date <= end_date)
)
filtered_df = df[mask]

if filtered_df.empty:
    st.warning("Keine Daten für die gewählten Filter verfügbar.")
    st.stop()

# --- Phase 3: High-Level KPIs ---
st.subheader("📊 Executive Summary")

total_revenue = filtered_df['revenue_usd'].sum()
total_units = filtered_df['units_sold'].sum()
avg_price_per_unit = total_revenue / total_units if total_units > 0 else 0
top_country = filtered_df.groupby('country')['revenue_usd'].sum().idxmax()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Gesamtumsatz", f"${total_revenue:,.0f}")
col2.metric("Verkaufte Einheiten", f"{total_units:,}")
col3.metric("Ø Preis pro Einheit", f"${avg_price_per_unit:,.2f}")
col4.metric("Stärkster Markt", top_country)
st.divider()

# --- Phase 4: Geografie (Plotly 3D) & Produkttiefe (Altair) ---
col_map, col_bar = st.columns(2)

with col_map:
    st.subheader("🌍 Geografische Verteilung")
    st.caption("Interaktiver 3D-Globus zur Identifikation von Logistik-Zentren.")
    country_sales = filtered_df.groupby('country')['revenue_usd'].sum().reset_index()
    fig_map = px.choropleth(country_sales, locations='country', locationmode='country names', color='revenue_usd', color_continuous_scale='Plasma')
    fig_map.update_geos(projection_type="orthographic", showcoastlines=True, showland=True, landcolor="#2A2A2A", showocean=True, oceancolor="#0E1117")
    fig_map.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig_map, use_container_width=True)

with col_bar:
    st.subheader("📦 Bestseller Modelle (Altair)")
    st.caption("Umsatzstärkste spezifische Produkte (Grundlage für Produktionspriorisierung).")
    
    # Altair Horizontal Bar Chart (Besser lesbar als ein Treemap)
    bar_chart = alt.Chart(filtered_df).mark_bar(cornerRadiusEnd=4).encode(
        x=alt.X('sum(revenue_usd):Q', title='Gesamtumsatz (USD)'),
        y=alt.Y('product_name:N', sort='-x', title=''), # Sortiert absteigend
        color=alt.Color('category:N', scale=alt.Scale(scheme='tealblues'), legend=alt.Legend(title="Kategorie", orient='bottom')),
        tooltip=[alt.Tooltip('product_name', title='Produkt'), alt.Tooltip('sum(revenue_usd):Q', title='Umsatz', format='$,.0f')]
    ).properties(height=350)
    st.altair_chart(bar_chart, use_container_width=True)

st.divider()

# --- Phase 5: Zeitreihe & Heatmap (Altair) ---
st.subheader("📈 Zeitreihenanalyse & Forecasting (Altair)")
st.caption("Historische Verkaufsdaten kombiniert mit einem 3-Monats-Trend zur proaktiven Bestandserkennung.")

time_df = filtered_df.copy()
time_df['YearMonth'] = time_df['sale_date'].dt.to_period('M')
monthly_sales = time_df.groupby('YearMonth')['revenue_usd'].sum().reset_index()
monthly_sales['YearMonth'] = monthly_sales['YearMonth'].dt.to_timestamp()
monthly_sales['MA_Trend'] = monthly_sales['revenue_usd'].rolling(window=3).mean()

# Altair Line Chart mit 2 Ebenen (Historisch + Trend)
base_line = alt.Chart(monthly_sales).encode(x=alt.X('YearMonth:T', title='Datum'))
line_revenue = base_line.mark_line(color='#1f77b4', strokeWidth=3).encode(
    y=alt.Y('revenue_usd:Q', title='Umsatz (USD)'),
    tooltip=[alt.Tooltip('YearMonth:T', title='Monat', format='%Y-%m'), alt.Tooltip('revenue_usd:Q', title='Umsatz', format='$,.0f')]
)
line_trend = base_line.mark_line(color='#ff7f0e', strokeDash=[5, 5], strokeWidth=3).encode(
    y=alt.Y('MA_Trend:Q'),
    tooltip=[alt.Tooltip('MA_Trend:Q', title='3-Monats-Trend', format='$,.0f')]
)
combined_line_chart = (line_revenue + line_trend).properties(height=350)
st.altair_chart(combined_line_chart, use_container_width=True)

st.subheader("🗓️ Saisonalität & Bestellzyklen (Altair Heatmap)")
heatmap_df = filtered_df.copy()
heatmap_df['Monat'] = heatmap_df['sale_date'].dt.month
heatmap_data = heatmap_df.groupby(['category', 'Monat'])['units_sold'].sum().reset_index()

# Altair Heatmap
heatmap = alt.Chart(heatmap_data).mark_rect().encode(
    x=alt.X('Monat:O', title='Monat (1-12)', axis=alt.Axis(labelAngle=0)),
    y=alt.Y('category:N', title='Kategorie'),
    color=alt.Color('units_sold:Q', scale=alt.Scale(scheme='oranges'), title='Verkaufte Einheiten'),
    tooltip=['Monat', 'category', 'units_sold']
).properties(height=250)
st.altair_chart(heatmap, use_container_width=True)

st.divider()

# --- Phase 6: Actionable Data & Fazit ---
col_table, col_fazit = st.columns([1.5, 1])

with col_table:
    st.subheader("🚨 Top 10 Logistik-Hotspots")
    st.caption("Diese Länder benötigen höchste Priorität bei der Lagerauffüllung.")
    top_countries = filtered_df.groupby('country')[['units_sold', 'revenue_usd']].sum().reset_index()
    top_countries = top_countries.sort_values(by='units_sold', ascending=False).head(10)
    top_countries.index = range(1, 11) 
    st.dataframe(top_countries.style.background_gradient(subset=['units_sold'], cmap='Blues').format({'revenue_usd': '${:,.0f}'}), use_container_width=True)

with col_fazit:
    st.subheader("💡 Handlungsempfehlung")
    st.info("""
    **Vom Report zur Aktion:**
    1. **Fokus:** Identifizieren Sie im Balkendiagramm die Bestseller und allozieren Sie Budgets entsprechend.
    2. **Timing:** Nutzen Sie die Heatmap und den Trend-Indikator, um Bestellungen auszulösen, *bevor* die Nachfragespitze eintritt.
    3. **Routing:** Routen Sie Container-Schiffe priorisiert in die Top 10 Hotspots, um Transportkosten zu sparen.
    """)


