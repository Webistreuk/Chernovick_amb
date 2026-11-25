"""
Предзагрузка тайлов OSM для Сочи.
Запуск: python download_tiles.py
Качает в static/tiles/{z}/{x}/{y}.png
"""
import math
import os
import time
import requests

BBOX = (39.30, 43.40, 40.10, 43.80)  # lng_min, lat_min, lng_max, lat_max
ZOOMS = range(11, 17)
OUT_DIR = os.path.join(os.path.dirname(__file__), "static", "tiles")
OSM_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
UA = "AmbulanceLocalMap/1.0 (tile preload)"


def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile


def download_tile(z, x, y):
    path_dir = os.path.join(OUT_DIR, str(z), str(x))
    file_path = os.path.join(path_dir, f"{y}.png")
    if os.path.isfile(file_path):
        return "skip"
    try:
        r = requests.get(OSM_URL.format(z=z, x=x, y=y),
                         headers={"User-Agent": UA}, timeout=10)
        if r.status_code == 200 and r.content:
            os.makedirs(path_dir, exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(r.content)
            return "ok"
    except requests.RequestException:
        pass
    return "fail"


def main():
    lng_min, lat_min, lng_max, lat_max = BBOX
    total = 0
    for z in ZOOMS:
        x1, y1 = deg2num(lat_max, lng_min, z)
        x2, y2 = deg2num(lat_min, lng_max, z)
        cnt = 0
        for x in range(min(x1, x2), max(x1, x2) + 1):
            for y in range(min(y1, y2), max(y1, y2) + 1):
                res = download_tile(z, x, y)
                if res in ("ok", "fail"):
                    cnt += 1
                total += 1
                if cnt % 50 == 0 and cnt > 0:
                    print(f"z={z}: скачано {cnt} тайлов…")
                time.sleep(0.5)  # вежливо к OSM: ~2 тайла/сек
        print(f"z={z}: обработано {cnt}")
    print(f"Готово. Всего обработано {total}")


if __name__ == "__main__":
    main()