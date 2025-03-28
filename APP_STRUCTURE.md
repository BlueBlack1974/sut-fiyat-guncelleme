# SUT Fiyat Güncelleme Uygulaması - Yapı ve Özellikler

## 1. Temel Amaç
- Excel formatındaki SUT fiyat listesini güncellemek
- Orijinal dosya formatını ve özelliklerini korumak (XLS veya XLSX)
- Minimum müdahale ile sadece fiyat kolonunu güncellemek

## 2. Veri İşleme Prensipleri
- Tüm işlemler bellek üzerinde (BytesIO)
- Geçici dosya oluşturmadan çalışma
- Orijinal dosya formatını koruma
- Formül ve stilleri muhafaza etme

## 3. Excel Yapısı ve Kullanıcı Girdileri
### Kullanıcıdan Alınan Kolon Bilgileri
- SUT Kodu Kolonu: Kullanıcı tarafından belirlenir
- İşlem Adı/Açıklama Kolonu: Kullanıcı tarafından belirlenir
- Fiyat Kolonu: Kullanıcı tarafından belirlenir (KDV Dahil/Hariç seçimi ile)

### Veri Özellikleri
- Başlık satırı genelde ilk 5 satır içinde
- P520030 kodlu işlemler için açıklama bazlı fiyatlandırma
- Diğer kodlar için direkt SUT kodu bazlı fiyatlandırma

## 4. Fiyat Güncelleme Süreci
### Admin Paneli
- Güncel fiyatlar admin panelinden girilir
- Veriler data/sut_fiyatlari.json dosyasında saklanır
- Admin girişleri doğrulanır

### Güncelleme Kuralları
#### EK2A için
- SUT kodu "P520030" olan satırları bul
- İşlem açıklamasına göre JSON'dan fiyat getir
- Açıklama eşleşmesi varsa fiyatı güncelle

#### EK2B ve EK2C için
- SUT koduna göre JSON'dan fiyat bul
- Eşleşen kod varsa fiyatı güncelle
- Formül varsa korumaya devam et

## 5. Hata Yönetimi
- Her adımda log tutma
- İşlem durumunu raporlama
- Hata mesajlarını loglama
- Güvenli hata kurtarma

## 6. Performans Kriterleri
- Minimum bellek kullanımı
- Hızlı işlem
- Gereksiz dosya I/O işlemi yapmama
- Verimli veri yapıları kullanma

## 7. Güvenlik
- Dosya formatı kontrolü
- Giriş verisi doğrulama
- Güvenli dosya işleme
- Hata durumunda veri kaybını önleme

## 8. Kullanıcı Arayüzü
- Basit ve anlaşılır
- İşlem durumu gösterimi
- Hata mesajları
- Başarı bildirimleri

## 9. Çıktı Formatı
- Orijinal dosya formatında kayıt
- Doğru MIME type kullanımı
- Uygun dosya adlandırma
- Başarılı güncelleme kontrolü

## Proje Yapısı

```
SUT_Fiyat_Guncelleme/
│
├── main.py                 # Ana uygulama dosyası
├── debug.log              # Log dosyası
├── requirements.txt       # Python bağımlılıkları
│
├── data/                  # Veri dosyaları
│   └── sut_fiyatlari.json # SUT fiyat verileri
│
├── static/               # Statik dosyalar (CSS, JS, vb.)
│   ├── css/
│   └── js/
│
├── templates/            # HTML şablonları
│   └── index.html
│
└── utils/               # Yardımcı modüller
    └── specialty_mapping.py  # Branş eşleştirme modülü
```

## Veri Yapısı

### SUT Fiyatları JSON Yapısı

```json
{
    "ek2a": {
        "2025-03-17 13:27:59": [
            {
                "uzmanlik_dali": "Anesteziyoloji ve Reanimasyon",
                "oh_kdv_haric": 109.0,
                "oh_kdv_dahil": 119.9,
                "otm_kdv_haric": 96.0,
                "otm_kdv_dahil": 105.6,
                "liste_turu": "ek2a"
            }
        ]
    },
    "ek2b": {
        "2025-03-17 13:05:43": [
            {
                "islem_kodu": "510010",
                "kdv_haric_fiyat": 185.3,
                "kdv_dahil_fiyat": 203.83,
                "liste_turu": "ek2b"
            }
        ]
    }
}
```

## Özel İşlemler

### EK2A Branş Eşleştirme

EK2A listesinde muayene hizmetleri için branş eşleştirmesi yapılırken:

1. Açıklama Temizleme:
   - "[Paket]", "[Kontrol]", "[Ek-2A]" gibi etiketler kaldırılır
   - Parantez içindeki metinler temizlenir
   - "muayene", "hizmetleri", "uzmanı" gibi gereksiz kelimeler çıkarılır
   - Dr., Prof., Doç. gibi unvanlar kaldırılır

2. Branş Eşleştirme:
   - Temizlenmiş açıklama, bilinen branş isimleri ve alternatifleriyle karşılaştırılır
   - Örnek alternatif isimler:
     * İç Hastalıkları = Dahiliye
     * Deri ve Zührevi Hastalıkları = Dermatoloji, Cildiye
     * Kulak Burun Boğaz = KBB
     * Çocuk Sağlığı ve Hastalıkları = Pediatri
   - En az %60 benzerlik oranı olan eşleşmeler kabul edilir
   - En yüksek benzerlik oranına sahip branş seçilir

3. Fiyat Seçimi:
   - Hastane türüne göre (özel hastane/tıp merkezi)
   - KDV durumuna göre (dahil/hariç)
   - İlgili branşın fiyatı seçilir

### EK2B ve EK2C İşlemleri

- SUT kodu ile birebir eşleştirme yapılır
- KDV durumuna göre ilgili fiyat seçilir
