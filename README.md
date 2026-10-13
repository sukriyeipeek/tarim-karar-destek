#  Tarımsal Karar Destek Sistemi

Tarımsal Karar Destek Sistemi; geçmiş tarımsal veriler, makine öğrenmesi ve matematiksel optimizasyon yöntemlerini kullanarak üreticilere **veriye dayalı ekim planı ve risk analizi** sunmayı amaçlayan bir karar destek uygulamasıdır.

Kullanıcı il, ilçe ve arazi büyüklüğünü girerek bölgesine uygun ürünleri inceleyebilir ve arazisinin ürünler arasında nasıl paylaştırılabileceğine dair öneriler alabilir.

## 🚀 Temel Özellikler

- 📍 İl ve ilçe bazlı uygun ürünlerin belirlenmesi
- 📊 Geçmiş üretim ve ekim alanı verilerinin analizi
- 🤖 Makine öğrenmesi ile ürün fiyat tahmini
- 🌾 Dönüm başına ortalama verim hesaplama
- 💰 Tahmini üretim, gelir ve kârlılık analizi
- ⚠️ Tarlada kalma / arz fazlası risk analizi
- 📏 Güvenli ekim kotasının değerlendirilmesi
- 🧮 PuLP ile optimal ekim alanı dağılımı

## 🧠 Sistem Nasıl Çalışır?

Kullanıcıdan alınan:

`İl + İlçe + Arazi Büyüklüğü`

bilgileri doğrultusunda bölgeye uygun ürünler belirlenir.

Ardından geçmiş üretim, fiyat ve maliyet verileri kullanılarak ürünlerin verim ve ekonomik potansiyelleri analiz edilir. Makine öğrenmesi modeli gelecek dönem ürün fiyatlarının tahmininde kullanılır.

Risk ve kota bilgileri de değerlendirilerek PuLP tabanlı optimizasyon modeli toplam araziyi uygun ürünler arasında paylaştırır.

```text
Kullanıcı Bilgileri
        ↓
Bölgeye Uygun Ürünler
        ↓
Veri Analizi & Feature Engineering
        ↓
Fiyat Tahmini
        ↓
Gelir / Kârlılık Analizi
        ↓
Risk & Kota Analizi
        ↓
PuLP Optimizasyonu
        ↓
Optimal Ekim Planı
```

## 🛠️ Kullanılan Teknolojiler

- Python, Pandas, Scikit-learn
- CatBoost (fiyat tahmini), XGBoost (ekim alanı ve üretim tahmini), Ridge regresyon (mazot ve enflasyon tahmini)
- PuLP (ekim optimizasyonu)
- FastAPI, SQLAlchemy, MySQL
- React.js (Vite)
- Git / GitHub

## 📊 Kullanılan Veri Türleri

Sistemde başlıca;

- ürün fiyatları,
- ekim alanı,
- üretim miktarı,
- mazot fiyatları,
- gübre fiyatları,
- enflasyon,
- yıl ve sezon

gibi veriler kullanılmaktadır.

Bu veriler temizleme, birleştirme ve feature engineering işlemlerinden geçirilerek makine öğrenmesi ve optimizasyon modellerine uygun hale getirilmektedir.

## 🎯 Projenin Amacı

Projenin amacı yalnızca en yüksek gelir potansiyeline sahip ürünü önermek değil; **kârlılık, üretim kapasitesi, arz riski ve ekim sınırlarını birlikte değerlendirerek daha dengeli bir üretim planı oluşturmaktır.**

Böylece üreticilerin veriye dayalı karar vermelerine ve mevcut tarım alanlarını daha verimli planlamalarına destek olunması hedeflenmektedir.

## 📈 Fiyat Modelinin Başarısı

Fiyat tahmini, geçen yılın aynı mevsimindeki fiyattan başlayıp beklenen enflasyonla büyütülüyor; CatBoost modeli bu tahmini ürün ve mevsime göre düzeltiyor.

Modeli geçmiş veriyle zamana göre test ettik: 2021–2025 arasındaki her noktada yalnızca o güne kadarki veriyle eğitip sonraki dört mevsimi tahmin ettirdik. Ortalama hata (MAPE) yaklaşık **%28**. İlk modelimiz rastgele bölmeyle ölçüldüğünde R² 0.95 görünüyordu, ama bu testte fiyatları sistematik olarak %30 düşük tahmin ettiği ortaya çıktı; yeni yapıda bu sapma %1.4'e indi.

```bash
python -m app.scripts.price_backtest
```

## ⚙️ Kurulum

Python 3.10 veya üstü gerekiyor (3.11 ile test edildi).

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Proje klasöründe bir `.env` dosyası oluşturup MySQL şifrenizi yazın:

```text
sifre=mysql_sifreniz
```

MySQL'de veritabanını oluşturun:

```sql
CREATE DATABASE tarim_karar_analiz CHARACTER SET utf8mb4;
```

Tablolar backend ilk çalıştığında otomatik oluşuyor. Backend'i bir kez açıp kapattıktan sonra ilçe, ürün ve kota verilerini yükleyin:

```bash
mysql -u root -p tarim_karar_analiz < database_seed.sql
python -m app.scripts.insert_kota
```

Frontend için:

```bash
cd frontend
npm install
```

## ▶️ Çalıştırma

```bash
uvicorn app.main:app_tarim --reload
```

```bash
cd frontend
npm run dev
```

Uygulama `http://localhost:5173` adresinde açılıyor. API dokümantasyonu `http://localhost:8000/docs` adresinde.

## 🧪 Testler

```bash
python -m pytest
```

## 🚧 Eksikler

- Henüz gerçek bir oturum/token sistemi yok; uygulama şu an yalnızca yerelde kullanılmak için.
- Kâr hesabında yalnızca gübre ve mazot giderleri otomatik hesaplanıyor, bu yüzden kârlar olduğundan yüksek çıkabiliyor.
- Hal fiyatları web sitelerinden okunuyor. İzmir Büyükşehir'in sitesine ulaşılamazsa Hal Kayıt Sistemi'nin Türkiye ortalamasına, o da yoksa kayıtlı son fiyatlara geçiliyor.

## 👥 Ekip

- Şükriye İpek
- Çağlar Özkan
