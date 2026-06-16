import streamlit as st
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import xarray as xr
import numpy as np
from datetime import datetime
import matplotlib.colors as mcolors
import cdsapi
import os
from scipy.ndimage import gaussian_filter

# הגדרות עמוד של Streamlit
st.set_page_config(page_title="מעבדה מטאורולוגית", layout="wide")

# קוד CSS עדין וממוקד: מחיל RTL רק על טקסטים וכותרות כדי למנוע את שבירת הסליידרים והגרפיקה
st.markdown(
    """
    <style>
    /* הגדרת כיווניות ויישור לימין עבור טקסטים וכותרות בלבד */
    h1, h2, h3, h4, h5, h6, p, span, label, .stMarkdown, [data-testid="stWidgetLabel"] p {
        direction: RTL !important;
        text-align: right !important;
    }
    /* השארת רכיבי הסליידרים והכפתורים עצמם במבנה הסטנדרטי שלהם כדי שלא יישברו */
    div[data-testid="stSlider"], div[data-testid="stRadio"] {
        direction: LTR;
    }
    /* תיקון ספציפי לתוויות של כפתורי הרדיו שיוצגו נכון לצד הכפתור */
    div[data-testid="stRadio"] label {
        direction: RTL !important;
        text-align: right !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🌍 מחולל מפות סינופטיות - מעבדה")
st.markdown("### מערכת הפקת מפות מבוססת נתוני ריאנליזה גלובלית ERA5 (ECMWF הרשמי)")

# סרגל צד להגדרות המשתמש
st.sidebar.header("הגדרות הפקה")

year = st.sidebar.slider("שנה", 1979, 2026, 2026)
month = st.sidebar.slider("חודש", 1, 12, 4)
day = st.sidebar.slider("יום", 1, 31, 27)
hour = st.sidebar.selectbox("שעה (UTC)", [0, 6, 12, 18], index=2)

map_type = st.sidebar.radio("סוג מפה", ["surface", "500mb", "850mb"])

if st.sidebar.button("הפק מפה"):
    if "CDS_KEY" not in st.secrets:
        st.error("🔑 מפתח ה-API (CDS_KEY) אינו מוגדר בהגדרות האפליקציה (Secrets). אנא הזיני את המפתח כדי לאפשר הפקת מפות.")
    else:
        with st.spinner('מתחבר לשרת האירופי ומושך נתוני ERA5...'):
            try:
                target_dt = datetime(year, month, day, hour)
                
                # משיכת המפתח המאובטח מהכספת של סטריםלייט
                cds_key = st.secrets["CDS_KEY"]
                c = cdsapi.Client(url="https://cds.climate.copernicus.eu/api", key=cds_key)
                
                temp_filename = "era5_temp.nc"
                
                if map_type == 'surface':
                    c.retrieve(
                        'reanalysis-era5-single-levels',
                        {
                            'product_type': 'reanalysis',
                            'format': 'netcdf',
                            'variable': ['mean_sea_level_pressure', '10m_u_component_of_wind', '10m_v_component_of_wind'],
                            'year': str(year),
                            'month': f"{month:02d}",
                            'day': f"{day:02d}",
                            'time': f"{hour:02d}:00",
                        },
                        temp_filename)
                    
                    # טעינה וסידור קווי הרוחב בסדר עולה
                    ds = xr.open_dataset(temp_filename).sortby('latitude')
                    slp = ds['msl'].sel(latitude=slice(20, 40), longitude=slice(20, 50)).squeeze() / 100.0
                    u = ds['u10'].sel(latitude=slice(20, 40), longitude=slice(20, 50)).squeeze()
                    v = ds['v10'].sel(latitude=slice(20, 40), longitude=slice(20, 50)).squeeze()
                    
                    # החלקת השדה הסינופטי של הלחץ בקרקע לזרימה נקייה
                    slp_smoothed = gaussian_filter(slp.values, sigma=1.2)
                    
                else:
                    var_name = 'temperature' if map_type == '850mb' else 'geopotential'
                    lev_val = '850' if map_type == '850mb' else '500'
                    
                    c.retrieve(
                        'reanalysis-era5-pressure-levels',
                        {
                            'product_type': 'reanalysis',
                            'format': 'netcdf',
                            'variable': var_name,
                            'pressure_level': lev_val,
                            'year': str(year),
                            'month': f"{month:02d}",
                            'day': f"{day:02d}",
                            'time': f"{hour:02d}:00",
                        },
                        temp_filename)
                    
                    # טעינה וסידור קווי הרוחב בסדר עולה למפות הרום
                    ds = xr.open_dataset(temp_filename).sortby('latitude')

                # בניית המפה הגרפית - מיושר כחלק מה-try הכללי
                fig = plt.figure(figsize=(14, 10))
                ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
                ax.set_extent([20, 50, 20, 40], crs=ccrs.PlateCarree())

                map_info = {
                    'surface': "Surface MSLP (hPa) & Wind Barbs",
                    '500mb': "500hPa Geopotential Height (m)",
                    '850mb': "850hPa Temperature (°C)"
                }
                title_text = f"{map_info[map_type]} | Valid for: {target_dt.strftime('%Y-%m-%d %H:00')} UTC | Source: ECMWF ERA5 Reanalysis"

                # --- שלב הציור המטאורולוגי (מתחת לקווי המפה) ---
                if map_type == 'surface':
                    white_cmap = mcolors.ListedColormap(['white'])
                    cf = ax.contourf(slp.longitude, slp.latitude, slp, cmap=white_cmap, levels=[slp.min(), slp.max()], zorder=1)
                    
                    cntr = ax.contour(slp.longitude, slp.latitude, slp_smoothed, colors='black', levels=np.arange(980, 1040, 2), linewidths=1.8, zorder=2)
                    ax.clabel(cntr, inline=True, fmt='%i', fontsize=11)
                    
                    ax.barbs(u.longitude[::5], u.latitude[::5], u.values[::5, ::5], v.values[::5, ::5], 
                             length=5.5, color='#1b3a4b', linewidth=0.9, zorder=3)

                elif map_type == '850mb':
                    temp = ds['t'].sel(latitude=slice(20, 40), longitude=slice(20, 50)).squeeze() - 273.15
                    temp_smoothed = gaussian_filter(temp.values, sigma=1.5)
                    
                    cf = ax.contourf(temp.longitude, temp.latitude, temp, cmap='coolwarm', levels=np.arange(-15, 35, 2), extend='both', zorder=1)
                    plt.colorbar(cf, label='Temperature (°C)', orientation='horizontal', pad=0.08, aspect=40)
                    
                    cntr = ax.contour(temp.longitude, temp.latitude, temp_smoothed, colors='black', levels=np.arange(-15, 35, 2), linewidths=1.2, zorder=2)
                    ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)

                elif map_type == '500mb':
                    hgt = ds['z'].sel(latitude=slice(20, 40), longitude=slice(20, 50)).squeeze() / 9.80665
                    hgt_smoothed = gaussian_filter(hgt.values, sigma=1.2)
                    
                    cf = ax.contourf(hgt.longitude, hgt.latitude, hgt, cmap='viridis', levels=np.arange(5100, 6000, 60), extend='both', zorder=1)
                    plt.colorbar(cf, label='Geopotential Height (m)', orientation='horizontal', pad=0.08, aspect=40)
                    
                    cntr = ax.contour(hgt.longitude, hgt.latitude, hgt_smoothed, colors='white', linewidths=1.6, levels=np.arange(5100, 6000, 60), zorder=2)
                    ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)

                # --- שלב הציור הגאוגרפי (מוקפץ לשכבה העליונה zorder=4) ---
                ax.add_feature(cfeature.COASTLINE.with_scale('50m'), linewidth=1.2, edgecolor='black', zorder=4)
                ax.add_feature(cfeature.BORDERS, linestyle=':', linewidth=1.0, edgecolor='#2c3e50', zorder=4)
                
                gl = ax.gridlines(draw_labels=True, linestyle='--', alpha=0.5, color='#bdc3c7', zorder=3)
                gl.top_labels = False
                gl.right_labels = False

                # הדפסת כותרת קריאה ויציבה מעל הגרף ב-Streamlit
                st.markdown(f"### {title_text}")
                fig.tight_layout()
                st.pyplot(fig)
                
                ds.close()
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
                
            except Exception as e:
                st.error(f"שגיאה במשיכת הנתונים הרשמיים משרת קופרניקוס האירופי. (Error: {e})")
