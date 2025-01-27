from flask import Flask, render_template, redirect, url_for, flash, jsonify, send_file, after_this_request, request
from flask_wtf import FlaskForm
from wtforms import FileField, RadioField, SubmitField, StringField
from wtforms.validators import DataRequired
from werkzeug.utils import secure_filename
import os
import json
import shutil
import time
from datetime import datetime, timedelta
from io import BytesIO
import openpyxl
import pandas as pd

# Flask app configuration
app = Flask(__name__,
    template_folder='templates',
    static_folder='static'
)

# Config
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')
app.config['TEMP_FOLDER'] = os.path.join(os.getcwd(), 'temp')

# Form classes
class UpdateForm(FlaskForm):
    excel_file = FileField('Excel Dosyası', validators=[DataRequired()])
    code_column = StringField('SUT Kodu Kolonu', validators=[DataRequired()])
    description_column = StringField('İşlem Açıklaması Kolonu', validators=[DataRequired()])
    price_column = StringField('Fiyat Kolonu', validators=[DataRequired()])
    price_type = RadioField('Fiyat Türü',
                          choices=[('dahil', 'KDV Dahil'),
                                 ('haric', 'KDV Hariç')],
                          default='dahil',
                          validators=[DataRequired()])
    hospital_type = RadioField('Hastane Türü',
                             choices=[('ozel_hastane', 'Özel Hastane'),
                                    ('ozel_tip_merkezi', 'Özel Tıp Merkezi')],
                             default='ozel_hastane',
                             validators=[DataRequired()])
    submit = SubmitField('Güncelle')

class AdminForm(FlaskForm):
    submit = SubmitField('SUT Verilerini Güncelle')

# Uzmanlık dalları ve eş anlamlıları
SPECIALTY_MAPPING = {
    'İç hastalıkları': ['Dahiliye', 'Internal'],
    'Kadın hastalıkları ve doğum': ['Jinekoloji', 'Kadın Doğum', 'Jinekolog'],
    'Kulak Burun Boğaz Hastalıkları': ['KBB', 'Kulak-Burun-Boğaz'],
    'Fizik tedavi ve rehabilitasyon': ['FTR', 'Fizik Tedavi'],
    'Göz hastalıkları': ['Oftalmoloji'],
    'Çocuk sağlığı ve hastalıkları': ['Pediatri'],
    'Ruh Sağlığı ve Hastalıkları': ['Psikiyatri'],
    'Deri ve zührevi hastalıkları': ['Dermatoloji', 'Cildiye'],
    'Nöroloji': ['Sinir Hastalıkları'],
    'Ortopedi ve travmatoloji': ['Ortopedi'],
    'Üroloji': ['Bevliye'],
    'Kardiyoloji': ['Kalp Hastalıkları'],
    'Kalp ve Damar Cerrahisi': ['Kardiyovasküler Cerrahi'],
    'Gastroenteroloji': []  # Eş anlamlısı yok, direkt kendisi kullanılacak
}

# Göz ardı edilecek kelimeler
IGNORE_WORDS = ['muayene', 'muayenesi', 'Muayene', 'Muayenesi', 'MUAYENE', 'MUAYENESI',
                'paket', 'Paket', 'PAKET', '[', ']', '[ paket ]', '[paket]', '**']

def clean_specialty_text(text):
    """Metinden göz ardı edilecek kelimeleri çıkarır ve temizler"""
    print(f"\nTemizleme öncesi metin: '{text}'")
    text = text.lower().strip()
    for word in IGNORE_WORDS:
        text = text.replace(word.lower(), '')
    text = ' '.join(text.split())  # Fazla boşlukları temizle
    print(f"Temizleme sonrası metin: '{text}'")
    return text

def find_specialty_match(text, target_specialty):
    """Verilen metin içinde uzmanlık dalı eşleşmesi arar"""
    if not text or not target_specialty:
        return False
        
    # Metinleri temizle
    cleaned_text = clean_specialty_text(text)
    cleaned_target = clean_specialty_text(target_specialty)
    print(f"\nKarşılaştırma: '{cleaned_text}' ile '{cleaned_target}'")
    
    # Tam eşleşme kontrolü
    if cleaned_text == cleaned_target:
        print("Tam eşleşme bulundu!")
        return True
        
    # Ana uzmanlık dalı kontrolü
    if target_specialty in SPECIALTY_MAPPING:
        # Önce ana uzmanlık dalının kendisiyle kontrol
        if cleaned_target in cleaned_text or cleaned_text in cleaned_target:
            print(f"Ana uzmanlık dalı eşleşmesi bulundu!")
            return True
            
        # Eş anlamlıları kontrol et
        for synonym in SPECIALTY_MAPPING[target_specialty]:
            cleaned_synonym = clean_specialty_text(synonym)
            print(f"Eş anlamlı kontrol: '{cleaned_text}' ile '{cleaned_synonym}'")
            
            if cleaned_text in cleaned_synonym or cleaned_synonym in cleaned_text:
                print(f"Eş anlamlı eşleşme bulundu: {synonym}")
                return True
                
    # Benzerlik oranı kontrolü
    from difflib import SequenceMatcher
    similarity = SequenceMatcher(None, cleaned_text, cleaned_target).ratio()
    print(f"Benzerlik oranı: {similarity}")
    if similarity > 0.8:
        print("Benzerlik eşleşmesi bulundu!")
        return True
    
    return False

def find_best_specialty_match(text, specialty_mapping):
    """Verilen metin için en iyi uzmanlık dalı eşleşmesini bul"""
    if not text:
        return None
        
    text = text.lower().strip()
    best_match = None
    max_similarity = 0
    
    for main_specialty, alternatives in specialty_mapping.items():
        # Ana uzmanlık dalı kontrolü
        if main_specialty.lower() in text:
            return main_specialty
            
        # Alternatif isimler kontrolü
        for alt in alternatives:
            if alt.lower() in text:
                return main_specialty
                
        # Kısmi eşleşme kontrolü
        main_words = set(main_specialty.lower().split())
        text_words = set(text.split())
        common_words = main_words.intersection(text_words)
        
        if common_words:
            similarity = len(common_words) / len(main_words)
            if similarity > max_similarity:
                max_similarity = similarity
                best_match = main_specialty
                
    return best_match if max_similarity > 0.5 else None

def update_excel_from_json(excel_file, hospital_type, code_column, description_column, price_column, price_type):
    """Excel dosyasını JSON verilerine göre güncelle"""
    try:
        # JSON verilerini oku
        data_dir = os.path.join(os.getcwd(), 'data')
        json_path = os.path.join(data_dir, 'sut_fiyatlari.json')
        
        if not os.path.exists(json_path):
            return None, 0, 0
            
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
            
        # SUT verilerini al
        sut_data = {}
        specialty_prices = {}
        
        # Ek2a listesinden uzmanlık dalı fiyatlarını al
        if 'ek2a' in json_data:
            latest_date = max(json_data['ek2a'].keys())
            for item in json_data['ek2a'][latest_date]:
                if isinstance(item, dict) and 'uzmanlik_dali' in item:
                    specialty = item['uzmanlik_dali']
                    if hospital_type == 'ozel_hastane':
                        price = item['oh_kdv_dahil'] if price_type == 'dahil' else item['oh_kdv_haric']
                    else:  # ozel_tip_merkezi
                        price = item['otm_kdv_dahil'] if price_type == 'dahil' else item['otm_kdv_haric']
                    specialty_prices[specialty] = price
            print(f"\nEk2a'dan {len(specialty_prices)} uzmanlık dalı fiyatı yüklendi")
            print("Yüklenen uzmanlık dalları ve fiyatları:")
            for specialty, price in specialty_prices.items():
                print(f"{specialty}: {price}")
        
        # Ek2b ve Ek2c listelerinden fiyatları al
        for liste_turu in ['ek2b', 'ek2c']:
            if liste_turu in json_data:
                latest_date = max(json_data[liste_turu].keys())
                print(f"\n{liste_turu.upper()} Listesi:")
                items = json_data[liste_turu][latest_date]
                
                for item in items:
                    if isinstance(item, dict) and 'islem_kodu' in item:
                        code = str(item['islem_kodu']).strip()
                        if code != 'P520030':  # P520030 dışındaki kodlar için
                            if price_type == 'dahil':
                                fiyat = item['kdv_dahil_fiyat']
                            else:
                                fiyat = item['kdv_haric_fiyat']
                            sut_data[code] = fiyat
                            print(f"- {code}: {fiyat} TL")
        
        # Excel'i yükle
        try:
            workbook = openpyxl.load_workbook(excel_file, data_only=True, read_only=False)
        except Exception as e:
            try:
                if excel_file.endswith('.xls'):
                    temp_dir = os.path.join(os.getcwd(), 'temp')
                    os.makedirs(temp_dir, exist_ok=True)
                    xlsx_path = os.path.join(temp_dir, 'temp.xlsx')
                    
                    # .xls dosyasını .xlsx'e çevir
                    df = pd.read_excel(excel_file)
                    df.to_excel(xlsx_path, index=False)
                    
                    # Yeni .xlsx dosyasını yükle
                    workbook = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=False)
                    
                    # Geçici dosyayı sil
                    delete_file_after_delay(xlsx_path)
                else:
                    raise e
            except Exception as e2:
                return None, 0, 0
                
        sheet = workbook.active
        
        # Kolon harflerini al
        code_col = code_column.upper()
        desc_col = description_column.upper()
        price_col = price_column.upper()
        
        # Başlık satırını bul
        header_row = 1  # Varsayılan olarak ilk satır
        updated_rows = 0
        total_rows = 0
        not_found_rows = 0
        
        for row in range(header_row + 1, sheet.max_row + 1):
            total_rows += 1
            
            # SUT kodunu al
            code_cell = f"{code_col}{row}"
            code = str(sheet[code_cell].value).strip() if sheet[code_cell].value else ""
            
            if code == "P520030":
                # İşlem açıklamasını al
                desc_cell = f"{desc_col}{row}"
                description = str(sheet[desc_cell].value).strip() if sheet[desc_cell].value else ""
                print(f"\nP520030 için işlem açıklaması kontrolü:")
                print(f"Satır {row} - İşlem açıklaması: '{description}'")
                
                # En uygun uzmanlık dalı eşleşmesini bul
                best_match = None
                best_similarity = 0
                
                for specialty in specialty_prices.keys():
                    print(f"\nUzmanlık dalı kontrolü: '{specialty}'")
                    if find_specialty_match(description, specialty):
                        # Eşleşme bulundu, fiyatı güncelle
                        new_price = specialty_prices[specialty]
                        old_price = sheet[f"{price_col}{row}"].value
                        sheet[f"{price_col}{row}"].value = new_price
                        updated_rows += 1
                        print(f"Eşleşme bulundu!")
                        print(f"Uzmanlık: {specialty}")
                        print(f"Fiyat güncellendi: {old_price} -> {new_price}")
                        break
                else:
                    print(f"Eşleşme bulunamadı!")
                    not_found_rows += 1
            
            elif code in sut_data:
                new_price = sut_data[code]
                old_price = sheet[f"{price_col}{row}"].value
                sheet[f"{price_col}{row}"].value = new_price
                updated_rows += 1
            else:
                not_found_rows += 1
        
        # Excel verilerini hafızada byte dizisine çevir
        excel_buffer = BytesIO()
        workbook.save(excel_buffer)
        excel_buffer.seek(0)
        
        return excel_buffer, updated_rows, not_found_rows
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, 0, 0

def cleanup_old_files():
    """1 saatten eski geçici dosyaları temizle"""
    temp_dir = os.path.join(os.getcwd(), 'temp')
    if not os.path.exists(temp_dir):
        return
        
    try:
        current_time = datetime.now()
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
            if current_time - file_modified > timedelta(hours=1):
                if os.path.isfile(file_path):
                    os.remove(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
    except Exception as e:
        print(f"Cleanup error: {str(e)}")

def delete_file_after_delay(file_path, delay=1):
    """Belirtilen süre sonra dosyayı sil"""
    def delete_file():
        try:
            time.sleep(delay)
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file: {str(e)}")
            
    import threading
    thread = threading.Thread(target=delete_file)
    thread.start()

def check_file_access(file_stream):
    """Excel dosyasının erişilebilir olup olmadığını kontrol et"""
    try:
        workbook = openpyxl.load_workbook(file_stream, read_only=True)
        workbook.close()
        return True
    except Exception as e:
        return False

# Routes
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    form = AdminForm()
    if form.validate_on_submit():
        try:
            sut_data = read_and_process_sut_files()
            if sut_data:
                # JSON dosyasına kaydet
                json_file = save_to_json(sut_data)
                
                if json_file:
                    flash('SUT verileri başarıyla güncellendi!', 'success')
                    return redirect(url_for('index'))
                else:
                    flash('JSON dosyası oluşturulamadı!', 'error')
            else:
                flash('SUT dosyaları okunamadı!', 'error')
                
        except Exception as e:
            flash(f"Hata: {str(e)}", 'error')
    return render_template('admin.html', form=form)

@app.route('/', methods=['GET', 'POST'])
def index():
    form = UpdateForm()
    
    if form.validate_on_submit():
        try:
            # Form verilerini al
            excel_file = form.excel_file.data
            hospital_type = form.hospital_type.data
            code_column = form.code_column.data
            description_column = form.description_column.data
            price_column = form.price_column.data
            price_type = form.price_type.data
            
            # Dosya erişilebilirliğini kontrol et
            if not check_file_access(excel_file):
                flash('Excel dosyası açık! Lütfen dosyayı kapatıp tekrar deneyin.', 'error')
                return redirect(url_for('index'))
            
            # Excel dosyasını oku ve güncelle
            result = update_excel_from_json(
                excel_file,
                hospital_type,
                code_column,
                description_column,
                price_column,
                price_type
            )
            
            if result is None or result[0] is None:
                flash('Güncelleme sırasında bir hata oluştu!', 'error')
                return redirect(url_for('index'))
                
            excel_buffer, updated_rows, not_found_rows = result
            
            # Güncellenmiş dosyayı kullanıcıya gönder
            original_name = os.path.splitext(excel_file.filename)[0]
            download_name = f"{original_name}_guncel.xlsx"
            
            return send_file(
                excel_buffer,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=download_name
            )
            
        except Exception as e:
            print(f"Hata oluştu: {str(e)}")
            import traceback
            traceback.print_exc()
            flash('Bir hata oluştu!', 'error')
            return redirect(url_for('index'))
            
    return render_template('index.html', form=form)

if __name__ == '__main__':
    app.run(debug=True)
