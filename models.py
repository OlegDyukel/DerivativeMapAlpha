from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
# from werkzeug.security import generate_password_hash, check_password_hash


db = SQLAlchemy()


class Underlying(db.Model):
    __tablename__ = "underlyings"

    id = db.Column(db.Integer, primary_key=True)
    underlying = db.Column(db.String(), nullable=False, unique=True)
    name = db.Column(db.String())
    section_id = db.Column(db.Integer)
    section = db.Column(db.String())
    quote = db.Column(db.String())
    exp_clearing = db.Column(db.String())
    exp_type = db.Column(db.String())
    web_page = db.Column(db.Text)
    date_created = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Cell(db.Model):
    __tablename__ = "cells"

    id = db.Column(db.Integer, primary_key=True)
    underlying = db.Column(db.String(), nullable=False)
    year_month = db.Column(db.String(), nullable=False)
    color = db.Column(db.String())
    label = db.Column(db.String())
    date_created = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Future(db.Model):
    __tablename__ = "futures"

    id = db.Column(db.Integer, primary_key=True)
    secid = db.Column(db.String())
    shortname = db.Column(db.String())
    lasttradedate = db.Column(db.DateTime)
    assetcode = db.Column(db.String())
    prevopenposition = db.Column(db.BigInteger)
    prevsettleprice = db.Column(db.Float)
    oi_rub = db.Column(db.Float)
    oi_percentage = db.Column(db.Float)
    lasttrademonth = db.Column(db.String())
    date_created = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Option(db.Model):
    __tablename__ = "options"

    id = db.Column(db.Integer, primary_key=True)
    secid = db.Column(db.String())
    shortname = db.Column(db.String())
    lasttradedate = db.Column(db.DateTime)
    assetcode = db.Column(db.String())
    prevopenposition = db.Column(db.BigInteger)
    prevsettleprice = db.Column(db.Float)
    oi_rub = db.Column(db.Float)
    oi_percentage = db.Column(db.Float)
    lasttrademonth = db.Column(db.String())
    date_created = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    underlying_future = db.Column(db.String())


class FeedBack(db.Model):
    __tablename__ = "feed_backs"

    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String())
    user_email = db.Column(db.String())
    user_phone = db.Column(db.String())
    user_text = db.Column(db.Text, nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class AdminUser(db.Model):
    __tablename__ = "admin_users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(), nullable=False, unique=True)
    password_hash = db.Column(db.String(128), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Edition(db.Model):
    __tablename__ = "editions"

    id = db.Column(db.Integer, primary_key=True)
    table = db.Column(db.String(), nullable=False, unique=True)
    edition = db.Column(db.BigInteger)
    date_created = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

