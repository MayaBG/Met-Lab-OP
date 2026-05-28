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
st.markdown("### מערכת הפקת מפות מבוססת נתוני ריאנליזה גלובלית ERA5 (ECMWF)")

# סרגל צד להגדרות המשתמש
st.sidebar.header("הגדרות הפקה")

year = st.sidebar.slider("שנה", 1979, 2026, 2026)
month = st.sidebar.slider("חודש", 1, 12, 4)
day = st.sidebar.slider("יום", 1, 31, 28)

# בחירת שעה מתוך רשימה קבועה
hour = st.sidebar.selectbox("שעה (UTC)", [0, 6, 12, 18], index=2)

map_type = st.sidebar.radio("סוג מפה", ["surface", "500mb", "850mb"])

if st.sidebar.button("הפק מפה"):
    with st.spinner('מושך נתוני ריאנליזה ERA5 מהשרת האירופי...'):
        try:
            target_dt = datetime(year, month, day, hour)
            
            # קישור קבוע ויציב לשרת הריאנליזה ERA5 הרציף
            # השרת משתמש בפורמט חודשי קבוע המונע נפילות וחורים בלוח השנה
            date_str = target_dt.strftime("%Y%m")
            
            # שרת הנתונים הציבורי של ERA5 Reanalysis
            base_url = f"https://thredds.rda.ucar.edu/thredds/dodsC/files/g/ds633.0/e5.oper.an.sfc/{date_str}/"
            base_url_pl = f"https://thredds.rda.ucar.edu/thredds/dodsC/files/g/ds633.0/e5.oper.an.pl/{date_str}/"
            
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
            title_text = f"{map_info[map_type]}\nValid for: {target_dt.strftime('%Y-%m-%d %H:00')} UTC\nSource: ECMWF ERA5 Reanalysis"

            if map_type == 'surface':
                # טעינת לחץ פני הים משרת ERA5
                url_slp = f"{base_url}e5.oper.an.sfc.128_151_msl.ll025sc.{date_str}0100_{date_str}3123.nc"
                ds = xr.open_dataset(url_slp)
                time_idx = np.abs(ds.time.values - np.datetime64(target_dt)).argmin()
                
                # ERA5 נותן לחץ בפסקל (Pa), מחלקים ב-100 לקבלת hPa
                slp = ds['MSL'].isel(time=time_idx).sel(latitude=slice(40, 20), longitude=slice(20, 50)) / 100.0
                
                white_cmap = mcolors.ListedColormap(['white'])
                cf = ax.contourf(slp.longitude, slp.latitude, slp, cmap=white_cmap, levels=[slp.min(), slp.max()])
                plt.colorbar(cf, orientation='horizontal', pad=0.08, aspect=40).ax.set_visible(False)
                
                cntr = ax.contour(slp.longitude, slp.latitude, slp, colors='black', levels=np.arange(980, 1040, 2))
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)
                
                # רוחות קרקע ב-ERA5 (רכיבי U ו-V בגובה 10 מטרים)
                url_u = f"{base_url}e5.oper.an.sfc.128_165_10u.ll025sc.{date_str}0100_{date_str}3123.nc"
                url_v = f"{base_url}e5.oper.an.sfc.128_166_10v.ll025sc.{date_str}0100_{date_str}3123.nc"
                ds_u = xr.open_dataset(url_u)
                ds_v = xr.open_dataset(url_v)
                u = ds_u['U10'].isel(time=time_idx).sel(latitude=slice(40, 20), longitude=slice(20, 50))
                v = ds_v['V10'].isel(time=time_idx).sel(latitude=slice(40, 20), longitude=slice(20, 50))
                ax.barbs(u.longitude[::6], u.latitude[::6], u.values[::6, ::6], v.values[::6, ::6], length=6, color='darkblue')

            elif map_type == '850mb':
                # טעינת טמפרטורה במפלסים משרת ERA5
                url_t = f"{base_url_pl}e5.oper.an.pl.128_130_t.ll025sc.{date_str}0100_{date_str}3123.nc"
                ds = xr.open_dataset(url_t)
                time_idx = np.abs(ds.time.values - np.datetime64(target_dt)).argmin()
                
                temp = ds['T'].isel(time=time_idx).sel(level=850, latitude=slice(40, 20), longitude=slice(20, 50)) - 273.15
                cf = ax.contourf(temp.longitude, temp.latitude, temp, cmap='coolwarm', levels=np.arange(-15, 35, 2), extend='both')
                plt.colorbar(cf, label='Temperature (°C)', orientation='horizontal', pad=0.08, aspect=40)
                cntr = ax.contour(temp.longitude, temp.latitude, temp, colors='black', levels=np.arange(-15, 35, 2), linewidths=0.8)
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)

            elif map_type == '500mb':
                # טעינת גובה גיאופוטנציאלי משרת ERA5
                url_z = f"{base_url_pl}e5.oper.an.pl.128_129_z.ll025sc.{date_str}0100_{date_str}3123.nc"
                ds = xr.open_dataset(url_z)
                time_idx = np.abs(ds.time.values - np.datetime64(target_dt)).argmin()
                
                # ERA5 נותן גיאופוטנציאל ($m^2/s^2$), מחלקים ב-9.80665 כדי לקבל מטרים גיאופוטנציאליים
                hgt = ds['Z'].isel(time=time_idx).sel(level=500, latitude=slice(40, 20), longitude=slice(20, 50)) / 9.80665
                cf = ax.contourf(hgt.longitude, hgt.latitude, hgt, cmap='viridis', levels=np.arange(5100, 6000, 60), extend='both')
                plt.colorbar(cf, label='Geopotential Height (m)', orientation='horizontal', pad=0.08, aspect=40)
                cntr = ax.contour(hgt.longitude, hgt.latitude, hgt, colors='white', linewidths=1.2, levels=np.arange(5100, 6000, 60))
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)

            plt.title(title_text, fontsize=14, pad=20)
            st.pyplot(fig)
            
        except Exception as e:
            st.error(f"לא ניתן למשוך נתונים לתאריך המבוקש. ודאו שהנתונים לחודש זה שוחררו רשמית על ידי ECMWF. (Error: {e})")
