# Tarımsal Karar Destek Sistemi

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![MySQL](https://img.shields.io/badge/MySQL-4479A1?logo=mysql&logoColor=white)
![CatBoost](https://img.shields.io/badge/CatBoost-FFCC00)
![PuLP](https://img.shields.io/badge/PuLP-optimizasyon-2E7D32)

Tarımsal Karar Destek Sistemi; geçmiş tarımsal veriler, makine öğrenmesi ve matematiksel optimizasyon yöntemlerini kullanarak üreticilere **veriye dayalı ekim planı ve risk analizi** sunan bir web uygulamasıdır.

Sistem, İzmir'in altı ilçesinde (Bayındır, Bergama, Menderes, Tire, Torbalı, Ödemiş) 15 sebze ürünü için çalışır. Kullanıcı tarlasını ve arazi büyüklüğünü girer; sistem gelecek sezon için fiyat tahmini, risk skoru ve tahmini kâr hesaplar, ardından araziyi ürünler arasında en dengeli şekilde paylaştıran bir ekim planı önerir.

Projenin amacı yalnızca en yüksek gelir potansiyeline sahip ürünü önermek değil; **kârlılık, üretim kapasitesi, arz riski ve ekim sınırlarını birlikte değerlendirerek daha dengeli bir üretim planı oluşturmaktır.**

## Özellikler

| Modül | Açıklama |
| --- | --- |
| Fiyat tahmini | Ürün ve sezon bazında gelecek dönem hal fiyatı (TL/kg) |
| Risk analizi | Arz fazlası, fiyat oynaklığı ve girdi maliyeti risklerini birleştiren 0–100 arası skor |
| Kârlılık analizi | Tahmini verim, üretim, gelir, gübre ve mazot giderleri ile net kâr |
| Ekim optimizasyonu | Kâr ve güvenliği birlikte gözeten, kota ve çeşitlendirme kısıtlı ekim planı |
| Tarla yönetimi | Tarla ekleme, ekili ürünler ve onaylanan planın tarlaya işlenmesi |
| Hal fiyatları | Günlük İzmir hal fiyatları; kaynak erişilemezse ulusal ortalama veya son kayıtlı fiyatlar |
| Yönetim paneli | Kullanıcı yetkilendirme ve ürünlerin aktif/pasif yapılması |

## Sistem Mimarisi

```text
┌───────────────────┐   HTTP / JSON   ┌──────────────────────────┐
│  React (Vite)     │ ──────────────► │  FastAPI                 │
│  Kullanıcı arayüzü│                 │  ├─ Fiyat tahmini        │
└───────────────────┘                 │  ├─ Risk analizi         │
                                      │  ├─ Kâr hesabı           │
                                      │  └─ Ekim optimizasyonu   │
                                      └─────┬──────────────┬─────┘
                                            │              │
                                 SQLAlchemy │              │ Eğitilmiş modeller
                                            ▼              ▼ ve veri setleri
                                     ┌────────────┐  ┌─────────────────┐
                                     │   MySQL    │  │ models/, data/  │
                                     └────────────┘  └─────────────────┘
```

Karar akışı:

```text
Kullanıcı bilgileri ─► Bölgeye uygun ürünler ─► Fiyat tahmini ─► Kârlılık analizi
                                                                       │
              Optimal ekim planı ◄─ PuLP optimizasyonu ◄─ Risk ve kota analizi
```

## Teknolojiler

| Katman | Teknoloji |
| --- | --- |
| Backend | Python, FastAPI, SQLAlchemy, Pydantic, passlib (bcrypt) |
| Veritabanı | MySQL |
| Veri işleme | Pandas, NumPy |
| Makine öğrenmesi | CatBoost (fiyat), XGBoost (ekim alanı ve üretim), Ridge regresyon (mazot ve enflasyon), Scikit-learn |
| Optimizasyon | PuLP (CBC çözücü) |
| Frontend | React 19, Vite, React Router, Recharts |

## Veri Kaynakları

| Veri | Kaynak |
| --- | --- |
| Sebze hal fiyatları (2014–2026) | İzmir Büyükşehir Belediyesi açık veri |
| İlçe bazında ekim alanı ve üretim | TÜİK |
| Enflasyon (TÜFE) | TCMB EVDS |
| Mazot fiyatları | Mevsimlik fiyat verileri |
| Güncel üre fiyatı | tradingeconomics.com |
| Günlük hal fiyatları | İzmir Büyükşehir Belediyesi; yedek olarak T.C. Ticaret Bakanlığı Hal Kayıt Sistemi |

Ham veriler temizlenir, aylık değerler mevsimlik ortalamalara çevrilir ve model girdileri için birleştirilir. Bu adımlar `data/processed/code` klasöründedir.

## Yöntem

### Fiyat tahmini

Tahmin, hedef sezonla aynı mevsimdeki en son fiyattan başlar ve beklenen enflasyonla büyütülür. CatBoost modeli bu tabanı ürün ve mevsime özgü sapmalara göre düzeltir:

```text
fiyat = taban fiyat × exp( yıl farkı × ln(1 + enflasyon) + model düzeltmesi )
```

Fiyatlar 2014–2026 arasında yaklaşık 35 kat arttığından, model doğrudan fiyat seviyesini değil enflasyonun açıklayamadığı değişimi öğrenir. Bu sayede ağaç tabanlı modellerin eğitimde görmediği fiyat seviyelerine ulaşamama sorunu ortadan kalkar. Enflasyon ve mazot tahminleri ayrı Ridge regresyon modellerinden gelir.

### Risk analizi

Beş risk bileşeni 0–100 arasında hesaplanır ve AHP (Analitik Hiyerarşi Süreci) ile belirlenen ağırlıklarla birleştirilir:

| Bileşen | Ağırlık | Ölçüt |
| --- | --- | --- |
| Kota doluluğu | 0.38 | İlçede beklenen ekim alanının dolma oranı |
| Fiyat oynaklığı | 0.29 | Enflasyondan arındırılmış fiyatların değişim katsayısı |
| Gübre | 0.16 | Güncel fiyatın tarihsel ortalamadan sapması |
| Mazot | 0.09 | Tahmini fiyatın tarihsel ortalamadan sapması |
| Enflasyon | 0.08 | Tahmini enflasyonun tarihsel ortalamadan sapması |

Toplam skor dört seviyeye ayrılır: Güvenli (0–25), Orta Risk (25–50), Riskli (50–75), Çok Riskli (75–100).

### Kârlılık analizi

```text
verim (ton/dönüm) = ilçenin tahmini üretimi / tahmini ekim alanı
gelir             = dönüm × verim × tahmini fiyat
gider             = gübre + mazot (+ isteğe bağlı sulama, işçilik ve tohum)
net kâr           = gelir − gider
```

Gübre ihtiyacı, Tarım ve Orman Bakanlığı'nın ürün bazındaki azot ve fosfor değerlerinden hesaplanır.

### Ekim optimizasyonu

Ekim planı bir doğrusal programlama problemi olarak çözülür:

```text
maksimize et   Σ xᵢ · skorᵢ             xᵢ: ürün i'ye ayrılan alan (dönüm)

kısıtlar       Σ xᵢ ≤ boş alan
               xᵢ ≤ 0.4 × boş alan       tek ürüne en fazla %40
               xᵢ ≤ kotaᵢ                ilçedeki beklenen ekim alanı
               xᵢ ≥ 0

skorᵢ = 0.7 × kâr skoruᵢ + 0.3 × (100 − riskᵢ)
```

Yalnızca hedef mevsimde ekilebilen ürünler aday olarak değerlendirilir.

## Model Değerlendirmesi

Fiyat modeli, gerçek kullanımı taklit eden **kayan başlangıçlı zaman serisi testi** ile değerlendirilmiştir: 2021–2025 arasındaki her başlangıç noktasında model yalnızca o tarihe kadarki veriyle eğitilmiş ve sonraki dört mevsimi tahmin etmiştir (261 tahmin).

| Yöntem | MAPE | Sapma |
| --- | --- | --- |
| Geçen yılın aynı mevsim fiyatı | %38.6 | −%40.2 |
| Geçen yıl × enflasyon | %26.5 | −%7.1 |
| İlk model (doğrudan fiyat tahmini) | %31.2 | −%29.8 |
| **Mevcut model** | **%28.4** | **−%1.4** |

İlk model rastgele veri bölmesiyle ölçüldüğünde R² 0.95 gösteriyordu; ancak zaman serisinde bu yöntem gelecekteki verinin eğitime sızmasına yol açar. Zamana göre yapılan test, ilk modelin fiyatları sistematik olarak yaklaşık %30 düşük tahmin ettiğini ortaya koymuş ve mevcut yapıya geçişi belirlemiştir.

Testi yeniden çalıştırmak için:

```bash
python -m app.scripts.price_backtest
```

## Kurulum

### Gereksinimler

- Python 3.10 veya üstü (3.11 ile test edilmiştir)
- MySQL 8
- Node.js 20 veya üstü

### Backend

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Proje kök dizininde bir `.env` dosyası oluşturun:

```text
sifre=<MySQL şifresi>
```

### Veritabanı

```sql
CREATE DATABASE tarim_karar_analiz CHARACTER SET utf8mb4;
```

Tablolar backend ilk kez çalıştırıldığında otomatik olarak oluşturulur. Ardından başlangıç verilerini yükleyin:

```bash
mysql -u root -p tarim_karar_analiz < database_seed.sql
python -m app.scripts.insert_kota
```

### Frontend

```bash
cd frontend
npm install
```

## Çalıştırma

```bash
uvicorn app.main:app_tarim --reload
```

```bash
cd frontend
npm run dev
```

| Adres | İçerik |
| --- | --- |
| `http://localhost:5173` | Web uygulaması |
| `http://localhost:8000/docs` | Etkileşimli API dokümantasyonu |

## Proje Yapısı

```text
app/
├── main.py           FastAPI uygulaması
├── routes.py         API uç noktaları
├── models.py         Veritabanı modelleri
├── schemas.py        İstek ve yanıt şemaları
├── services/         Fiyat, risk, kâr, optimizasyon ve veri servisleri
└── scripts/          Model eğitimi, veri yükleme ve backtest betikleri
data/
├── raw_data/         Ham veriler
└── processed/        Temizleme betikleri ve işlenmiş veri setleri
models/               Eğitilmiş modeller
frontend/             React uygulaması
tests/                Otomatik testler
database_seed.sql     İlçe ve ürün başlangıç verileri
```

## API

Başlıca uç noktalar aşağıdadır; tam liste `/docs` adresindedir.

| Metot | Uç nokta | Açıklama |
| --- | --- | --- |
| POST | `/tahmin/fiyat` | Ürün ve sezon için fiyat tahmini |
| POST | `/tahmin/risk` | Risk analizi |
| POST | `/kar/hesapla` | Kârlılık analizi |
| POST | `/oneri/tarla_getir` | Kayıtlı tarla için ekim planı |
| POST | `/oneri/manual` | İlçe ve alan girilerek ekim planı |
| POST | `/oneri/onayla` | Önerilen planın tarlaya işlenmesi |
| GET | `/istatistikler/hal-fiyatlari` | Günlük hal fiyatları |

## Testler

```bash
python -m pytest
```

Testler veritabanı veya internet bağlantısı gerektirmez.

## Bilinen Kısıtlar ve Yol Haritası

- **Kimlik doğrulama:** Uygulama şu an yerel kullanım içindir. Yayına alınmadan önce JWT tabanlı oturum yönetimi eklenmelidir.
- **Maliyet kalemleri:** Varsayılan kâr hesabı yalnızca gübre ve mazot giderlerini içerir. İşçilik, tohum ve sulama için bölgesel varsayılanlar eklenmesi planlanmaktadır.
- **Enflasyon tahmini:** Fiyat tahmini enflasyon tahminine doğrudan bağlıdır. Enflasyon modelinin de zaman serisi testiyle değerlendirilmesi planlanmaktadır.
- **Dış veri kaynakları:** Güncel hal ve gübre fiyatları web kaynaklarından alınır. Hal fiyatları için yedek kaynaklar mevcuttur.

## Ekip

- Şükriye İpek
- Çağlar Özkan
