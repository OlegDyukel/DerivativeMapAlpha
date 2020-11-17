import requests
import pandas as pd


from datetime import datetime
from sqlalchemy import func
from flask import Flask, render_template, request, redirect, url_for
from flask_migrate import Migrate
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_wtf.csrf import CSRFProtect


from models import db, Underlying, Cell, Future, Option, FeedBack, AdminUser, Edition
from forms import ClientFeedBack
from functions import get_data, get_dict_matrix, get_colors, iss_urls, get_list_months, round_up_log
from functions import get_dict_section_undrl
from config import Config


app = Flask(__name__)

app.config.from_object(Config)
db.init_app(app)
migrate = Migrate(app, db)
admin = Admin(app)
csrf = CSRFProtect(app)


class MyUserView(ModelView):
    # Настройка общего списка
    column_exclude_list = ['password_hash']  # убрать из списка одно или несколько полей


# admin.add_view(MyUserView(Underlying, db.session))
# admin.add_view(MyUserView(Edition, db.session))
# admin.add_view(MyUserView(FeedBack, db.session))


def update_futopt_tables(db_future_nrows, db_option_nrows):
    text_errors = []
    data = get_data()

    if 0.5*db_future_nrows < len(data["futures"]):
        # clear table with staled data
        db.session.query(Future).delete()

        # write fresh data
        for row in data["futures"].drop_duplicates().iterrows():
            future = Future(secid=row[1].SECID, shortname=row[1].SHORTNAME, lasttradedate=row[1].LASTTRADEDATE,
                            assetcode=row[1].ASSETCODE, prevopenposition=row[1].PREVOPENPOSITION,
                            prevsettleprice=row[1].PREVSETTLEPRICE, oi_rub=row[1].OI_RUB,
                            oi_percentage=row[1].OI_PERCENTAGE, lasttrademonth=row[1].LASTTRADEMONTH,
                            date_created=datetime.utcnow())
            db.session.add(future)

        try:
            editions = db.session.query(Edition).filter(Edition.table == "futures").first()
            editions.edition = data["future_edition"]
            editions.date_created = datetime.utcnow()
        except AttributeError:
            editions = Edition(table="futures", edition=data["future_edition"], date_created=datetime.utcnow())
            db.session.add(editions)

        db.session.commit()
    else:
        text_errors.append("a new data of futures has too little rows")


    if 0.5*db_option_nrows < len(data["options"]):
        # clear table with staled data
        db.session.query(Option).delete()

        # write fresh data
        for row in data["options"].drop_duplicates().iterrows():
            option = Option(secid=row[1].SECID, shortname=row[1].SHORTNAME, lasttradedate=row[1].LASTTRADEDATE,
                            assetcode=row[1].ASSETCODE, prevopenposition=row[1].PREVOPENPOSITION,
                            prevsettleprice=row[1].PREVSETTLEPRICE, oi_rub=row[1].OI_RUB,
                            oi_percentage=row[1].OI_PERCENTAGE, lasttrademonth=row[1].LASTTRADEMONTH,
                            underlying_future=row[1].UNDERLYING, date_created=datetime.utcnow())
            db.session.add(option)

        try:
            editions = db.session.query(Edition).filter(Edition.table == "options").first()
            editions.edition = data["option_edition"]
            editions.date_created = datetime.utcnow()
        except AttributeError:
            editions = Edition(table="options", edition=data["option_edition"], date_created=datetime.utcnow())
            db.session.add(editions)

        db.session.commit()
    else:
        text_errors.append("a new data of options has too little rows")

    df_fut = pd.read_sql(db.session.query(Future).statement, db.session.bind)
    df_opt = pd.read_sql(db.session.query(Option).statement, db.session.bind)
    return [df_fut, df_opt, text_errors]


def update_underlying(df_fut):
    text_errors = []
    df_undrl = pd.read_sql(db.session.query(Underlying).statement, db.session.bind).set_index('underlying')
    new_set = set(df_fut['assetcode']).difference(set(df_undrl.index))

    if new_set:
        id = int(df_undrl['id'].max())
        for i in new_set:
            id += 1
            db_undrl = Underlying(id=id, underlying=i, name='', section_id=0, section='Новые',
                                  quote='', exp_clearing='', exp_type='', web_page='',
                                  date_created=datetime.utcnow())
            db.session.add(db_undrl)

        db.session.commit()

    df_undrl = pd.read_sql(db.session.query(Underlying).statement, db.session.bind).set_index('underlying')

    return df_undrl


def update_matrix(df_fut, df_opt, df_undrl):
    # combining tables fut and opt
    df_fut['type'] = 'F'
    df_opt['type'] = 'O'
    df_futopt_grouped = pd.concat([df_fut, df_opt]).groupby(["lasttrademonth", "assetcode"])

    # cell - max OI_RUB for coloring the cell
    cell_max_OI_rub = df_futopt_grouped['oi_rub'].sum().max()
    d_colors = get_colors()
    n_colors = len(d_colors)

    # cleaning cells table
    db.session.query(Cell).delete()

    # filling cells
    for name, group in df_futopt_grouped:
        cell_OI_rub = group['oi_rub'].sum()
        cell_type = set(group['type'].unique())
        db_cell = Cell(underlying=name[1], year_month=name[0],
                       color=d_colors[round_up_log(cell_OI_rub, cell_max_OI_rub, n_colors)],
                       label=" ".join(sorted([e for e in cell_type])),
                       date_created=datetime.utcnow())
        db.session.add(db_cell)

    db.session.commit()
    return 'd'


@app.route("/", methods=["GET"])
def index():
    # инициализация датафреймов
    df_fut = pd.DataFrame()
    df_opt = pd.DataFrame()
    df_undrl = pd.DataFrame()

    # грубо проверяем что в БД консистентные данные. проверка по кол-ву записей (50 записей для фьючей)
    db_future_nrows = db.session.query(Future).count()
    db_option_nrows = db.session.query(Option).count()
    if db_future_nrows < 100 or db_option_nrows < 50:
        df_fut, df_opt, _ = update_futopt_tables(db_future_nrows, db_option_nrows)
        df_undrl = update_underlying(df_fut)
        update_matrix(df_fut, df_opt, df_undrl)

    # во-вторых проверяем совпадение даты сегодня и даты обновления таблицы
    try:
        db_future_date = db.session.query(func.max(Future.date_created)).first()[0].strftime("%Y-%m-%d")
        db_option_date = db.session.query(func.max(Option.date_created)).first()[0].strftime("%Y-%m-%d")
    except AttributeError:
        db_future_date = "1999-09-19"
        db_option_date = "1999-09-19"
    current_date = datetime.utcnow().strftime("%Y-%m-%d")

    if db_future_date != current_date or db_option_date != current_date:
        # далее проверяем версионность данных - в выходные даты могут не совпадать, но в источнике также не обновл
        db_future_edition = db.session.query(Edition).filter(Edition.table == "futures").first().edition
        db_option_edition = db.session.query(Edition).filter(Edition.table == "options").first().edition
        iss_future_edition = requests.get(iss_urls()["query_futures_edition"]).json()["dataversion"]["data"][0][0]
        iss_option_edition = requests.get(iss_urls()["query_options_edition"]).json()["dataversion"]["data"][0][0]
        if db_future_edition != iss_future_edition or db_option_edition != iss_option_edition:
            df_fut, df_opt, _ = update_futopt_tables(db_future_nrows, db_option_nrows)
            df_undrl = update_underlying(df_fut)
            update_matrix(df_fut, df_opt, df_undrl)

    # запрашиваем данные если не получили их ранее, когда обновляли базы данных
    if df_fut.empty:
        df_fut = pd.read_sql(db.session.query(Future).statement, db.session.bind)
    if df_opt.empty:
        df_opt = pd.read_sql(db.session.query(Option).statement, db.session.bind)
    if df_undrl.empty:
        df_undrl = pd.read_sql(db.session.query(Underlying).statement, db.session.bind)\
            .set_index('underlying')
    df_cell = pd.read_sql(db.session.query(Cell).statement, db.session.bind)

    return render_template("table.html",
                           colors=get_colors(),
                           dict_section=get_dict_section_undrl(df_undrl, df_fut),
                           dict_undrl=df_undrl.to_dict(orient='index'),
                           lst_months=get_list_months(df_fut),
                           dict_matrix=get_dict_matrix(df_cell, df_fut, df_opt),
                           time_upd=current_date)


@app.route("/feedback/", methods=["GET", "POST"])
def feedback():
    form = ClientFeedBack()

    if request.method == 'POST':
        input_name = form.client_name.data
        input_email = form.client_email.data
        input_phone = form.client_phone.data
        input_text = form.client_text.data

        db_feedback = FeedBack(user_name=input_name, user_email=input_email, user_phone=input_phone,
                              user_text=input_text, date_created=datetime.utcnow())

        db.session.add(db_feedback)
        db.session.commit()
        return redirect(url_for("confirmed_feedback"))

    return render_template("feedback.html", form=form)


@app.route("/confirmed_feedback/", methods=["GET"])
def confirmed_feedback():
    return render_template("confirmed_feedback.html")


@app.route("/donate/", methods=["GET"])
def donate():
    return render_template("donate.html")


if __name__ == "__main__":
    app.run()
