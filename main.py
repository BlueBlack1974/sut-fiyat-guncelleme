from flask import Flask, render_template, redirect, url_for, flash, jsonify, send_file, after_this_request, request
from flask_wtf import FlaskForm
from wtforms import FileField, RadioField, SubmitField
from wtforms.validators import DataRequired
from werkzeug.utils import secure_filename
import os
import json
import shutil
import time
from datetime import datetime, timedelta
from io import BytesIO
import openpyxl

# Flask app configuration
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Form classes
class UpdateForm(FlaskForm):
    excel_file = FileField('Excel Dosyası', validators=[DataRequired()])
    hospital_type = RadioField('Hastane Türü',
                             choices=[('ozel_hastane', 'Özel Hastane'),
                                    ('ozel_tip_merkezi', 'Özel Tıp Merkezi')],
                             validators=[DataRequired()])
    submit = SubmitField('Güncelle')

class AdminForm(FlaskForm):
    submit = SubmitField('SUT Verilerini Güncelle')

# Helper functions
def read_and_process_sut_files():
    """SUT Excel dosyalarını oku ve işle"""
    try:
        data_dir = os.path.join(os.getcwd(), 'data')
        json_path = os.path.join(data_dir, 'sut_fiyatlari.json')
        
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    except Exception as e:
        print(f"Error reading SUT files: {str(e)}")
        return None

def save_to_json(data):
    """Verileri JSON dosyasına kaydet"""
    try:
        data_dir = os.path.join(os.getcwd(), 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        json_path = os.path.join(data_dir, 'sut_fiyatlari.json')
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return json_path
    except Exception as e:
        print(f"Error saving to JSON: {str(e)}")
        return None

def update_excel_from_json(excel_file, hospital_type):
    """Excel dosyasını JSON verilerine göre güncelle"""
    try:
        # JSON verilerini oku
        data_dir = os.path.join(os.getcwd(), 'data')
        json_path = os.path.join(data_dir, 'sut_fiyatlari.json')
        
        if not os.path.exists(json_path):
            return None
            
        with open(json_path, 'r', encoding='utf-8') as f:
            sut_data = json.load(f)
        
        # Excel'i yükle
        workbook = openpyxl.load_workbook(excel_file)
        sheet = workbook.active
        
        # Başlık satırını bul
        header_row = None
        for row in sheet.iter_rows(min_row=1, max_row=10):
            for cell in row:
                if cell.value and isinstance(cell.value, str) and "SUT" in cell.value.upper():
                    header_row = cell.row
                    break
            if header_row:
                break
                
        if not header_row:
            return None
            
        # Sütun başlıklarını bul
        headers = {}
        for cell in sheet[header_row]:
            if cell.value:
                value = str(cell.value).strip().lower()
                if "sut" in value:
                    headers['sut_kodu'] = cell.column_letter
                elif "fiyat" in value:
                    headers['fiyat'] = cell.column_letter
                    
        if 'sut_kodu' not in headers or 'fiyat' not in headers:
            return None
            
        # Fiyatları güncelle
        for row in sheet.iter_rows(min_row=header_row + 1):
            sut_kodu = row[openpyxl.utils.column_index_from_string(headers['sut_kodu']) - 1].value
            if sut_kodu:
                sut_kodu = str(sut_kodu).strip()
                if sut_kodu in sut_data:
                    fiyat_cell = row[openpyxl.utils.column_index_from_string(headers['fiyat']) - 1]
                    if hospital_type == 'ozel_hastane':
                        fiyat_cell.value = float(sut_data[sut_kodu]) * 1.1
                    else:  # ozel_tip_merkezi
                        fiyat_cell.value = float(sut_data[sut_kodu])
                        
        # Sonucu BytesIO'ya kaydet
        output = BytesIO()
        workbook.save(output)
        return output
        
    except Exception as e:
        print(f"Error updating Excel: {str(e)}")
        return None

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
    # Her istek öncesi eski dosyaları temizle
    cleanup_old_files()
    
    form = UpdateForm()
    if form.validate_on_submit():
        try:
            # Dosya yüklendi mi kontrol et
            if not form.excel_file.data:
                flash('Lütfen bir Excel dosyası seçin!', 'error')
                return redirect(url_for('index'))

            file = form.excel_file.data
            filename = secure_filename(file.filename)
            
            # Dosya uzantısını kontrol et
            if not filename.endswith('.xlsx'):
                flash('Lütfen geçerli bir Excel dosyası seçin! (.xlsx)', 'error')
                return redirect(url_for('index'))
            
            # Dosya erişilebilir mi kontrol et
            if not check_file_access(file.stream):
                flash('Excel dosyası açılamıyor veya erişim engellendi!', 'error')
                return redirect(url_for('index'))
            
            # Dosyayı başa sar
            file.stream.seek(0)
            
            # Excel'i güncelle
            output = update_excel_from_json(file.stream, form.hospital_type.data)
            
            if output:
                # BytesIO'yu başa sar
                output.seek(0)
                
                # Geçici dosya oluştur
                temp_dir = os.path.join(os.getcwd(), 'temp')
                os.makedirs(temp_dir, exist_ok=True)
                
                temp_filename = f"updated_{filename}"
                temp_path = os.path.join(temp_dir, temp_filename)
                
                # BytesIO'yu geçici dosyaya kaydet
                with open(temp_path, 'wb') as f:
                    f.write(output.getvalue())
                
                # Dosyayı kullanıcıya gönder
                @after_this_request
                def cleanup(response):
                    # Dosyayı 1 saniye sonra sil
                    delete_file_after_delay(temp_path)
                    return response
                
                return send_file(
                    temp_path,
                    as_attachment=True,
                    download_name=f"guncellenmis_{filename}",
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
            else:
                flash('Excel dosyası güncellenirken bir hata oluştu!', 'error')
                
        except Exception as e:
            flash(f"Hata: {str(e)}", 'error')
            
    return render_template('index.html', form=form)

if __name__ == '__main__':
    app.run(debug=True)
