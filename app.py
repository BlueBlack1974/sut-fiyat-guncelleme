from flask import Flask, render_template, redirect, url_for, flash, jsonify, send_file, after_this_request
from app.forms import UpdateForm, AdminForm
from app.models import read_and_process_sut_files, save_to_json, update_excel_from_json
from werkzeug.utils import secure_filename
import os
import shutil
import time
from datetime import datetime, timedelta
from io import BytesIO
import openpyxl

app = Flask(__name__, 
    template_folder='app/templates',
    static_folder='app/static'
)

# Config
app.config.from_object('config.Config')

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

# Uygulama kapanırken temizleme işlemini yap
import atexit
atexit.register(cleanup_old_files)

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
