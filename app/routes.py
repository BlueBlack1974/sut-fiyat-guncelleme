from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, send_file, after_this_request
from app.forms import UpdateForm, AdminForm
from app.models import read_and_process_sut_files, save_to_json, update_excel_from_json
from werkzeug.utils import secure_filename
import os
import shutil
import time
from datetime import datetime, timedelta
from io import BytesIO
import openpyxl

main = Blueprint('main', __name__)

def cleanup_old_files():
    """1 saatten eski geçici dosyaları temizle"""
    temp_dir = os.path.join(os.getcwd(), 'temp')
    if not os.path.exists(temp_dir):
        return
        
    try:
        current_time = datetime.now()
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            try:
                # Dosya oluşturulma zamanını al
                file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                # 1 saatten eski dosyaları sil
                if current_time - file_time > timedelta(hours=1):
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        print(f"Eski dosya silinirken hata: {str(e)}")
            except Exception as e:
                print(f"Dosya zamanı alınırken hata: {str(e)}")
    except Exception as e:
        print(f"Temp klasörü temizlenirken hata: {str(e)}")

def delete_file_after_delay(file_path, delay=1):
    """Belirtilen süre sonra dosyayı sil"""
    def delete_file():
        try:
            time.sleep(delay)  # Belirtilen süre kadar bekle
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Dosya silinirken hata: {str(e)}")
    
    return delete_file

def check_file_access(file_stream):
    """Excel dosyasının erişilebilir olup olmadığını kontrol et"""
    try:
        # Dosyayı test amaçlı aç
        workbook = openpyxl.load_workbook(file_stream)
        workbook.close()
        return True
    except PermissionError:
        return False
    except Exception as e:
        print(f"Dosya kontrolü sırasında hata: {str(e)}")
        return False

# Uygulama kapanırken temizleme işlemini yap
import atexit
atexit.register(cleanup_old_files)

@main.route('/admin', methods=['GET', 'POST'])
def admin():
    form = AdminForm()
    if form.validate_on_submit():
        try:
            uploaded_file = form.sut_file.data
            filename = uploaded_file.filename.lower()
            
            # Dosya türü kontrolü
            if not any(x in filename for x in ['ek-2a', 'ek-2b', 'ek-2c']):
                flash("Geçersiz dosya! Lütfen EK-2A/B/C dosyası yükleyin.", 'error')
                return redirect(url_for('main.admin'))
            
            # Dosyayı geçici olarak bellekte tut
            file_stream = BytesIO(uploaded_file.read())
            
            # İşle ve JSON'a kaydet
            data = read_and_process_sut_files(file_stream)
            liste_turu = 'ek2a' if 'ek-2a' in filename else 'ek2b' if 'ek-2b' in filename else 'ek2c'
            save_to_json(data, liste_turu)
            
            flash(f"{liste_turu.upper()} başarıyla güncellendi!", 'success')
            return redirect(url_for('main.admin'))
            
        except Exception as e:
            flash(f"Hata: {str(e)}", 'error')
    return render_template('admin.html', form=form)

@main.route('/', methods=['GET', 'POST'])
def index():
    # Her istek öncesi eski dosyaları temizle
    cleanup_old_files()
    
    form = UpdateForm()
    if form.validate_on_submit():
        try:
            # Form verilerini al
            file = form.excel_file.data
            code_column = form.code_column.data.upper()
            description_column = form.description_column.data.upper()
            price_column = form.price_column.data.upper()
            price_type = form.price_type.data
            hospital_type = form.hospital_type.data
            
            # Excel dosyasını güncelle
            result = update_excel_from_json(
                file, 
                code_column, 
                description_column, 
                price_column, 
                price_type,
                hospital_type
            )
            
            if result['success'] and result['file_stream']:
                # Dosya adını hazırla
                original_filename = secure_filename(file.filename)
                base_name = os.path.splitext(original_filename)[0]
                extension = os.path.splitext(original_filename)[1]
                new_filename = f"{base_name}_guncel{extension}"
                
                # Güncellenmiş dosyayı gönder
                response = send_file(
                    result['file_stream'],
                    as_attachment=True,
                    download_name=new_filename,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                
                # İstatistikleri header'a ekle
                response.headers['X-Total-Rows'] = str(result['total_rows'])
                response.headers['X-Updated-Rows'] = str(result['updated_rows'])
                response.headers['X-Not-Found-Rows'] = str(result['not_found_rows'])
                
                return response
            else:
                return jsonify({
                    'success': False,
                    'message': result['message'],
                    'total_rows': result['total_rows'],
                    'updated_rows': result['updated_rows'],
                    'not_found_rows': result['not_found_rows']
                })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Hata oluştu: {str(e)}',
                'total_rows': 0,
                'updated_rows': 0,
                'not_found_rows': 0
            })
            
    return render_template('index.html', form=form)