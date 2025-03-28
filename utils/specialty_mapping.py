"""
Tıbbi branşların alternatif isimlerini içeren eşleştirme sözlüğü
"""

SPECIALTY_MAPPING = {
    "Anesteziyoloji ve Reanimasyon": [
        "anestezi",
        "anesteziyoloji",
        "anestezi ve reanimasyon",
        "anesteziyoloji ve yoğun bakım"
    ],
    "Beyin ve Sinir Cerrahisi": [
        "beyin cerrahisi",
        "nöroşirurji",
        "beyin ve sinir cerrahisi",
        "nörocerrahi"
    ],
    "Çocuk Cerrahisi": [
        "pediatrik cerrahi",
        "çocuk cerrahisi"
    ],
    "Çocuk Sağlığı ve Hastalıkları": [
        "pediatri",
        "çocuk hastalıkları",
        "çocuk sağlığı",
        "pediatrik"
    ],
    "Çocuk ve Ergen Ruh Sağlığı ve Hastalıkları": [
        "çocuk psikiyatrisi",
        "ergen psikiyatrisi",
        "çocuk ve ergen ruh sağlığı",
        "çocuk ve ergen psikiyatrisi"
    ],
    "Deri ve Zührevi Hastalıkları": [
        "dermatoloji",
        "deri hastalıkları",
        "cildiye",
        "deri",
        "dermatoloji ve veneroloji"
    ],
    "Enfeksiyon Hastalıkları ve Klinik Mikrobiyoloji": [
        "enfeksiyon hastalıkları",
        "enfeksiyon hastalıkları ve klinik mikrobiyoloji",
        "enfeksiyon",
        "enfeksiyon hastalıkları uzmanı",
        "enfeksiyon uzmanı",
        "mikrobiyoloji",
        "klinik mikrobiyoloji"
    ],
    "Fiziksel Tıp ve Rehabilitasyon": [
        "fizik tedavi",
        "ftr",
        "fizyoterapi",
        "fiziksel tıp",
        "fizik tedavi ve rehabilitasyon",
        "fiziksel tıp ve rehabilitasyon",
        "fizik tedavi ve rehabilitasyon uzmanı",
        "fiziksel tıp ve rehabilitasyon uzmanı",
        "fizik tedavi uzmanı",
        "fiziksel tıp uzmanı",
        "rehabilitasyon uzmanı"
    ],
    "Genel Cerrahi": [
        "cerrahi",
        "genel cerrahi"
    ],
    "Göğüs Hastalıkları": [
        "göğüs",
        "akciğer hastalıkları",
        "göğüs hastalıkları",
        "pulmoner hastalıklar"
    ],
    "Göz Hastalıkları": [
        "göz",
        "oftalmoloji",
        "göz hastalıkları"
    ],
    "İç Hastalıkları": [
        "dahiliye",
        "iç hastalıkları",
        "internal medicine"
    ],
    "Kadın Hastalıkları ve Doğum": [
        "kadın doğum",
        "jinekoloji",
        "kadın hastalıkları",
        "obstetrik ve jinekoloji",
        "kadın hastalıkları ve doğum"
    ],
    "Kalp ve Damar Cerrahisi": [
        "kalp cerrahisi",
        "kardiyovasküler cerrahi",
        "kalp damar cerrahisi",
        "kalp ve damar cerrahisi"
    ],
    "Kardiyoloji": [
        "kardiyoloji",
        "kalp hastalıkları"
    ],
    "Kulak Burun Boğaz Hastalıkları": [
        "kbb",
        "kulak burun boğaz",
        "kbb hastalıkları",
        "otolaringoloji"
    ],
    "Nöroloji": [
        "nöroloji",
        "sinir hastalıkları"
    ],
    "Ortopedi ve Travmatoloji": [
        "ortopedi",
        "travmatoloji",
        "ortopedi ve travmatoloji"
    ],
    "Plastik, Rekonstrüktif ve Estetik Cerrahi": [
        "plastik cerrahi",
        "plastik ve rekonstrüktif cerrahi",
        "plastik rekonstrüktif ve estetik cerrahi",
        "plastik ve estetik cerrahi"
    ],
    "Radyoloji": [
        "radyoloji",
        "radyodiagnostik",
        "tıbbi görüntüleme"
    ],
    "Ruh Sağlığı ve Hastalıkları": [
        "psikiyatri",
        "ruh sağlığı",
        "ruh hastalıkları",
        "psikiyatri ve ruh sağlığı",
        "ruh ve sinir hastalıkları",
        "psikiyatri uzmanı",
        "ruh sağlığı uzmanı",
        "psikiyatrist",
        "ruh hekimi",
        "psikiyatri hekimi"
    ],
    "Üroloji": [
        "üroloji",
        "üroloji hastalıkları"
    ]
}

def clean_specialty_name(description):
    """
    Uzmanlık adını temizler ve standartlaştırır
    """
    # Küçük harfe çevir
    description = description.lower()
    
    # Gereksiz kelimeleri kaldır
    remove_words = [
        "muayene",
        "hizmetleri",
        "paket",
        "kontrol",
        "ek-2a",
        "ek - 2a",
        "ek2a",
        "uzmanı",
        "uzman",
        "doktor",
        "dr",
        "dr.",
        "prof",
        "prof.",
        "doç",
        "doç.",
        "yard",
        "yard.",
        "yrd",
        "yrd.",
        "ek-2b",
        "ek - 2b",
        "ek2b",
        "ek-2c",
        "ek - 2c",
        "ek2c"
    ]
    
    # Parantez içindeki metinleri kaldır ve boşluk bırak
    import re
    description = re.sub(r'\[.*?\]', ' ', description)  # Köşeli parantez
    description = re.sub(r'\(.*?\)', ' ', description)  # Normal parantez
    
    # Gereksiz kelimeleri kaldır
    for word in remove_words:
        description = description.replace(word, ' ')
    
    # Türkçe karakterleri düzelt
    tr_chars = {
        'ı': 'i',
        'ğ': 'g',
        'ü': 'u',
        'ş': 's',
        'ö': 'o',
        'ç': 'c',
        'İ': 'i',
        'Ğ': 'g',
        'Ü': 'u',
        'Ş': 's',
        'Ö': 'o',
        'Ç': 'c'
    }
    for tr_char, eng_char in tr_chars.items():
        description = description.replace(tr_char, eng_char)
    
    # Fazla boşlukları temizle
    description = ' '.join(description.split())
    
    return description.strip()

def find_specialty_match(description):
    """
    Verilen açıklamaya en uygun uzmanlık alanını bulur
    """
    from difflib import SequenceMatcher
    
    try:
        # Açıklamayı temizle
        clean_desc = clean_specialty_name(description)
        
        best_ratio = 0
        best_match = None
        
        # Her bir uzmanlık alanı için kontrol et
        for specialty_key, alternatives in SPECIALTY_MAPPING.items():
            # Ana branş adıyla karşılaştır
            ratio = SequenceMatcher(None, clean_desc, clean_specialty_name(specialty_key)).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = specialty_key
                
            # Alternatif isimlerle karşılaştır
            for alt in alternatives:
                ratio = SequenceMatcher(None, clean_desc, clean_specialty_name(alt)).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = specialty_key
        
        # Benzerlik eşiğini 0.35'e düşür
        return (best_match, best_ratio) if best_ratio >= 0.35 else (None, 0)
        
    except Exception as e:
        print(f"Branş eşleştirme hatası: {str(e)}")
        return None, 0
