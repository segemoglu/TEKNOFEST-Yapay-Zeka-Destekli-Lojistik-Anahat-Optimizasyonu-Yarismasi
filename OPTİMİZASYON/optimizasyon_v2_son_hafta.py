# Gerekli kütüphaneleri yüklüyoruz
import os  # Dosya ve dizin işlemleri için
import sys  # Konsol çıktı kodlamasını ayarlamak için
import pandas as pd  # Excel dosyalarını okuma, yazma ve veri manipülasyonu için
import numpy as np  # Matematiksel ve matris işlemleri için
from ortools.linear_solver import pywraplp  # Google OR-Tools doğrusal/tamsayılı programlama çözücüsü
import time  # Süre ölçümü için

# Konsolun Türkçe karakterleri doğru basabilmesi için UTF-8 kodlamasını ayarlıyoruz
sys.stdout.reconfigure(encoding='utf-8')

# Çalışma dizinini tanımlıyoruz (Dinamik yol yapısı)
calisma_dizini = os.path.dirname(os.path.abspath(__file__))

# Gerçek zamanlı log yazmak için bir log dosyası açıyoruz (optimizasyon_v2_son_hafta.log)
log_dosya_yolu = os.path.join(calisma_dizini, "optimizasyon_v2_son_hafta.log")
log_dosyasi = open(log_dosya_yolu, "w", encoding="utf-8")

# Hem konsola hem de log dosyasına anında yazıp tamponu (buffer) boşaltan özel print fonksiyonu
def log_yaz(mesaj):
    print(mesaj)
    log_dosyasi.write(mesaj + "\n")
    log_dosyasi.flush()
    sys.stdout.flush()

# Dosya yollarını tanımlıyoruz
koordinat_yolu = os.path.join(calisma_dizini, "Koordinatlar v2.xlsx")
maliyet_yolu = os.path.join(calisma_dizini, "Arac_Kapasite_Maliyet.xlsx")
kiralik_yolu = os.path.join(calisma_dizini, "Kiralik_Araclar.xlsx")
tahmin_talep_yolu = os.path.join(calisma_dizini, "Tahminlenen_Talep.xlsx")

# Gerekli dosyaların varlığını kontrol ediyoruz
gerekli_dosyalar = {
    "Koordinatlar v2.xlsx": koordinat_yolu,
    "Arac_Kapasite_Maliyet.xlsx": maliyet_yolu,
    "Kiralik_Araclar.xlsx": kiralik_yolu,
    "Tahminlenen_Talep.xlsx": tahmin_talep_yolu
}

eksik_dosyalar = [dosya_adi for dosya_adi, dosya_yolu in gerekli_dosyalar.items() if not os.path.exists(dosya_yolu)]

if eksik_dosyalar:
    mesaj = f"HATA: {', '.join(eksik_dosyalar)} isimli excel dosyaları bulunamadı! Lütfen aynı klasörün içine bu dosyaları koyun sonra yeniden çalıştırın."
    log_yaz(mesaj)
    sys.exit(1)

log_yaz("1. Adım: Veriler yükleniyor...")
# Excel dosyalarını okuyoruz
df_koordinat = pd.read_excel(koordinat_yolu)
df_maliyet = pd.read_excel(maliyet_yolu)
df_kiralik = pd.read_excel(kiralik_yolu)
df_tahmin_talep = pd.read_excel(tahmin_talep_yolu)

# Tarih kolonlarını datetime formatına dönüştürüyoruz
df_tahmin_talep["Tarih"] = pd.to_datetime(df_tahmin_talep["Tarih"])

# Tahminlenen_Talep.xlsx formatı güncellenmiş veya eski olabilir, bunu kontrol ederek normalize ediyoruz
df_tahmin_talep_norm = df_tahmin_talep.copy()
if "Çıkış TM" in df_tahmin_talep_norm.columns:
    df_tahmin_talep_norm = df_tahmin_talep_norm.rename(columns={
        "Çıkış TM": "Çıkış Transfer Merkezi",
        "Varış TM": "Varış Transfer Merkezi",
        "Tahmin Edilen Desi": "Toplam Desi"
    })
    df_tahmin_talep_norm["Çıkış Transfer Merkezi"] = df_tahmin_talep_norm["Çıkış Transfer Merkezi"].astype(str).str.replace(" TM", "", regex=False)
    df_tahmin_talep_norm["Varış Transfer Merkezi"] = df_tahmin_talep_norm["Varış Transfer Merkezi"].astype(str).str.replace(" TM", "", regex=False)

# Sadece tahmin edilen son haftayı sıralıyoruz
df_talep_hepsi = df_tahmin_talep_norm.sort_values(by=["Tarih", "Çıkış Transfer Merkezi", "Varış Transfer Merkezi"]).reset_index(drop=True)

# Transfer merkezleri ve koordinat sözlüğünü oluşturuyoruz
koordinatlar = {r["Transfer Merkezi"]: (r["Enlem"], r["Boylam"]) for idx, r in df_koordinat.iterrows()}
merkezler = list(koordinatlar.keys())

# Araç maliyetleri ve kapasite sözlüklerini oluşturuyoruz
arac_kapasiteleri = {}
kiralik_sabit_maliyetler = {}
kiralik_km_maliyetler = {}
spot_sabit_maliyetler = {}
spot_km_maliyetler = {}

for idx, r in df_maliyet.iterrows():
    ad = r["Araç Adı"]
    arac_kapasiteleri[ad] = r["Kapasite (desi)"]
    kiralik_sabit_maliyetler[ad] = r["Kiralık Araç Günlük Kira (TL)"]
    kiralik_km_maliyetler[ad] = r["Kiralık Araç Kilometre Başına Maliyet (TL)"]
    spot_sabit_maliyetler[ad] = r["Spot Araç Sabit Günlük Maliyet (TL)"]
    spot_km_maliyetler[ad] = r["Spot Kilometre Başına Maliyet (TL)"]

# Kiralık araç kısıtlarını hat bazında sözlüğe alıyoruz
kiralik_filo = {}
for idx, r in df_kiralik.iterrows():
    kiralik_filo[(r["Çıkış Transfer Merkezi"], r["Varış Transfer Merkezi"], r["Araç Türü"])] = r["Araç sayısı"]

# Haversine formülü ile iki koordinat arası mesafeyi hesaplayan yardımcı fonksiyon
def haversine(cikis, varis):
    if cikis == varis:
        return 0.0
    lat1, lon1 = koordinatlar[cikis]
    lat2, lon2 = koordinatlar[varis]
    R = 6371.0  # Dünya yarıçapı (km)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c

# Mesafe matrisini oluşturuyoruz
mesafeler = {(m1, m2): haversine(m1, m2) for m1 in merkezler for m2 in merkezler}

# Uzak şehirler
uzak_sehirler = {m for m in merkezler if mesafeler[("İstanbul", m)] > 600.0}

# Araç Tipi çıktı haritalama sözlüğü
arac_tipi_map = {
    "Tır": "TIR",
    "Kamyon": "Kamyon",
    "Hafif Kamyon": "Hafif Kamyon",
    "Kamyonet": "Kamyonet"
}

# 3. Adım: Günlük optimizasyon çözücüsü ve döngüsü başlatılıyor
tum_arac_atamalari = []
gunler = sorted(df_talep_hepsi["Tarih"].unique())
toplam_maliyet_genel = 0.0

# Taşınamayıp bir sonraki güne devreden kargo miktarlarını tutacak sözlük
# Anahtar: (çıkış_tm, varış_tm), Değer: desi_miktarı
devir_talep = {}

# MIP modelini kuran ve çözen genel yardımcı fonksiyon
def solve_mip_model(aktif_talepler, routes, time_limit_ms, is_last_day=False):
    r_tasinabilir = {}
    route_traversed_segments = {}
    for r in routes:
        for i in range(len(r)):
            for j in range(i+1, len(r)):
                o, d = r[i], r[j]
                r_tasinabilir.setdefault((o, d), []).append(r)
                route_traversed_segments[(r, o, d)] = [(r[k], r[k+1]) for k in range(i, j)]
                
    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        return None, None, None, None, None
        
    solver.SetSolverSpecificParametersAsString("limits/gap = 0.08")
    
    y = {}  # Spot araç adetleri (IntVar)
    f_rent = {}  # Kiralık akış miktarları (NumVar)
    f_spot = {}  # Spot akış miktarları (NumVar)
    kalan_desi = {}  # Taşınamayıp ertelenen akış miktarları (NumVar)
    
    rental_segment_flows = {}
    spot_segment_flows = {}
    
    z = {}
    for r in routes:
        for v in arac_kapasiteleri.keys():
            if len(r) == 2 and (r[0], r[1], v) in kiralik_filo:
                z[(r, v)] = kiralik_filo[(r[0], r[1], v)]
            else:
                z[(r, v)] = 0
                
    for (o, d), desi_mik in aktif_talepler.items():
        # Kiralık araç olan hatlarda ve son günde desi birikmesi (erteleme) olamaz
        has_rented = any(kiralik_filo.get((o, d, v), 0) > 0 for v in arac_kapasiteleri.keys())
        
        if is_last_day or has_rented:
            var_kalan = solver.NumVar(0.0, 0.0, "")
        else:
            var_kalan = solver.NumVar(0.0, desi_mik, "")
        kalan_desi[(o, d)] = var_kalan
        
        ilgili_rotalar = r_tasinabilir.get((o, d), [])
        for r in ilgili_rotalar:
            for v in arac_kapasiteleri.keys():
                if z.get((r, v), 0) > 0:
                    var_f_rent = solver.NumVar(0.0, desi_mik, "")
                    f_rent[(o, d, r, v)] = var_f_rent
                    segs = route_traversed_segments[(r, o, d)]
                    for seg in segs:
                        rental_segment_flows.setdefault((r, seg, v), []).append(var_f_rent)
                var_f_spot = solver.NumVar(0.0, desi_mik, "")
                f_spot[(o, d, r, v)] = var_f_spot
                segs = route_traversed_segments[(r, o, d)]
                for seg in segs:
                    spot_segment_flows.setdefault((r, seg, v), []).append(var_f_spot)
                if (r, v) not in y:
                    y[(r, v)] = solver.IntVar(0, 100, "")

    # Kısıt 1: Talep Karşılanma Kısıtı (Taşınan akışlar + kalan kargo == aktif talep)
    for (o, d), desi_mik in aktif_talepler.items():
        ilgili_rotalar = r_tasinabilir.get((o, d), [])
        terimler = [kalan_desi[(o, d)]]
        for r in ilgili_rotalar:
            for v in arac_kapasiteleri.keys():
                if (o, d, r, v) in f_rent: terimler.append(f_rent[(o, d, r, v)])
                if (o, d, r, v) in f_spot: terimler.append(f_spot[(o, d, r, v)])
        solver.Add(solver.Sum(terimler) == desi_mik)

    # Kısıt 2: Kiralık Araç Kapasite Kısıtı
    for (r, seg, v), flow_vars in rental_segment_flows.items():
        solver.Add(solver.Sum(flow_vars) <= arac_kapasiteleri[v] * z.get((r, v), 0))

    # Kısıt 3: Spot Araç Kapasite Kısıtı
    for (r, seg, v), flow_vars in spot_segment_flows.items():
        solver.Add(solver.Sum(flow_vars) <= arac_kapasiteleri[v] * y[(r, v)])

    # Kısıt 4: Spot Araçlar İçin %10 Minimum Doluluk Kısıtı (Sadece ilk çıkış segmentinde)
    for (r, v), var_y in y.items():
        first_seg = (r[0], r[1])
        flow_vars = spot_segment_flows.get((r, first_seg, v), [])
        if flow_vars:
            solver.Add(solver.Sum(flow_vars) >= 0.10 * arac_kapasiteleri[v] * var_y)
        else:
            solver.Add(var_y == 0)

    # Hedef Fonksiyonu (Maliyetler + sanal erteleme limitleri)
    hedef_terimleri = []
    
    # 1. Kiralık araç maliyetleri
    for r in routes:
        for v in arac_kapasiteleri.keys():
            z_val = z.get((r, v), 0)
            if len(r) == 2 and z_val > 0:
                dist = sum(mesafeler[(r[i], r[i+1])] for i in range(len(r)-1))
                hedef_terimleri.append(z_val * (kiralik_sabit_maliyetler[v] + kiralik_km_maliyetler[v] * dist))
                
    # 2. Spot araç maliyetleri
    for (r, v), var_y in y.items():
        dist = sum(mesafeler[(r[i], r[i+1])] for i in range(len(r)-1))
        hedef_terimleri.append(var_y * (spot_sabit_maliyetler[v] + spot_km_maliyetler[v] * dist))
        
    # 3. Sanal Erteleme Eşiği (Sadece karar kılavuzu olarak - final maliyete eklenmeyecek!)
    for (o, d), var_kalan in kalan_desi.items():
        dist = mesafeler[(o, d)]
        # Rota mesafesine göre dinamik erteleme eşiği
        esik = max(dist * 0.025, 5.0)
        hedef_terimleri.append(var_kalan * esik)
        
    solver.Minimize(solver.Sum(hedef_terimleri))
    
    solver.set_time_limit(time_limit_ms)
    status = solver.Solve()
    
    day_allocations = []
    ertelenenler = {}
    if status in [pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE]:
        # Gerçek araç maliyeti (Sanal erteleme eşik maliyetleri hariç!)
        gercek_arac_maliyeti = 0.0
        
        # 1. Kiralık araç atamaları
        for r in routes:
            for v in arac_kapasiteleri.keys():
                z_val = z.get((r, v), 0)
                if len(r) == 2 and z_val > 0:
                    dist = sum(mesafeler[(r[i], r[i+1])] for i in range(len(r)-1))
                    toplam_akis = sum(f_rent[(o, d, r, v)].solution_value() for o, d in aktif_talepler if (o, d, r, v) in f_rent)
                    tek_maliyet = round(kiralik_sabit_maliyetler[v] + kiralik_km_maliyetler[v] * dist, 2)
                    
                    kalan_akis = toplam_akis
                    for _ in range(z_val):
                        atanan_load = min(kalan_akis, arac_kapasiteleri[v])
                        kalan_akis = max(0.0, kalan_akis - atanan_load)
                        day_allocations.append({
                            "Tarih": None,
                            "Araç Tipi": f"Kiralık {arac_tipi_map.get(v, v)}",
                            "Çıkış TM": r[0] + " TM",
                            "Uğranılan Yerler": "-",
                            "Varış TM": r[1] + " TM",
                            "Atanan Desi": round(atanan_load, 2),
                            "Maliyet": tek_maliyet
                        })
                        gercek_arac_maliyeti += tek_maliyet
                        
        # 2. Spot araç atamaları
        for (r, v), var_y in y.items():
            adet = int(round(var_y.solution_value()))
            if adet > 0:
                dist = sum(mesafeler[(r[i], r[i+1])] for i in range(len(r)-1))
                toplam_akis = sum(f_spot[(o, d, r, v)].solution_value() for o, d in aktif_talepler if (o, d, r, v) in f_spot)
                tek_maliyet = round(spot_sabit_maliyetler[v] + spot_km_maliyetler[v] * dist, 2)
                
                kalan_akis = toplam_akis
                for _ in range(adet):
                    atanan_load = min(kalan_akis, arac_kapasiteleri[v])
                    kalan_akis = max(0.0, kalan_akis - atanan_load)
                    day_allocations.append({
                        "Tarih": None,
                        "Araç Tipi": f"Spot {arac_tipi_map.get(v, v)}",
                        "Çıkış TM": r[0] + " TM",
                        "Uğranılan Yerler": ", ".join([city + " TM" for city in r[1:-1]]) if len(r) > 2 else "-",
                        "Varış TM": r[-1] + " TM",
                        "Atanan Desi": round(atanan_load, 2),
                        "Maliyet": tek_maliyet
                    })
                    gercek_arac_maliyeti += tek_maliyet
                    
        # Ertelenen kargoları tespit ediyoruz
        for (o, d), var_kalan in kalan_desi.items():
            val = var_kalan.solution_value()
            if val > 0.01:
                ertelenenler[(o, d)] = val
                
        obj_val = solver.Objective().Value()
        best_bound = solver.Objective().BestBound()
        gap = 0.0
        if abs(obj_val) > 1e-6:
            gap = (abs(obj_val - best_bound) / abs(obj_val)) * 100.0
        return status, gercek_arac_maliyeti, gap, day_allocations, ertelenenler
        
    return status, None, None, None, None

log_yaz("2. Adım: Günlük optimizasyon döngüsü başlatılıyor...")
t_start_all = time.time()

# Her gün için sırasıyla çözümü yapıyoruz
for gun_idx, gun in enumerate(gunler):
    gun_str = pd.Timestamp(gun).strftime('%Y-%m-%d')
    is_last_day = (gun_str == "2026-05-17")
    
    df_gun_talep = df_talep_hepsi[df_talep_hepsi["Tarih"] == gun]
    talep = {(r["Çıkış Transfer Merkezi"], r["Varış Transfer Merkezi"]): r["Toplam Desi"] for idx, r in df_gun_talep.iterrows()}
    
    # Bugünün aktif talebi = bugünün orijinal talebi + geçmişten devreden talep
    aktif_talepler = {}
    tum_rota_anahtarlari = set(talep.keys()).union(devir_talep.keys())
    for k in tum_rota_anahtarlari:
        toplam_talep = talep.get(k, 0.0) + devir_talep.get(k, 0.0)
        if toplam_talep > 0.01:
            aktif_talepler[k] = toplam_talep
            
    if not aktif_talepler:
        log_yaz(f"Gün: {gun_str} | Aktif talep yok. Pas geçiliyor.")
        continue
        
    # Her şehir için toplam çıkış talebini hesaplıyoruz (küçük çıkış noktalarını belirlemek için)
    outgoing_demands = {}
    for (o, d), v in aktif_talepler.items():
        outgoing_demands[o] = outgoing_demands.get(o, 0.0) + v
    small_origins = {o for o, v in outgoing_demands.items() if v < 560.0}
    
    # ------------------ AŞAMA 1 ROTA HAVUZU (1-Stop + Seçici 2-Stop) ------------------
    rotalar_havuzu_stg1 = []
    
    # 1. Doğrudan rotalar
    for m1 in merkezler:
        for m2 in merkezler:
            if m1 != m2:
                rotalar_havuzu_stg1.append((m1, m2))
                
    # 2. 1 Ara duraklı rotalar (m1 -> c -> m2)
    for m1 in merkezler:
        for m2 in merkezler:
            if m1 == m2: continue
            dogrudan_dist = mesafeler[(m1, m2)]
            for c in merkezler:
                if c == m1 or c == m2: continue
                is_c_active = (m1, c) in aktif_talepler or (c, m2) in aktif_talepler
                if not is_c_active: continue
                ugramali_dist = mesafeler[(m1, c)] + mesafeler[(c, m2)]
                lim = 2000.0 if is_last_day else max(dogrudan_dist * 0.25, 150.0)
                if ugramali_dist <= dogrudan_dist + lim:
                    rotalar_havuzu_stg1.append((m1, c, m2))
                    
    # 3. Seçici 2 Ara duraklı rotalar (v0 -> o -> v2 -> d)
    # Küçük çıkış noktalarından kalkan desileri büyük akışlar üzerinden taşımak için.
    large_demand_pairs_sorted = [k for k, v in sorted(aktif_talepler.items(), key=lambda x: x[1], reverse=True) if v >= 560.0]
    large_demand_pairs = large_demand_pairs_sorted[:5]
    
    for o in small_origins:
        destinations = [d for (orig, d) in aktif_talepler.keys() if orig == o]
        for d in destinations:
            for (v0, v2) in large_demand_pairs:
                if v0 in [o, d] or v2 in [o, d] or v0 == v2: 
                    continue
                route_dist = mesafeler[(v0, o)] + mesafeler[(o, v2)] + mesafeler[(v2, d)]
                direct_dist = mesafeler[(v0, d)]
                if route_dist <= direct_dist + 2000.0:
                    rotalar_havuzu_stg1.append((v0, o, v2, d))
                    
    # Çift kayıtları kaldırıp sırayı koruyoruz
    rotalar_havuzu_stg1 = list(dict.fromkeys(rotalar_havuzu_stg1))
                    
    # Aşama 1'i çözmeyi deneriz (hafta içi 15 saniye, son gün 30 saniye limitli)
    t0_stg1 = time.time()
    limit_ms = 30000 if is_last_day else 15000
    status, cost, gap, res, ertelenenler = solve_mip_model(aktif_talepler, rotalar_havuzu_stg1, limit_ms, is_last_day=is_last_day)
    t1_stg1 = time.time()
    
    if status in [pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE] and cost is not None:
        toplam_maliyet_genel += cost
        for row in res:
            row["Tarih"] = gun_str
        tum_arac_atamalari.extend(res)
        
        # Devredilen kargoları güncelliyoruz
        devir_talep = ertelenenler.copy()
        kalan_toplam = sum(devir_talep.values())
        
        log_yaz(f"Gün: {gun_str} | Çözüldü (Aşama 1) | Maliyet: {cost:,.2f} TL | Gap: {gap:.2f}% | Devreden: {kalan_toplam:,.2f} desi | Rota Havuzu: {len(rotalar_havuzu_stg1)} | Süre: {t1_stg1-t0_stg1:.2f}s")
        continue
        
    # ------------------ AŞAMA 2 FALLBACK (Genişletilmiş Rota Havuzu) ------------------
    # Aşama 1 başarısız olursa, Stage 2 çalışır
    log_yaz(f"Gün: {gun_str} | Aşama 1 çözülemedi! Aşama 2 deneniyor...")
    
    rotalar_havuzu_stg2 = []
    for m1 in merkezler:
        for m2 in merkezler:
            if m1 != m2:
                rotalar_havuzu_stg2.append((m1, m2))
                
    for m1 in merkezler:
        for m2 in merkezler:
            if m1 == m2: continue
            dogrudan_dist = mesafeler[(m1, m2)]
            for c in merkezler:
                if c == m1 or c == m2: continue
                is_c_active = (m1, c) in aktif_talepler or (c, m2) in aktif_talepler
                if not is_c_active: continue
                ugramali_dist = mesafeler[(m1, c)] + mesafeler[(c, m2)]
                lim = max(dogrudan_dist * 0.40, 300.0) # Limiti genişletiyoruz
                if ugramali_dist <= dogrudan_dist + lim:
                    rotalar_havuzu_stg2.append((m1, c, m2))
                    
    # Tüm küçük origins için 2 ara duraklı rotaları daha geniş limitlerle ekliyoruz
    for o in small_origins:
        destinations = [d for (orig, d) in aktif_talepler.keys() if orig == o]
        for d in destinations:
            for (v0, v2) in large_demand_pairs:
                if v0 in [o, d] or v2 in [o, d] or v0 == v2: continue
                route_dist = mesafeler[(v0, o)] + mesafeler[(o, v2)] + mesafeler[(v2, d)]
                direct_dist = mesafeler[(v0, d)]
                if route_dist <= direct_dist + 2500.0:
                    rotalar_havuzu_stg2.append((v0, o, v2, d))
                    
    rotalar_havuzu_stg2 = list(dict.fromkeys(rotalar_havuzu_stg2))
                    
    t0_stg2 = time.time()
    status, cost, gap, res, ertelenenler = solve_mip_model(aktif_talepler, rotalar_havuzu_stg2, 30000, is_last_day=is_last_day)
    t1_stg2 = time.time()
    
    if status in [pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE] and cost is not None:
        toplam_maliyet_genel += cost
        for row in res:
            row["Tarih"] = gun_str
        tum_arac_atamalari.extend(res)
        
        devir_talep = ertelenenler.copy()
        kalan_toplam = sum(devir_talep.values())
        log_yaz(f"Gün: {gun_str} | Çözüldü (Aşama 2) | Maliyet: {cost:,.2f} TL | Gap: {gap:.2f}% | Devreden: {kalan_toplam:,.2f} desi | Rota Havuzu: {len(rotalar_havuzu_stg2)} | Süre: {t1_stg2-t0_stg2:.2f}s")
    else:
        log_yaz(f"Gün: {gun_str} | HATA! Aşama 2 de çözülemedi! solver_status: {status}")

t_end_all = time.time()
log_yaz(f"\n============================================================")
log_yaz(f"SON HAFTA OPTİMİZASYONU TAMAMLANDI!")
log_yaz(f"Son Hafta Toplam Operasyonel Maliyet: {toplam_maliyet_genel:,.2f} TL")
log_yaz(f"Toplam Hesaplama Süresi: {t_end_all - t_start_all:.2f} saniye")
log_yaz(f"============================================================")

# Sonuçları Excel dosyasına bültene uygun kolon ve formatta yazdırıyoruz (Arac_Planlama_v2_son_hafta.xlsx)
df_arac_planlama = pd.DataFrame(tum_arac_atamalari)
df_arac_planlama = df_arac_planlama[["Tarih", "Araç Tipi", "Çıkış TM", "Uğranılan Yerler", "Varış TM", "Atanan Desi", "Maliyet"]]

planlama_excel_yolu = os.path.join(calisma_dizini, "Arac_Planlama_v2_son_hafta.xlsx")
df_arac_planlama.to_excel(planlama_excel_yolu, index=False)

log_yaz(f"Son hafta araç atama planı başarıyla kaydedildi: {planlama_excel_yolu}")
log_yaz(f"Toplam atanan araç satır sayısı: {len(df_arac_planlama)}")

# Log dosyasını kapatıyoruz
log_dosyasi.close()
