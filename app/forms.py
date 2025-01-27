from flask_wtf import FlaskForm
from wtforms import FileField, StringField, RadioField, SubmitField
from wtforms.validators import DataRequired
from flask_wtf.file import FileRequired, FileAllowed

class AdminForm(FlaskForm):
    sut_file = FileField('SUT Dosyası Yükle', validators=[DataRequired()])
    submit = SubmitField('Yükle')

class UpdateForm(FlaskForm):
    excel_file = FileField('Excel Dosyası', validators=[
        FileRequired(),
        FileAllowed(['xlsx'], 'Sadece Excel dosyaları!')
    ])
    
    code_column = StringField('İşlem Kodu Kolonu', 
        validators=[DataRequired()]
    )
    
    description_column = StringField('İşlem Açıklaması Kolonu',
        validators=[DataRequired()]
    )
    
    price_column = StringField('Fiyat Kolonu',
        validators=[DataRequired()]
    )
    
    price_type = RadioField('Fiyat Türü',
        choices=[
            ('dahil', 'KDV Dahil'),
            ('haric', 'KDV Hariç')
        ],
        default='dahil'
    )

    hospital_type = RadioField('Hastane Türü',
        choices=[
            ('oh', 'Özel Hastane'),
            ('otm', 'Özel Tıp Merkezi')
        ],
        default='oh'
    )
    
    submit = SubmitField('Güncelle')