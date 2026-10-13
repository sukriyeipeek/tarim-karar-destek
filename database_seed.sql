-- Başlangıç verisi: ilçeler ve ürünler.
-- Tablolar backend ilk kez başlatıldığında SQLAlchemy tarafından oluşturulur;
-- bu dosyayı ondan sonra çalıştırın. Ardından kota tablosunu doldurmak için:
--   python -m app.scripts.insert_kota
--
-- Ürün adları data/processed/data_files altındaki veri setleriyle birebir aynı
-- olmalıdır (ör. BROKOLI, BROKOLİ değil): fiyat ve risk hesapları bu adlarla eşleşir.

USE tarim_karar_analiz;

INSERT INTO ilce (ilce_adi) VALUES
    ('Bayındır'),
    ('Bergama'),
    ('Menderes'),
    ('Tire'),
    ('Torbalı'),
    ('Ödemiş');

-- "Boş", tarlada henüz ekilmemiş alanı temsil eder; öneriler bu alana yapılır.
INSERT INTO urun (urun_adi, aktif) VALUES
    ('BIBER SIVRI', TRUE),
    ('DOMATES SALKIM', TRUE),
    ('SALATALIK SILOR', TRUE),
    ('KABAK TAZE', TRUE),
    ('KARPUZ', TRUE),
    ('PATLICAN UZUN', TRUE),
    ('Boş', TRUE),
    ('BAKLA', TRUE),
    ('BEZELYE', TRUE),
    ('BROKOLI', TRUE),
    ('ISPANAK', TRUE),
    ('KARNABAHAR', TRUE),
    ('LAHANA BEYAZ', TRUE),
    ('LAHANA KIRMIZI', TRUE),
    ('MARUL', TRUE),
    ('PIRASA', TRUE);
