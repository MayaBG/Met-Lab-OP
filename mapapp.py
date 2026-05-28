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
import urllib3
import traceback
import requests

# ביטול אזהרות SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# הגדרות עמוד של Streamlit
st.set_page_config(page_title="מעבדה מטאורולוגית - אבחון שגיאות", layout="wide")

st.title("🌍 מחולל מפות סינופטיות - מצב אבחון (Debug Mode)")
st.markdown("### מערכת הפקת מפות מבוססת נתוני ריאנליזה גלובלית ERA5")

# סרגל צד להגדרות המשתמש
st.sidebar.header("הגדרות הפקה")

year = st.sidebar.slider("שנה", 1979, 2026, 2026)
month = st.sidebar.slider("חודש", 1, 12, 4)
day = st.sidebar.slider("יום", 1, 31, 27)
hour = st.sidebar.selectbox("שעה (UTC)", [0, 6, 12, 18], index=2)

map_type = st.sidebar.radio("סוג מפה", ["surface", "500mb", "850mb"])

if st.sidebar.button("הפק מפה (במצב אבחון)"):
    # קופסת מידע להצגת שלבי הריצה בזמן אמת
    debug_placeholder = st.empty()
    
    with st.spinner('מריץ בדיקות ואבחון מול שרתי קופרניקוס...'):
        try:
            target_dt = datetime(year, month, day, hour)
            
            # --- נקודת בדיקה 1: בדיקת שלמות מפתח ה-Secrets ---
            debug_placeholder.info("🔍 נקודת בדיקה 1: בודק זמינות מפתח בכספת ה-Secrets...")
            if "CDS_KEY" not in st.secrets:
                st.error("❌ שגיאה: המפתח 'CDS_KEY' לא נמצא בתוך ה-Secrets של Streamlit!")
                st.stop()
            cds_key = st.secrets["CDS_KEY"]
            st.success("✅ מפתח ה-Secrets נמצא בהצלחה.")

            # --- נקודת בדיקה 2: בדיקת גרסת הספרייה המותקנת ---
            debug_placeholder.info("🔍 נקודת בדיקה 2: בודק את גרסת ספריית cdsapi המותקנת...")
            try:
                version = cdsapi.__version__
                st.write(f"ℹ️ גרסת ספריית `cdsapi` המותקנת בשרת: `{version}`")
            except Exception as v_err:
                st.write(f"⚠️ לא ניתן לקרוא את גרסת הספרייה: {v_err}")

            # --- נקודת בדיקה 3: בדיקת תקשורת רשת ישירה (ללא הספרייה) ---
            debug_placeholder.info("🔍 נקודת בדיקה 3: בודק תקשורת רשת ישירה ומצב שרת ה-Beta...")
            test_url = "https://cds-beta.climate.copernicus.eu/api"
            try:
                res = requests.get(test_url, verify=False, timeout=10)
                st.write(f"ℹ️ תגובה ישירה מהשרת (Status Code): `{res.status_code}`")
                st.write(f"ℹ️ תוכן תגובת השרת: `{res.text[:150]}`")
            except Exception as net_err:
                st.write(f"⚠️ נכשלה תקשורת ישירה לשרת: {net_err}")

            # --- נקודת בדיקה 4: יצירת הקליינט וביצוע הפנייה ---
            debug_placeholder.info("🔍 נקודת בדיקה 4: מנסה לבצע את פניית ה-API הרשמית...")
            
            # הגדרת הקליינט עם הכתובת הרשמית של שרת ה-Beta
            c = cdsapi.Client(url="https://cds-beta.climate.copernicus.eu/api", key=cds_key, verify=False)
            
            temp_filename = "era5_temp.nc"
            
            if map_type == 'surface':
                dataset_name = 'reanalysis-era5-single-levels'
                params = {
                    'product_type': 'reanalysis',
                    'format': 'netcdf',
                    'variable': ['mean_sea_level_pressure', '10m_u_component_of_wind', '10m_v_component_of_wind'],
                    'year': str(year),
                    'month': f"{month:02d}",
                    'day': f"{day:02d}",
                    'time': f"{hour:02d}:00",
                }
            else:
                dataset_name = 'reanalysis-era5-pressure-levels'
                var_name = 'temperature' if map_type == '850mb' else 'geopotential'
                lev_val = '850' if map_type == '850mb' else '500'
                params = {
                    'product_type': 'reanalysis',
                    'format': 'netcdf',
                    'variable': var_name,
                    'pressure_level': lev_val,
                    'year': str(year),
                    'month': f"{month:02d}",
                    'day': f"{day:02d}",
                    'time': f"{hour:02d}:00",
                }

            st.write(f"📡 שולח בקשה למאגר: `{dataset_name}` עם הפרמטרים שנבחרו...")
            
            # ביצוע ה-Retrieve
            c.retrieve(dataset_name, params, temp_filename)
            
            # --- נקודת בדיקה 5: בדיקת קובץ הפלט ---
            debug_placeholder.info("🔍 נקודת בדיקה 5: הבקשה הצליחה, בודק את קובץ הנתונים שירד...")
            if not os.path.exists(temp_filename):
                st.error("❌ שגיאה: השרת דיווח על הצלחה אך הקובץ הזמני לא נוצר פיזית על הדיסק!")
                st.stop()
                
            ds = xr.open_dataset(temp_filename)
            st.success("✅ הקובץ נפתח ונקרא בהצלחה על ידי xarray. מתחיל לשרטט את המפה...")

            # --- בניית המפה הגרפית ---
            fig = plt.figure(figsize=(14, 10))
            ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
            ax.set_extent([20, 50, 20, 40], crs=ccrs.PlateCarree())
            
            ax.add_feature(cfeature.COASTLINE.with_scale('50m'), linewidth=1.5)
            ax.add_feature(cfeature.BORDERS, linestyle=':')
            gl = ax.gridlines(draw_labels=True, linestyle='--', alpha=0.6)
            gl.top_labels = False
            gl.right_labels = False

            if map_type == 'surface':
                slp = ds['msl'].sel(latitude=slice(40, 20), longitude=slice(20, 50)) / 100.0
                u = ds['u10'].sel(latitude=slice(40, 20), longitude=slice(20, 50))
                v = ds['v10'].sel(latitude=slice(40, 20), longitude=slice(20, 50))
                
                white_cmap = mcolors.ListedColormap(['white'])
                cf = ax.contourf(slp.longitude, slp.latitude, slp, cmap=white_cmap, levels=[slp.min(), slp.max()])
                cntr = ax.contour(slp.longitude, slp.latitude, slp, colors='black', levels=np.arange(980, 1040, 2))
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)
                ax.barbs(u.longitude[::2], u.latitude[::2], u.values[::2, ::2], v.values[::2, ::2], length=6, color='darkblue')

            elif map_type == '850mb':
                temp = ds['t'].sel(latitude=slice(40, 20), longitude=slice(20, 50)) - 273.15
                cf = ax.contourf(temp.longitude, temp.latitude, temp, cmap='coolwarm', levels=np.arange(-15, 35, 2), extend='both')
                plt.colorbar(cf, label='Temperature (°C)', orientation='horizontal', pad=0.08, aspect=40)
                cntr = ax.contour(temp.longitude, temp.latitude, temp, colors='black', levels=np.arange(-15, 35, 2), linewidths=0.8)
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)

            elif map_type == '500mb':
                hgt = ds['z'].sel(latitude=slice(40, 20), longitude=slice(20, 50)) / 9.80665
                cf = ax.contourf(hgt.longitude, hgt.latitude, hgt, cmap='viridis', levels=np.arange(5100, 6000, 60), extend='both')
                plt.colorbar(cf, label='Geopotential Height (m)', orientation='horizontal', pad=0.08, aspect=40)
                cntr = ax.contour(hgt.longitude, hgt.latitude, hgt, colors='white', linewidths=1.2, levels=np.arange(5100, 6000, 60))
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)

            title_text = f"{map_type.upper()}\nValid for: {target_dt.strftime('%Y-%m-%d %H:00')} UTC\nSource: ECMWF ERA5 (Debug Output)"
            plt.title(title_text, fontsize=14, pad=20)
            st.pyplot(fig)
            
            # ניקוי קבצים
            ds.close()
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
                
            debug_placeholder.empty()

        except Exception as main_e:
            debug_placeholder.empty()
            st.error("🛑 קרסה שגיאה במהלך הריצה! להלן נתוני האבחון המלאים:")
            
            # הדפסת סוג השגיאה וההודעה המקורית שלה
            st.warning(f"**סוג השגיאה (Error Type):** `{type(main_e).__name__}`")
            st.warning(f"**הודעת השגיאה (Error Message):** `{str(main_e)}`")
            
            # הדפסת ה-Traceback המלא (איפה בדיוק בקוד זה קרה)
            st.markdown("**נתיב קריסת הקוד (Full Traceback):**")
            tb_lines = traceback.format_exc()
            st.code(tb_lines, language="python")
