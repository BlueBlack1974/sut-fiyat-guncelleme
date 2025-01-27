# Excel Fiyat Güncelleme Aracı

Bu araç, SUT fiyat listesindeki (EK-2B ve EK-2C) güncel fiyatları kullanarak Excel dosyanızdaki fiyatları günceller.

## Kurulum

1. Python'u bilgisayarınıza yükleyin (https://www.python.org/downloads/)
2. Bu projeyi bilgisayarınıza indirin
3. Gerekli kütüphaneleri yükleyin:
   ```
   pip install -r requirements.txt
   ```

## Kullanım

1. Komut satırında aşağıdaki komutu çalıştırın:
   ```
   python update_excel.py
   ```

2. Program sizden şu bilgileri isteyecek:
   - Excel dosyasının tam yolu (örn: C:\Users\User\Desktop\fiyat_listesi.xlsx)
   - İşlem kodu kolonu (örn: A, B, C)
   - Fiyat kolonu (örn: A, B, C)
   - Fiyat türü (dahil/haric) - varsayılan: dahil

3. Program Excel dosyanızı güncelleyecek ve sonuçları ekranda gösterecektir.

## Önemli Notlar

- Program sadece EK-2B ve EK-2C listelerindeki fiyatları günceller
- Bulunamayan kodların fiyatları değiştirilmez
- Excel dosyanız açıksa, program çalışmadan önce dosyayı kapatmanız gerekir
