from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField
from wtforms.validators import InputRequired, Email, DataRequired, Length, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash


class ClientFeedBack(FlaskForm):
    client_name = StringField("Ваше имя (опционально)")
    client_email = StringField("Электропочта (опционально)")
    client_phone = StringField("Телефон (опционально)")
    client_text = TextAreaField("Ваши идеи", [InputRequired(message="Как нам стать лучше?")])