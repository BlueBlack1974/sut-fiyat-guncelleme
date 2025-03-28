from flask import Flask, render_template, redirect, url_for, flash, jsonify, send_file, after_this_request, request, Response
from flask_wtf import FlaskForm
from wtforms import FileField, RadioField, SubmitField, StringField
from wtforms.validators import DataRequired
from werkzeug.utils import secure_filename
import pandas as pd
import json
import os
from io import BytesIO
import win32com.client
import pythoncom
import tempfile
import datetime
from difflib import SequenceMatcher
from utils.specialty_mapping import find_specialty_match, clean_specialty_name

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

# Gerekli klasörleri oluştur
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['TEMP_FOLDER'], exist_ok=True)

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
    sut_file = FileField('SUT Dosyası')  # Dosya yükleme alanı
    submit = SubmitField('SUT Verilerini Güncelle')
    clear_data = SubmitField('Verileri Temizle')  # Temizleme butonu eklendi

def get_column_index(column_letter):
    """Excel kolon harfini indekse çevirir (A=1, B=2, ...)"""
    if not column_letter:
        return None
        
    if column_letter.isdigit():
        return int(column_letter)
        
    result = 0
    for i, char in enumerate(reversed(column_letter.upper())):
        result += (ord(char) - ord('A') + 1) * (26 ** i)
    return result

def find_header_row(df, code_column, description_column, price_column):
    """Excel'de başlık satırını bul (1-5 arası satırlarda ara)"""
    try:
        # Kolon indekslerini bul
        code_idx = code_column if isinstance(code_column, int) else get_column_index(code_column)
        desc_idx = description_column if isinstance(description_column, int) else get_column_index(description_column)
        price_idx = price_column if isinstance(price_column, int) else get_column_index(price_column)
        
        if code_idx is None or desc_idx is None or price_idx is None:
            log_to_file("Geçersiz kolon indeksi")
            return 0
            
        # İlk 5 satırı kontrol et
        for i in range(min(5, len(df))):
            row = df.iloc[i]
            # Başlık satırını bulmak için bazı anahtar kelimeleri kontrol et
            row_str = ' '.join(str(x).lower() for x in row if pd.notna(x))
            if any(keyword in row_str for keyword in ['sut', 'kod', 'işlem', 'fiyat', 'tutar', 'ücret']):
                return i
        return 0
        
    except Exception as e:
        log_to_file(f"Başlık satırı bulma hatası: {str(e)}")
        return 0

def log_to_file(message):
    """Mesajı dosyaya yaz"""
    with open('debug.log', 'a', encoding='utf-8') as f:
        f.write(f"{message}\n")
        f.flush()

def add_p_to_code(code):
    """SUT koduna P ekler (eğer L ile başlamıyorsa)"""
    if isinstance(code, str):
        code = code.strip()
        if not code.startswith('P') and not code.startswith('L'):
            code = 'P' + code
    return str(code)

def update_excel_from_json(excel_file, filename, df, code_idx, desc_idx, price_idx, hospital_type, price_type, updated_rows, not_found_rows):
    """Excel dosyasını JSON'dan gelen fiyatlarla günceller"""
    try:
        log_to_file(f"Güncelleme başlıyor... SUT Kodu: {code_idx}, Açıklama: {desc_idx}, Fiyat: {price_idx}, "
                   f"Fiyat Türü: {price_type}, Hastane Türü: {'Özel Hastane' if hospital_type == 'ozel_hastane' else 'Özel Tıp Merkezi'}")
        
        # JSON verisini oku
        json_path = os.path.join(os.path.dirname(__file__), 'data', 'sut_fiyatlari.json')
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                sut_data = json.load(f)
                log_to_file(f"JSON dosyası okundu: {json_path}")
                
                # Her liste için en son tarihi bul
                latest_dates = {}
                for liste_turu in ['ek2a', 'ek2b', 'ek2c']:
                    if liste_turu in sut_data:
                        latest_dates[liste_turu] = max(sut_data[liste_turu].keys())
                        log_to_file(f"{liste_turu} için en son tarih: {latest_dates[liste_turu]}")
                
                # Her liste için fiyat verilerini al
                price_lists = {}
                for liste_turu, latest_date in latest_dates.items():
                    price_lists[liste_turu] = sut_data[liste_turu][latest_date]
                    log_to_file(f"{liste_turu} fiyat listesi alındı, {len(price_lists[liste_turu])} kayıt bulundu")
                
        except Exception as e:
            log_to_file(f"JSON okuma hatası: {str(e)}")
            return None, 0, 0
        
        # Geçici dosya yolları oluştur
        temp_dir = tempfile.mkdtemp()
        temp_input = os.path.join(temp_dir, "temp_input" + os.path.splitext(filename)[1])
        temp_output = os.path.join(temp_dir, "temp_output" + os.path.splitext(filename)[1])
        
        try:
            # Excel dosyasını geçici konuma kaydet
            excel_file.seek(0)
            with open(temp_input, 'wb') as f:
                f.write(excel_file.read())
            
            log_to_file(f"Excel dosyası geçici konuma kaydedildi: {temp_input}")
            
            # Excel COM nesnelerini başlat
            pythoncom.CoInitialize()
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = False
            excel.DisplayAlerts = False
            
            try:
                # Excel dosyasını aç
                log_to_file("Excel dosyası açılıyor...")
                wb = excel.Workbooks.Open(temp_input)
                ws = wb.ActiveSheet
                log_to_file(f"Excel dosyası açıldı. Aktif sayfa: {ws.Name}")
                
                # Son satırı bul
                try:
                    last_row = ws.UsedRange.Rows.Count
                    log_to_file(f"Son satır (UsedRange): {last_row}")
                except:
                    # Alternatif yöntem
                    last_row = ws.Cells(ws.Rows.Count, code_idx).End(-4162).Row
                    log_to_file(f"Son satır (End-xlUp): {last_row}")
                
                # İlk 10 satırı kontrol et
                log_to_file("\nİlk 10 satır kontrolü:")
                for row in range(1, 11):
                    code_val = ws.Cells(row, code_idx).Value
                    desc_val = ws.Cells(row, desc_idx).Value
                    price_val = ws.Cells(row, price_idx).Value
                    log_to_file(f"Satır {row}:")
                    log_to_file(f"  SUT Kodu ({code_idx}): {code_val}")
                    log_to_file(f"  Açıklama ({desc_idx}): {desc_val}")
                    log_to_file(f"  Fiyat ({price_idx}): {price_val}")
                
                # Fiyat listelerini hazırla
                log_to_file("Fiyat listeleri hazırlanıyor...")
                
                # EK2B ve EK2C'yi dictionary'e çevir - hızlı erişim için
                ek2b_dict = {item['islem_kodu']: item for item in price_lists['ek2b']}
                ek2c_dict = {item['islem_kodu']: item for item in price_lists['ek2c']}
                
                # Her satır için işlem yap
                row = 2  # Başlık satırından sonra başla
                updated_count = 0
                not_found_count = 0
                updated_rows = []  # Liste olarak tanımla
                not_found_rows = []  # Liste olarak tanımla
                log_messages = []  # Log mesajlarını toplu yazmak için
                
                try:
                    while row <= last_row:
                        try:
                            # SUT kodunu oku
                            cell_value = ws.Cells(row, code_idx).Value
                            if cell_value is None:
                                sut_code = ""
                            elif isinstance(cell_value, (int, float)):
                                sut_code = str(int(cell_value))
                            else:
                                sut_code = str(cell_value)
                            sut_code = sut_code.strip()
                            
                            if not sut_code:
                                row += 1
                                continue

                            found_price = None
                            
                            # P520030 kodu için EK2A'da branş eşleştirmesi yap
                            if sut_code == "P520030":
                                try:
                                    desc_val = str(ws.Cells(row, desc_idx).Value or "").strip()
                                    specialty_match = find_specialty_match(desc_val)
                                    if specialty_match:
                                        specialty, score = specialty_match  # tuple'ı ayrıştır
                                        
                                        for item in price_lists['ek2a']:
                                            if item['uzmanlik_dali'].lower() == specialty.lower():
                                                found_price = item
                                                break
                                except Exception as e:
                                    log_messages.append(f"P520030 işleme hatası - Satır {row}: {str(e)}")
                                    row += 1
                                    continue
                            
                            # P520030 değilse EK2B ve EK2C'de ara
                            else:
                                # Önce EK2B'de ara
                                found_price = ek2b_dict.get(sut_code)
                                
                                # EK2B'de bulunamadıysa EK2C'de ara
                                if not found_price:
                                    found_price = ek2c_dict.get(sut_code)
                            
                            # Fiyat güncelleme
                            if found_price:
                                try:
                                    if sut_code == "P520030":
                                        # EK2A için fiyat güncelleme
                                        new_price = float(found_price['oh_kdv_haric' if price_type == 'haric' else 'oh_kdv_dahil'] if hospital_type == 'ozel_hastane' else found_price['otm_kdv_haric' if price_type == 'haric' else 'otm_kdv_dahil'])
                                    else:
                                        # EK2B ve EK2C için fiyat güncelleme
                                        new_price = float(found_price['kdv_haric_fiyat' if price_type == 'haric' else 'kdv_dahil_fiyat'])
                                    
                                    ws.Cells(row, price_idx).Value = new_price
                                    updated_count += 1
                                    updated_rows.append(row)
                                except Exception as e:
                                    log_messages.append(f"Fiyat güncelleme hatası - Satır {row}: {str(e)}")
                            else:
                                not_found_count += 1
                                not_found_rows.append(row)
                            
                            # Her 100 satırda bir log yaz
                            if len(log_messages) >= 100:
                                log_to_file("\n".join(log_messages))
                                log_messages = []
                            
                            row += 1
                            
                            # Her 1000 satırda bir ilerleme bilgisi ver
                            if row % 1000 == 0:
                                log_to_file(f"\nİşlenen satır: {row}, Güncellenen: {updated_count}, Bulunamayan: {not_found_count}")
                                
                        except Exception as e:
                            log_messages.append(f"Satır işleme hatası - Satır {row}: {str(e)}")
                            row += 1
                            continue
                            
                    # Kalan log mesajlarını yaz
                    if log_messages:
                        log_to_file("\n".join(log_messages))
                        
                except Exception as e:
                    log_to_file(f"Genel işleme hatası: {str(e)}")
                
                log_to_file(f"\nGüncelleme tamamlandı. Toplam {row-2} satır işlendi.")
                log_to_file(f"Güncellenen: {updated_count}, Bulunamayan: {not_found_count}")
                
                # Dosyayı kaydet
                wb.SaveAs(temp_output)
                wb.Close(False)
                log_to_file("Excel dosyası kaydedildi ve kapatıldı.")
                
                # Dosyayı oku ve BytesIO nesnesine aktar
                with open(temp_output, 'rb') as f:
                    output = BytesIO(f.read())
                
                return output, updated_count, not_found_count
                
            finally:
                excel.Quit()
                pythoncom.CoUninitialize()
                log_to_file("Excel nesneleri temizlendi.")
                
        finally:
            # Geçici dosyaları temizle
            try:
                os.remove(temp_input)
                os.remove(temp_output)
                os.rmdir(temp_dir)
                log_to_file("Geçici dosyalar temizlendi.")
            except:
                pass
                
    except Exception as e:
        log_to_file(f"Excel güncelleme hatası: {str(e)}")
        import traceback
        log_to_file(traceback.format_exc())
        return None, 0, 0

def update_excel_from_json_original(excel_file, filename, df, code_idx, desc_idx, price_idx, hospital_type, price_type, updated_rows, not_found_rows):
    """Excel dosyasını JSON'dan gelen fiyatlarla güncelle"""
    try:
        log_to_file("\n=== EXCEL OKUMA BAŞLIYOR ===")
        
        # Excel dosyası bilgileri
        log_to_file(f"Dosya adı: {filename}")
        
        # Excel dosyasını oku
        df = pd.read_excel(excel_file)
        
        # Kolon indekslerini bul
        code_idx = code_column if isinstance(code_column, int) else get_column_index(code_column)
        desc_idx = description_column if isinstance(description_column, int) else get_column_index(description_column)
        price_idx = price_column if isinstance(price_column, int) else get_column_index(price_column)
        
        # Excel dosyasını güncelle
        result = update_excel_from_json(excel_file, filename, df, code_idx, desc_idx, price_idx, hospital_type, price_type, updated_rows, not_found_rows)
        
        return result
            
    except Exception as e:
        log_to_file(f"Excel okuma/işleme hatası: {str(e)}")
        import traceback
        log_to_file(traceback.format_exc())
        return None
            
def read_and_process_sut_files():
    # JSON verilerini oku
    try:
        with open('sut_data.json', 'r', encoding='utf-8') as f:
            json_data = json.load(f)
            return json_data
    except FileNotFoundError:
        log_to_file("SUT verileri dosyası bulunamadı!")
        return None
    except Exception as e:
        log_to_file(f"SUT verileri okunamadı: {str(e)}")
        return None

def save_to_json(data):
    # JSON verilerini kaydet
    try:
        with open('sut_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        log_to_file(f"SUT verileri kaydedilemedi: {str(e)}")

def process_ek2a(df):
    """EK2A listesini işle"""
    result = []
    
    for _, row in df.iterrows():
        uzmanlik_dali = row['İşlem Adı'].strip()
        oh_kdv_haric = float(row['Özel Hastane'])
        oh_kdv_dahil = round(oh_kdv_haric * 1.1, 2)  # %10 KDV
        otm_kdv_haric = float(row['Tıp Merkezi'])
        otm_kdv_dahil = round(otm_kdv_haric * 1.1, 2)  # %10 KDV
        
        result.append({
            'uzmanlik_dali': uzmanlik_dali,
            'oh_kdv_haric': oh_kdv_haric,
            'oh_kdv_dahil': oh_kdv_dahil,
            'otm_kdv_haric': otm_kdv_haric,
            'otm_kdv_dahil': otm_kdv_dahil,
            'liste_turu': 'ek2a'
        })
    
    return result

def process_ek2b(df):
    """EK2B listesini işle"""
    result = []
    
    for _, row in df.iterrows():
        islem_kodu = str(row['SUT_KODU']).strip()
        kdv_haric = float(row['UCRET'])
        kdv_dahil = round(kdv_haric * 1.1, 2)  # %10 KDV
        
        result.append({
            'islem_kodu': islem_kodu,
            'kdv_haric_fiyat': kdv_haric,
            'kdv_dahil_fiyat': kdv_dahil,
            'liste_turu': 'ek2b'
        })
    
    return result

def process_ek2c(df):
    """EK2C listesini işle"""
    result = []
    
    for _, row in df.iterrows():
        islem_kodu = str(row['SUT_KODU']).strip()
        kdv_haric = float(row['UCRET'])
        kdv_dahil = round(kdv_haric * 1.1, 2)  # %10 KDV
        
        result.append({
            'islem_kodu': islem_kodu,
            'kdv_haric_fiyat': kdv_haric,
            'kdv_dahil_fiyat': kdv_dahil,
            'liste_turu': 'ek2c'
        })
    
    return result

@app.route('/update_prices', methods=['POST'])
def update_prices():
    try:
        excel_file = request.files['excel_file']
        hospital_type = request.form['hospital_type']
        price_type = request.form['price_type']
        
        if excel_file.filename == '':
            return jsonify({'success': False, 'error': 'Dosya seçilmedi'})
            
        result = update_excel_prices(excel_file, hospital_type, price_type)
        
        if result['success']:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': result.get('error', 'Bilinmeyen bir hata oluştu')})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/', methods=['GET', 'POST'])
def index():
    form = UpdateForm()
    
    if form.validate_on_submit():
        try:
            # Dosya kontrolü
            if not form.excel_file.data:
                flash('Lütfen bir Excel dosyası seçin.', 'error')
                return redirect(url_for('index'))
            
            file = form.excel_file.data
            filename = secure_filename(file.filename)
            log_to_file(f"Excel dosyası alındı: {filename}")
            
            # Excel dosyasını oku
            try:
                df = pd.read_excel(BytesIO(file.read()))
                log_to_file(f"Excel dosyası pandas ile okundu. Satır sayısı: {len(df)}")
                log_to_file(f"Sütunlar: {df.columns.tolist()}")
                file.seek(0)  # Dosya işaretçisini başa al
            except Exception as e:
                log_to_file(f"Excel okuma hatası: {str(e)}")
                flash('Excel dosyası okunamadı. Lütfen dosyanın formatını kontrol edin.', 'error')
                return redirect(url_for('index'))
            
            # Kolon indekslerini bul
            try:
                code_idx = int(form.code_column.data) if form.code_column.data.isdigit() else get_column_index(form.code_column.data.upper())
                desc_idx = int(form.description_column.data) if form.description_column.data.isdigit() else get_column_index(form.description_column.data.upper())
                price_idx = int(form.price_column.data) if form.price_column.data.isdigit() else get_column_index(form.price_column.data.upper())
                
                if code_idx is None or desc_idx is None or price_idx is None:
                    flash('Geçersiz kolon harfi. Lütfen A-Z arasında bir harf veya 1-99 arasında bir sayı girin.', 'error')
                    return redirect(url_for('index'))
                    
                log_to_file(f"Kolon indeksleri (1-tabanlı): Kod={code_idx}, Açıklama={desc_idx}, Fiyat={price_idx}")
                
                # İlk birkaç satırı kontrol et
                log_to_file("İlk 5 satır örnek veri:")
                for i in range(min(5, len(df))):
                    kod = df.iloc[i, code_idx-1] if code_idx-1 < len(df.columns) else 'HATA'  # 0-tabanlı indeks için -1
                    aciklama = df.iloc[i, desc_idx-1] if desc_idx-1 < len(df.columns) else 'HATA'  # 0-tabanlı indeks için -1
                    fiyat = df.iloc[i, price_idx-1] if price_idx-1 < len(df.columns) else 'HATA'  # 0-tabanlı indeks için -1
                    log_to_file(f"Satır {i+1}: Kod={kod}, Açıklama={aciklama}, Fiyat={fiyat}")
                    
                    # Liste türünü belirle
                    if i == 0:  # İlk satırda kod varsa liste türünü belirle
                        kod_str = str(kod)
                        if 'P520030' in kod_str:
                            liste_turu = 'ek2b'
                            log_to_file("Liste türü: EK-2B (520030 koduna göre)")
                        elif 'P530010' in kod_str:
                            liste_turu = 'ek2c'
                            log_to_file("Liste türü: EK-2C (530010 koduna göre)")
                        else:
                            liste_turu = 'ek2a'
                            log_to_file("Liste türü: EK-2A (varsayılan)")
                
            except Exception as e:
                log_to_file(f"Kolon indeksi hatası: {str(e)}")
                flash('Kolon bilgisi geçersiz. Lütfen A-Z arasında bir harf veya 1-99 arasında bir sayı girin.', 'error')
                return redirect(url_for('index'))
            
            # Başlık satırını bul ve veriyi hazırla
            header_row = find_header_row(df, code_idx-1, desc_idx-1, price_idx-1)  # 0-tabanlı indeks için -1
            if header_row > 0:
                df = df.iloc[header_row:]
                df = df.reset_index(drop=True)
                log_to_file(f"Başlık satırı bulundu: {header_row}. Veri yeniden düzenlendi.")
            
            # Excel'i güncelle
            output, updated_count, not_found_count = update_excel_from_json(
                file, filename, df, code_idx, desc_idx, price_idx,  # Orijinal 1-tabanlı indeksler
                form.hospital_type.data, form.price_type.data, [], []  # Boş liste ile çağır
            )
            
            if output:
                flash(f'Güncelleme başarılı! {updated_count} satır güncellendi, {not_found_count} satır için fiyat bulunamadı.', 'success')
                # Dosyayı indir
                return send_file(
                    output,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    as_attachment=True,
                    download_name=f"guncellenmis_{filename}"
                )
            else:
                flash('Dosya güncellenirken bir hata oluştu.', 'error')
                
        except Exception as e:
            log_to_file(f"Hata: {str(e)}")
            import traceback
            log_to_file(traceback.format_exc())
            flash('Bir hata oluştu: ' + str(e), 'error')
            
        return redirect(url_for('index'))
        
    return render_template('index.html', form=form)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    form = AdminForm()
    if form.validate_on_submit():
        if form.clear_data.data:  # Temizle butonuna basıldıysa
            try:
                # Boş JSON yapısını oluştur
                empty_data = {
                    'ek2a': {},
                    'ek2b': {},
                    'ek2c': {}
                }
                # JSON dosyasını temizle
                save_to_json(empty_data)
                flash('Tüm veriler başarıyla temizlendi.', 'success')
            except Exception as e:
                flash(f'Veriler temizlenirken bir hata oluştu: {str(e)}', 'error')
            return redirect(url_for('admin'))
            
        if form.sut_file.data:
            # Dosya seçildi mi kontrol et
            if not form.sut_file.data.filename:
                flash('Lütfen bir dosya seçin.', 'error')
                return redirect(url_for('admin'))
            
            # Dosya adını kontrol et
            filename = form.sut_file.data.filename
            if not (filename.startswith('EK-2A') or filename.startswith('EK-2B') or filename.startswith('EK-2C')):
                flash('Dosya adı EK-2A, EK-2B veya EK-2C ile başlamalıdır.', 'error')
                return redirect(url_for('admin'))
            
            try:
                # Geçici dosyayı kaydet
                temp_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
                form.sut_file.data.save(temp_path)
                
                # Excel dosyasını oku
                df = pd.read_excel(temp_path)
                
                # Debug için yazdır
                print("\nKolon isimleri:", df.columns.tolist(), flush=True)
                print("\n3. satır (index=2):", df.iloc[2].tolist(), flush=True)
                print("\n3. satır str:", [str(x) for x in df.iloc[2].tolist()], flush=True)
                
                # Dosya türüne göre işle
                if filename.startswith('EK-2A'):
                    data = process_ek2a(df)
                elif filename.startswith('EK-2B'):
                    data = process_ek2b(df)
                else:  # EK-2C
                    data = process_ek2c(df)
                
                if data:
                    # JSON dosyasını oku
                    json_data = read_and_process_sut_files()
                    if json_data is None:
                        json_data = {'ek2a': {}, 'ek2b': {}, 'ek2c': {}}
                    
                    # Güncel tarihi al
                    current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Dosya türüne göre güncelle
                    if filename.startswith('EK-2A'):
                        json_data['ek2a'][current_date] = data
                    elif filename.startswith('EK-2B'):
                        json_data['ek2b'][current_date] = data
                    else:  # EK-2C
                        json_data['ek2c'][current_date] = data
                    
                    # JSON'a kaydet
                    save_to_json(json_data)
                    flash('Veriler başarıyla güncellendi.', 'success')
                else:
                    flash('Veri işlenirken bir hata oluştu.', 'error')
                
                # Geçici dosyayı sil
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                
            except Exception as e:
                flash(f'Hata: {str(e)}', 'error')
                # Hata durumunda da geçici dosyayı silmeye çalış
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            
            return redirect(url_for('admin'))
    
    return render_template('admin.html', form=form)

if __name__ == '__main__':
    # Debug ve logging ayarları
    app.debug = True
    import sys
    import logging
    logging.basicConfig(filename='debug.log', level=logging.DEBUG,
                      format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Uygulamayı başlat
    app.run(host='0.0.0.0', port=5000)
