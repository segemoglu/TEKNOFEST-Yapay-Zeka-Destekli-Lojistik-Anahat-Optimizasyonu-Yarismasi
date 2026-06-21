# 🚚 Lojistik Hacim (Desi) Tahminleme ve Rota Optimizasyonu Modeli

Bu proje, Teknofest Lojistik Rota Optimizasyonu yarışması kapsamında Türkiye genelindeki kargo/lojistik rotalarındaki günlük toplam hacmi (desi) tahmin etmek için geliştirilmiş **uçtan uca bir Makine Öğrenmesi (Machine Learning) boru hattıdır (pipeline).**

Zaman serisi verilerindeki eksik günleri, tatil/kriz etkilerini ve "Haftalık Döngü" (Weekly Seasonality) problemlerini aşmak için özel iteratif özellik mühendisliği (Feature Engineering) algoritmaları kullanılmıştır.

---

## ⚙️ Proje Mimarisi ve Teknik Öne Çıkanlar

* **Algoritma:** XGBoost Regressor (GPU Hızlandırmalı)
* **Kategorik Veri İşleme:** Target Encoding (Rota DNA'sını çıkarma)
* **Dinamik Gecikme (Lag) Mekanizması:** * Sabit 7 ve 14 günlük lag'ler yerine, tatil ve kriz günlerini atlayan **iteratif arama** mekanizması kurulmuştur.
  * Veri seyrekliği (Data Sparsity) yaşanan günlerde modelin çökmesini veya `0` tahmin üretmesini engelleyen, o güne özel (örneğin Pazar ise geçmişteki son Pazar'ı bulan) **Akıllı Fallback** algoritması geliştirilmiştir.
* **Target Leakage (Hedef Sızıntısı) Koruması:** Geçmiş lag verileri türetilirken modelin kopya çekmesi tamamen engellenmiştir.

---

## 📂 Dosya Yapısı ve Görevleri

Proje temel olarak iki ana bacaktan oluşmaktadır: **Eğitim (Training)** ve **Tahmin (Inference)**.

### 1. `01_model_train_colab.py` (Model Eğitim Fabrikası)
* **Ortam:** Google Colab (GPU gücü kullanılarak hızlı eğitim için tasarlandı).
* **Görev:** Master veri setini alır, nükleer veri temizliği yapar (Target Leakage önleme), RandomSearchCV ile XGBoost için en optimum hiperparametreleri avlar. Kategorik değişkenler için Target Encoder eğitilir.
* **Çıktı:** Bilgisayarınıza indirmeniz gereken iki adet zeka dosyası üretir:
  * `xgboost_sampiyon_model.pkl` (Eğitilmiş model ağı)
  * `target_encoder.pkl` (Kategorik veri dönüştürücü)

### 2. `02_model_predict_local.py` (Tam Otomatik Tahmin Boru Hattı)
* **Ortam:** Lokal makine (VS Code vb.)
* **Görev:** İstenen gelecek tarih aralığı (Örn: 11-17 Mayıs) için otomatik olarak bir Excel iskeleti oluşturur. Master veritabanına bağlanıp, iteratif olarak geçmiş günlerin temiz lag değerlerini bulur. `.pkl` dosyalarını uykudan uyandırır ve tahminleri üretir.
* **Çıktı:** Sadece istenen sütunları (`Tarih`, `Rota_Adi`, `Tahmin_Edilen_Desi`) içeren nihai yarışma/teslim dosyasını basar (`11_17_MAYIS_YARISMA_TESLIM_FINAL.xlsx`).

---

## 🚀 Kurulum ve Çalıştırma Sırası

Projeyi kendi ortamınızda çalıştırmak için aşağıdaki adımları sırasıyla izleyin:

### Gereksinimler
Aşağıdaki kütüphanelerin kurulu olduğundan emin olun:

```bash
pip install pandas numpy xgboost category_encoders scikit-learn joblib openpyxl
