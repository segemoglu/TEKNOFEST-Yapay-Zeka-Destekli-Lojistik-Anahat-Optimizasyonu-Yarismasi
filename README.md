# 🏆 TEKNOFEST 2026 - Lojistik Hacim Tahminleme ve Rota Optimizasyonu

Bu proje, **Teknofest Lojistik Rota Optimizasyonu Yarışması** kapsamında geliştirilmiş uçtan uca bir **Makine Öğrenmesi + Yöneylem Araştırması (Optimization)** çözümüdür.

Sistem iki ana aşamadan oluşmaktadır:

1. 📈 **Kargo Hacmi Tahmini (Machine Learning)**

   * XGBoost tabanlı zaman serisi tahmin modeli
   * Feature Engineering
   * Target Encoding
   * Eksik gün ve sezon etkilerine karşı özel algoritmalar

2. 🚚 **Araç Sevk Planlama ve Rota Optimizasyonu**

   * Google OR-Tools
   * Mixed Integer Programming (MIP)
   * Minimum maliyetli araç planlama

---

# 🏗️ Sistem Mimarisi

```
                 Geçmiş Kargo Verisi
                         |
                         ↓
              Feature Engineering
                         |
                         ↓
                 XGBoost Modeli
                         |
                         ↓
              Tahminlenen Talep veya DatasetA
                         |
                         ↓
              Google OR-Tools MIP
                         |
                         ↓
              Optimize Araç Planı
```

---

# 📦 Kullanılan Teknolojiler

| Alan             | Teknoloji       |
| ---------------- | --------------- |
| Machine Learning | XGBoost         |
| Encoding         | Target Encoder  |
| Optimization     | Google OR-Tools |
| Programming      | Python 3.8+     |
| Data Processing  | Pandas / NumPy  |
| Model Kaydetme   | Joblib          |
| Veri Formatı     | Excel           |

---

# ⚙️ Kurulum

Projeyi çalıştırmadan önce gerekli paketleri yükleyin:

```bash
pip install -r requirements.txt
```

## requirements.txt

```txt
pandas
numpy
xgboost
category_encoders
scikit-learn
joblib
openpyxl
ortools
```

---

# 🚀 Çalıştırma Akışı

Proje iki ana pipeline'dan oluşmaktadır:

## 1. 📈 Makine Öğrenmesi Pipeline

### Model_Train.ipynb

Model eğitim sürecini gerçekleştirir.

Yapılan işlemler:

* Veri temizleme
* Feature Engineering
* Target Leakage kontrolü
* Lag feature üretimi
* Target Encoding
* XGBoost hiperparametre optimizasyonu
* RandomSearchCV

Çıktılar:

```
xgboost_sampiyon_model.pkl
target_encoder.pkl
```

---

## Model_Predict.py

Belirlenen tarih aralığı için otomatik tahmin üretir.

Örnek:

```
11-17 Mayıs 2026
```

Özellikler:

✅ Otomatik tarih oluşturma
✅ Eksik veri yönetimi
✅ Akıllı Fallback algoritması
✅ Geçmiş haftalardan referans alma

Çıktı:

```
11_17_MAYIS_YARISMA_TESLIM_FINAL.xlsx
```

---

# 🚚 2. Optimizasyon Pipeline

Google OR-Tools kullanılarak araç sevk planlaması yapılır.

Amaç:

> Minimum maliyet ile maksimum taşıma kapasitesini karşılayan araç rotalarını oluşturmak.

---

## optimizasyon_v2.py

### Tüm dönem optimizasyonu

Kapsam:

```
01 Ocak 2026
        |
        ↓
17 Mayıs 2026
```


Çıktılar:

```
Arac_Planlama_v2.xlsx
optimzasyon_v2.log
```

---

## optimizasyon_v2_son_hafta.py

Sadece yarışma tahmin haftasını optimize eder.

Kapsam:

```
11 - 17 Mayıs 2026
```

Avantaj:

* Geçmiş kargo verisine ihtiyaç duymaz
* Daha hızlı çözüm üretir

Çıktılar:

```
Arac_Planlama_v2_son_hafta.xlsx
optimizasyon_v2_son_hafta.log
```

---

# 📂 Gerekli Dosya Yapısı

Proje klasörü aşağıdaki yapıda olmalıdır:

```
Project/
│
├── Model_Train.ipynb
├── Model_Predict.py
├── optimizasyon_v2.py
│
├── Master_Veri.xlsx
├── Koordinatlar v2.xlsx
├── Arac_Kapasite_Maliyet.xlsx
├── Kiralik_Araclar.xlsx
├── Tahminlenen_Talep.xlsx
└── Desi_talep.xlsx
```

---

# 📊 Girdi Dosyaları

| Dosya                      | Açıklama                         | Kullanım     |
| -------------------------- | -------------------------------- | ------------ |
| Master_Veri.xlsx           | Eğitim veri seti                 | ML           |
| Koordinatlar v2.xlsx       | TM koordinatları                 | Optimizasyon |
| Arac_Kapasite_Maliyet.xlsx | Araç kapasite ve maliyet bilgisi | Optimizasyon |
| Kiralik_Araclar.xlsx       | Sabit araç bilgileri             | Optimizasyon |
| Tahminlenen_Talep.xlsx     | Tahmin çıktısı                   | Optimizasyon |
| Desi_talep.xlsx            | Geçmiş talep verisi              | Optimizasyon |

Eksik dosya durumunda sistem hata mesajı vererek güvenli şekilde durur.

---

# 📑 Optimizasyon Çıktı Formatı

Üretilen planlama dosyası:

| Kolon            | Açıklama                   |
| ---------------- | -------------------------- |
| Tarih            | Sevk günü                  |
| Araç Tipi        | Kullanılan araç            |
| Çıkış TM         | Başlangıç transfer merkezi |
| Uğranılan Yerler | Ara duraklar               |
| Varış TM         | Hedef merkez               |
| Atanan Desi      | Taşınan hacim              |
| Maliyet          | Toplam sevkiyat maliyeti   |

---

# 🧠 Algoritmik Özellikler

## Smart Fallback (Tahmin)

Model eksik veri durumunda:

Örneğin:

```
Tahmin günü için 7 günlük lag yok
```

yerine:

```
Geçmişteki aynı gün paterni bulunur
```

ve tahmin devam eder.

---

# ⚙️ Optimizasyon Parametreleri

## Çözüm Süresi

| Durum              | Süre      |
| ------------------ | --------- |
| Hafta içi günler   | 15 saniye |
| Son gün (17 Mayıs) | 30 saniye |

---

## MIP Ayarları

```
MIP Gap = %8
```

Çözücü bu seviyeye ulaştığında daha iyi çözüm aramayı bırakır ve sonraki güne geçer.

---

# 🎯 Proje Özeti

Bu proje:

* 📈 Makine öğrenmesi ile talep tahmini
* 🚛 Araç kapasite planlama
* 🗺️ Rota optimizasyonu
* 💰 Minimum maliyet hedefleme

adımlarını tek bir otomatik pipeline içerisinde birleştiren **hibrit ML + OR çözümüdür.**

---

## 👨‍💻 Geliştirme

Python kullanılarak geliştirilmiştir.

Ana teknolojiler:

```
Python
XGBoost
Pandas
Scikit-Learn
Google OR-Tools
```
