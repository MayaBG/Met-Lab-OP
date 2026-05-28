import streamlit as st
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import xarray as xr
import numpy as np
from datetime import datetime
import matplotlib.colors as mcolors

# הגדרות עמוד של Streamlit
st.set_page_config(page_title="מעבדה מטאורולוגית", layout="wide")

st.title("🌍 מחולל מפות סינופטיות - מעבדה")
st.markdown("### מערכת הפקת מפות מבוססת שרת הריאנליזה הפתוח (Columbia University Mirror)")

# סרגל צד להגדרות המשתמש
st.sidebar.header("הגדרות הפקה")

year = st.sidebar.slider("שנה", 1979, 2026, 2026)
month = st.sidebar.slider("חודש", 1, 12, 4)
day = st.sidebar.slider("יום", 1, 31, 27)

# בחירת שעה מתוך רשימה קבועה
hour = st.sidebar.selectbox("שעה (UTC)", [0, 6, 12, 18], index=2)

map_type = st.sidebar.radio("סוג מפה", ["surface", "500mb", "850mb"])

if st.sidebar.button("הפק מפה"):
    with st.spinner('מושך נתונים משרת הריאנליזה הפתוח...'):
        try:
            target_dt = datetime(year, month, day, hour)
            
            # מעבר לשרת המראה הפתוח של אוניברסיטת קולומביה (IRI/LDEO)
            # שרת זה פתוח לחלוטין וממשיך לעדכן את הריאנליזה מעבר ל-17 במרץ
            base_url = "https://iridl.ldeo.columbia.edu/SOURCES/.NOAA/.NCEP-NCAR/.CDAS"
            
            # חישוב דינמי של הזמן לפרוטוקול קולומביה
            # השרת סופר ימים מאז 1 בינואר 1960
            base_date = datetime(1960, 1, 1)
            days_since = (target_dt - base_date).days + (hour / 24.0)

            # בניית מפה ועיבוד נתונים
            fig = plt.figure(figsize=(14, 10))
            ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
            ax.set_extent([20, 50, 20, 40], crs=ccrs.PlateCarree())
            
            ax.add_feature(cfeature.COASTLINE.with_scale('50m'), linewidth=1.5)
            ax.add_feature(cfeature.BORDERS, linestyle=':')
            gl = ax.gridlines(draw_labels=True, linestyle='--', alpha=0.6)
            gl.top_labels = False
            gl.right_labels = False

            map_info = {
                'surface': "Surface MSLP (hPa) & Wind Barbs",
                '500mb': "500hPa Geopotential Height (m)",
                '850mb': "850hPa Temperature (°C)"
            }
            title_text = f"{map_info[map_type]}\nValid for: {target_dt.strftime('%Y-%m-%d %H:00')} UTC\nSource: NCEP/NCAR Reanalysis (Columbia Univ. Mirror)"

            if map_type == 'surface':
                # טעינת לחץ פני הים משרת קולומביה
                url_slp = f"{base_url}/.DAILY/.MSLP/dods"
                ds = xr.open_dataset(url_slp)
                slp_data = ds['prmsl'].sel(time=days_since, method='nearest').sel(lat=slice(40, 20), lon=slice(20, 50))
                
                # המרה ל-hPa במידת הצורך (תלוי בפורמט השרת)
                if slp_data.max() > 5000:
                    slp_data = slp_data / 100.0
                
                white_cmap = mcolors.ListedColormap(['white'])
                cf = ax.contourf(slp_data.lon, slp_data.lat, slp_data, cmap=white_cmap, levels=[slp_data.min(), slp_data.max()])
                plt.colorbar(cf, orientation='horizontal', pad=0.08, aspect=40).ax.set_visible(False)
                
                cntr = ax.contour(slp_data.lon, slp_data.lat, slp_data, colors='black', levels=np.arange(980, 1040, 2))
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)
                
                # רוחות קרקע משרת קולומbiה
                url_u = f"{base_url}/.DAILY/.ugrd/dods"
                url_v = f"{base_url}/.DAILY/.vgrd/dods"
                ds_u = xr.open_dataset(url_u)
                ds_v = xr.open_dataset(url_v)
                u = ds_u['uwnd'].sel(time=days_since, method='nearest').sel(lat=slice(40, 20), lon=slice(20, 50))
                v = ds_v['vwnd'].sel(time=days_since, method='nearest').sel(lat=slice(40, 20), lon=slice(20, 50))
                ax.barbs(u.lon[::1], u.lat[::1], u.values[::1, ::1], v.values[::1, ::1], length=6, color='darkblue')

            elif map_type == '850mb':
                # טעינת טמפרטורה
                url_t = f"{base_url}/.DAILY/.temp/dods"
                ds = xr.open_dataset(url_t)
                temp_data = ds['air'].sel(time=days_since, level=850, method='nearest').sel(lat=slice(40, 20), lon=slice(20, 50))
                
                if temp_data.max() > 100:  # המרה מקלווין לצלזיוס
                    temp_data = temp_data - 273.15
                    
                cf = ax.contourf(temp_data.lon, temp_data.lat, temp_data, cmap='coolwarm', levels=np.arange(-15, 35, 2), extend='both')
                plt.colorbar(cf, label='Temperature (°C)', orientation='horizontal', pad=0.08, aspect=40)
                cntr = ax.contour(temp_data.lon, temp_data.lat, temp_data, colors='black', levels=np.arange(-15, 35, 2), linewidths=0.8)
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)

            elif map_type == '500mb':
                # טעינת גובה גיאופוטנציאלי
                url_z = f"{base_url}/.DAILY/.hgt/dods"
                ds = xr.open_dataset(url_z)
                hgt_data = ds['hgt'].sel(time=days_since, level=500, method='nearest').sel(lat=slice(40, 20), lon=slice(20, 50))
                
                cf = ax.contourf(hgt_data.lon, hgt_data.lat, hgt_data, cmap='viridis', levels=np.arange(5100, 6000, 60), extend='both')
                plt.colorbar(cf, label='Geopotential Height (m)', orientation='horizontal', pad=0.08, aspect=40)
                cntr = ax.contour(hgt_data.lon, hgt_data.lat, hgt_data, colors='white', linewidths=1.2, levels=np.arange(5100, 6000, 60))
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)

            plt.title(title_text, fontsize=14, pad=20)
            st.pyplot(fig)
            
        except Exception as e:
            st.error(f"שגיאה במשיכת הנתונים משרת המראה הציבורי. אנא ודאו שהתאריך תקין. (Error: {e})")
