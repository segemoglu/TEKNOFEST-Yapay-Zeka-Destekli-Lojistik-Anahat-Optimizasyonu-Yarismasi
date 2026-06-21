import pandas as pd
import numpy as np
import joblib
import warnings
import os

warnings.filterwarnings('ignore')

def tam_otomatik_tahmin_fabrikasi(master_excel_yolu, model_yolu, encoder_yolu, cikti_yolu):
    print("1. Master Veritabanı Okunuyor ve Analiz Ediliyor...")
    
    if not os.path.exists(master_excel_yolu):
        print(f"🚨 HATA: Master veri bulunamadı! Yol: {master_excel_yolu}")
        return
        
    df_db = pd.read_excel(master_excel_yolu)
    df_db.columns = [str(col).strip().replace(' ', '_') for col in df_db.columns]
    
    kolon_haritasi = {col: 'Tarih' for col in df_db.columns if str(col).lower() in ['tarih', 'tarıh']}
    df_db.rename(columns=kolon_haritasi, inplace=True)
    df_db['Tarih'] = pd.to_datetime(df_db['Tarih'], format='mixed', dayfirst=True)

    rota_isim = [col for col in df_db.columns if str(col).lower() == 'rota_adi']
    if rota_isim:
        df_db.rename(columns={rota_isim[0]: 'Rota_Adi'}, inplace=True)

    # ---------------------------------------------------------
    # 2. 11-17 MAYIS İSKELETİNİN YARATILMASI
    # ---------------------------------------------------------
    print("2. Excel İskeleti Kod Tarafından Otomatik Üretiliyor...")
    df_son_durum = df_db.sort_values('Tarih').drop_duplicates(subset=['Rota_Adi'], keep='last').copy()
    
    gelecek_tarihler = pd.date_range(start='2026-05-11', end='2026-05-17')
    klon_listesi = []
    
    hafta_katsayisi = 1 if ('Haftanin_Gunu' in df_db.columns and df_db['Haftanin_Gunu'].max() == 7) else 0

    for tarih in gelecek_tarihler:
        df_gecici = df_son_durum.copy()
        df_gecici['Tarih'] = tarih
        
        for col in ['Haftanin_Gunu', 'Ay', 'Gun', 'is_holiday', 'Kriz_Mi', 'tatil_sonrasi_mi']:
            if col in df_gecici.columns:
                if 'Haftanin_Gunu' == col: df_gecici[col] = tarih.dayofweek + hafta_katsayisi
                elif 'Ay' == col: df_gecici[col] = tarih.month
                elif 'Gun' == col: df_gecici[col] = tarih.day
                else: df_gecici[col] = 0
            
        klon_listesi.append(df_gecici)
    df_future = pd.concat(klon_listesi, ignore_index=True)

    # ---------------------------------------------------------
    # 3. HİBRİT VE İTERATİF LAG HESAPLAMASI (GÜN EŞLEMELİ)
    # ---------------------------------------------------------
    print("3. İteratif ve Gün Eşlemeli Lag'ler Hesaplanıyor...")
    db_indexli = df_db.set_index(['Rota_Adi', 'Tarih'])

    def temiz_lag_bul(hedef_tarih, rota, lag_gun_sayisi):
        aranan_tarih = hedef_tarih - pd.Timedelta(days=lag_gun_sayisi)
        
        # 1. İteratif Döngü (Kriz/Tatil olmayan gün ara)
        for _ in range(5): 
            if (rota, aranan_tarih) in db_indexli.index:
                row = db_indexli.loc[(rota, aranan_tarih)]
                if isinstance(row, pd.DataFrame): row = row.iloc[0]
                
                if row.get('Kriz_Mi', 0) == 1 or row.get('is_holiday', 0) == 1 or row.get('tatil_sonrasi_mi', 0) == 1:
                    aranan_tarih -= pd.Timedelta(days=7) # 7 gün daha geriye git
                    continue
                else:
                    return row.get('Toplam_Desi', 0) # Temiz veri bulundu
        
        # 2. Fallback (Aranan gün veritabanında yoksa veya hiç temiz gün bulamadıysak)
        # Sadece en son veriyi değil, "Aynı Günün Karakterini" bul
        try:
            rota_data = db_indexli.loc[rota]
            # Sadece hedef gün ile aynı günlere sahip kayıtları filtrele (Örn: Pazar ise Pazarları getir)
            ayni_gunler = rota_data[rota_data.index.get_level_values('Tarih').dayofweek == hedef_tarih.dayofweek]
            
            if not ayni_gunler.empty:
                return ayni_gunler.iloc[-1].get('Toplam_Desi', 0) # Geçmişteki en son aynı günün verisi
            else:
                # O günün verisi yoksa, rotanın en son bilinen herhangi bir verisi
                if isinstance(rota_data, pd.DataFrame): return rota_data.iloc[-1].get('Toplam_Desi', 0)
                return rota_data.get('Toplam_Desi', 0)
        except:
            return 0

    df_future['lag_7'] = df_future.apply(lambda row: temiz_lag_bul(row['Tarih'], row['Rota_Adi'], 7), axis=1)
    df_future['lag_14'] = df_future.apply(lambda row: temiz_lag_bul(row['Tarih'], row['Rota_Adi'], 14), axis=1)

    # ---------------------------------------------------------
    # 4. ŞAMPİYON MODELİN UYANDIRILMASI VE TAHMİN
    # ---------------------------------------------------------
    print("4. Şampiyon Model ve Encoder Yükleniyor...")
    target_encoder = joblib.load(encoder_yolu)
    final_model = joblib.load(model_yolu)

    drop_cols = ['Tarih', 'Toplam_Desi', 'Rota_Adi', 'Sentetik_Mi']
    X_future = df_future.drop(columns=[c for c in drop_cols if c in df_future.columns], errors='ignore')

    beklenen_sutunlar = final_model.feature_names_in_
    for col in beklenen_sutunlar:
        if col not in X_future.columns: X_future[col] = 0
    X_future = X_future[beklenen_sutunlar] 

    X_future = target_encoder.transform(X_future)

    tahminler = np.maximum(final_model.predict(X_future), 0)
    
    df_teslim = df_future[['Tarih', 'Rota_Adi']].copy()
    df_teslim['Tahmin_Edilen_Desi'] = np.round(tahminler, 2)
    df_teslim.sort_values(by=['Tarih', 'Rota_Adi'], inplace=True)

    df_teslim.to_excel(cikti_yolu, index=False)
    print(f"\n[🏆 OPERASYON BAŞARILI] Çıktı: '{cikti_yolu}'")

# ==========================================
# ÇALIŞTIRMA
# ==========================================
if __name__ == "__main__":
    MASTER_DB = r"C:\Users\bozku\Desktop\model_tahmin\MODEL1_READY_MASTER_DATASET_2_ESKİ.xlsx" 
    MODEL_DOSYASI = r"C:\Users\bozku\Desktop\model_tahmin\01_xgboost_sampiyon_model.pkl"
    ENCODER_DOSYASI = r"C:\Users\bozku\Desktop\model_tahmin\01_target_encoder.pkl"
    YARISMA_TESLIM_DOSYASI = r"C:\Users\bozku\Desktop\model_tahmin\11_17_MAYIS_YARISMA_TESLIM_vol3_FINAL.xlsx"
    
    tam_otomatik_tahmin_fabrikasi(MASTER_DB, MODEL_DOSYASI, ENCODER_DOSYASI, YARISMA_TESLIM_DOSYASI)
