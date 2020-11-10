import os

class Config:
    SECRET_KEY = "derivative_map_alpha_"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False