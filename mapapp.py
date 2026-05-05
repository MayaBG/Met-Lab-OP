import streamlit as st
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import xarray as xr
import numpy as np
from datetime import datetime
import matplotlib.colors as mcolors

# הגדרות עמוד
st.set_page_config(page_title="מעבדה מטאורולוגית", layout="wide")

st.title("🌍 מחולל מפות סינופטיות")
st.markdown("### Source: NCEP/NCAR Reanalysis")

# סרגל צד להגדרות
st.sidebar.header("הגדרות הפקה")

year = st.sidebar.slider("שנה", 1979, 2026, 2024)
month = st.sidebar.slider("חודש", 1, 12, 1)
day = st.sidebar.slider("יום", 1, 31, 10)

# עדכון השעות לתיבת בחירה קבועה
hour = st.sidebar.selectbox("שעה (UTC)", [0, 6, 12, 18], index=2)

map_type = st.sidebar.radio("סוג מפה", ["surface", "500mb", "850mb"])

if st.sidebar.button("הפק מפה"):
    with st.spinner('מושך נתונים מהשרת...'):
        try:
            target_dt = datetime(year, month, day, hour)
            day_idx = target_dt.timetuple().tm_yday - 1
            
            urls = {
                'slp': f"https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis/surface/slp.{year}.nc",
                'hgt': f"https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis/pressure/hgt.{year}.nc",
                'air': f"https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis/pressure/air.{year}.nc",
                'uwnd': f"https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis/surface/uwnd.sig995.{year}.nc",
                'vwnd': f"https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis/surface/vwnd.sig995.{year}.nc"
            }

            fig = plt.figure(figsize=(12, 8))
            ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
            
            # הגדרות האזור לבקשתך: 20-40 צפון, 20-50 מזרח
            ax.set_extent([20, 50, 20, 40], crs=ccrs.PlateCarree())
            
            ax.add_feature(cfeature.COASTLINE.with_scale('50m'), linewidth=1.5)
            ax.add_feature(cfeature.BORDERS, linestyle=':')
            gl = ax.gridlines(draw_labels=True, linestyle='--', alpha=0.6)
            gl.top_labels = False
            gl.right_labels = False

            if map_type == 'surface':
                ds_slp = xr.open_dataset(urls['slp'])
                slp = ds_slp['slp'].isel(time=day_idx).sel(lat=slice(40, 20), lon=slice(20, 50)) / 100.0
                
                # שיידינג לבן לסימטריה
                white_cmap = mcolors.ListedColormap(['white'])
                cf = ax.contourf(slp.lon, slp.lat, slp, cmap=white_cmap, levels=[slp.min(), slp.max()])
                plt.colorbar(cf, orientation='horizontal', pad=0.08, aspect=40).ax.set_visible(False)
                
                cntr = ax.contour(slp.lon, slp.lat, slp, colors='black', levels=np.arange(980, 1040, 2))
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)
                
                ds_u = xr.open_dataset(urls['uwnd'])
                ds_v = xr.open_dataset(urls['vwnd'])
                u = ds_u['uwnd'].isel(time=day_idx).sel(lat=slice(40, 20), lon=slice(20, 50))
                v = ds_v['vwnd'].isel(time=day_idx).sel(lat=slice(40, 20), lon=slice(20, 50))
                ax.barbs(u.lon[::1], u.lat[::1], u.values[::1, ::1], v.values[::1, ::1], length=6, color='darkblue')
                st.write(f"### Surface MSLP & Winds | {target_dt}")

            elif map_type == '850mb':
                ds_air = xr.open_dataset(urls['air'])
                temp = ds_air['air'].isel(time=day_idx).sel(level=850, lat=slice(40, 20), lon=slice(20, 50)) - 273.15
                cf = ax.contourf(temp.lon, temp.lat, temp, cmap='coolwarm', levels=np.arange(-15, 35, 2), extend='both')
                plt.colorbar(cf, label='Temperature (°C)', orientation='horizontal', pad=0.08, aspect=40)
                cntr = ax.contour(temp.lon, temp.lat, temp, colors='black', levels=np.arange(-15, 35, 2), linewidths=0.8)
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)
                st.write(f"### 850hPa Temperature | {target_dt}")

            elif map_type == '500mb':
                ds_hgt = xr.open_dataset(urls['hgt'])
                hgt = ds_hgt['hgt'].isel(time=day_idx).sel(level=500, lat=slice(40, 20), lon=slice(20, 50))
                cf = ax.contourf(hgt.lon, hgt.lat, hgt, cmap='viridis', levels=np.arange(5100, 6000, 60), extend='both')
                plt.colorbar(cf, label='Geopotential Height (m)', orientation='horizontal', pad=0.08, aspect=40)
                cntr = ax.contour(hgt.lon, hgt.lat, hgt, colors='white', linewidths=1.2, levels=np.arange(5100, 6000, 60))
                ax.clabel(cntr, inline=True, fmt='%i', fontsize=10)
                st.write(f"### 500hPa Geopotential Height | {target_dt}")

            st.pyplot(fig)
            
        except Exception as e:
            st.error(f"שגיאה במשיכת נתונים: וודאו שהתאריך תקין וקיים במאגר. (Error: {e})")