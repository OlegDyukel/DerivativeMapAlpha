import requests
import pandas as pd
import numpy as np
import re


def get_colors():
    return {0: "#f8f9fa", 1: "#e9ecef", 2: "#dee2e6", 3: "#ced4da", 4: "#adb5bd", 5: "#868e96"}


def get_option_series_name(s):
    st = re.sub("[CP]A[\d\.\-]+$", "", s)
    return st


def get_option_underlying(option_name):
    st = re.split("M\d{6}", option_name)
    return st[0]


def get_year_month(date):
    return date.strftime("%Y %b")


def get_list_months(df_fut):
    lst_months = []
    for dt in pd.period_range(start=df_fut["lasttradedate"].min(),
                              end=df_fut["lasttradedate"].max(),
                              freq='M'):
        lst_months.append(get_year_month(dt))

    return lst_months


def round_up_log(number, base, n_groups):
    return int(np.log(number + 1.0)/(np.log(base + 1.0001)/(n_groups-1)) - 0.00001) \
            + (np.log(number + 1.0)%(np.log(base + 1.0001)/(n_groups-1))>0)


def short_number(number):
    try:
        d = {0: "", 1: "K", 2: "M", 3: "B"}
        power = (len(str(int(number))) - 1)//3
        devisor = 10**(3*power)
        if number/devisor < 10 and number >= 10:
            modificated_number = round(number/devisor, 1)
        else:
            modificated_number = int(round(number/devisor, 0))
        return "{}{}".format(modificated_number, d[power])
    except ValueError:
        return "0"


def iss_urls():
    url_basic_futures = "https://iss.moex.com/iss/engines/futures/markets/forts/securities.json"
    url_basic_options = "https://iss.moex.com/iss/engines/futures/markets/options/securities.json"
    columns_input = ["SECID", "SHORTNAME", "LASTTRADEDATE", "ASSETCODE",
                     "PREVOPENPOSITION", "PREVSETTLEPRICE", "MINSTEP", "STEPPRICE"]

    return {"query_futures_instruments": url_basic_futures + \
                                "?iss.only=securities&securities.columns={}".format(','.join(columns_input)),
    "query_futures_edition": url_basic_futures + "?iss.only=dataversion&dataversion.columns=seqnum",
    "query_options_instruments": url_basic_options + \
                                "?iss.only=securities&securities.columns={}".format(','.join(columns_input)),
    "query_options_edition": url_basic_options + "?iss.only=dataversion&dataversion.columns=seqnum"}



def get_data(exp_date=None):
    ######### futures data
    r_fut = requests.get(iss_urls()["query_futures_instruments"])
    data_fut = r_fut.json()["securities"]["data"]
    columns_fut = r_fut.json()["securities"]["columns"]
    df_fut = pd.DataFrame(data_fut, columns=columns_fut)

    ####### futures edition #####
    r_seqnum_fut = requests.get(iss_urls()["query_futures_edition"])
    seqnum_fut = r_seqnum_fut.json()["dataversion"]["data"][0][0]

    ######### options data
    r_opt = requests.get(iss_urls()["query_options_instruments"])
    data_opt = r_opt.json()["securities"]["data"]
    columns_opt = r_opt.json()["securities"]["columns"]
    df_opt_raw = pd.DataFrame(data_opt, columns=columns_opt)

    ####### options edition #####
    r_seqnum_opt = requests.get(iss_urls()["query_options_edition"])
    seqnum_opt = r_seqnum_opt.json()["dataversion"]["data"][0][0]

    # deleting NaN values
    df_fut = df_fut[-df_fut["PREVOPENPOSITION"].isnull()]
    df_opt_raw = df_opt_raw[-df_opt_raw["PREVOPENPOSITION"].isnull()]

    # getting underlying
    df_opt_raw["UNDERLYING"] = df_opt_raw["SHORTNAME"].apply(get_option_underlying)

    # getting short option names = cutting strikes and types
    df_opt_raw["SHORTNAME"] = df_opt_raw["SHORTNAME"].apply(get_option_series_name)

    # getting STEPPRICE param for options from futures
    df_opt_raw = df_opt_raw.merge(df_fut[["SHORTNAME", "STEPPRICE"]],
                                  how="left", left_on="UNDERLYING", right_on="SHORTNAME", suffixes=["", "_y"])

    # calc OI_RUB
    df_fut["OI_RUB"] = df_fut["PREVOPENPOSITION"] * df_fut["PREVSETTLEPRICE"] * df_fut["STEPPRICE"] / df_fut["MINSTEP"]
    df_opt_raw["OI_RUB"] = df_opt_raw["PREVOPENPOSITION"] * df_opt_raw["PREVSETTLEPRICE"] * df_opt_raw["STEPPRICE"] / \
                           df_opt_raw["MINSTEP"]

    # filtering, sorting and grouping
    if exp_date:
        df_fut = df_fut[df_fut["LASTTRADEDATE"] == exp_date].sort_values(by=["PREVOPENPOSITION"], ascending=False)
        df_opt = df_opt_raw[df_opt_raw["LASTTRADEDATE"] == exp_date].groupby(
            ["SHORTNAME", "LASTTRADEDATE", "ASSETCODE", "UNDERLYING"]).agg(
            {"PREVOPENPOSITION": "sum", "OI_RUB": "sum", "SECID": "max",
             "PREVSETTLEPRICE": "mean"}).reset_index().sort_values(by=["OI_RUB"], ascending=False)
    else:
        df_fut = df_fut.sort_values(by=["PREVOPENPOSITION"], ascending=False)
        df_opt = df_opt_raw.groupby(["SHORTNAME", "LASTTRADEDATE", "ASSETCODE", "UNDERLYING"]).agg(
            {"PREVOPENPOSITION": "sum", "OI_RUB": "sum", "SECID": "max",
             "PREVSETTLEPRICE": "mean"}).reset_index().sort_values(by=["OI_RUB"], ascending=False)

    # OI_PERCENTAGE(sum_undrl = 100%)
    df_fut["OI_PERCENTAGE"] = 100 * df_fut[["PREVOPENPOSITION"]] / df_fut[["ASSETCODE", "PREVOPENPOSITION"]].groupby(
        "ASSETCODE").transform("sum")
    df_opt["OI_PERCENTAGE"] = 100 * df_opt[["PREVOPENPOSITION"]] / df_opt[["ASSETCODE", "PREVOPENPOSITION"]].groupby(
        "ASSETCODE").transform("sum")

    # transforming date type
    df_fut["LASTTRADEDATE"] = pd.to_datetime(df_fut["LASTTRADEDATE"])
    df_opt["LASTTRADEDATE"] = pd.to_datetime(df_opt["LASTTRADEDATE"])

    df_fut["LASTTRADEMONTH"] = df_fut["LASTTRADEDATE"].apply(get_year_month)
    df_opt["LASTTRADEMONTH"] = df_opt["LASTTRADEDATE"].apply(get_year_month)

    # OI_contracts to int
    df_fut["PREVOPENPOSITION"] = df_fut["PREVOPENPOSITION"].apply(int)
    df_opt["PREVOPENPOSITION"] = df_opt["PREVOPENPOSITION"].apply(int)

    columns_output_fut = ["SECID", "SHORTNAME", "LASTTRADEDATE", "ASSETCODE", "PREVOPENPOSITION",
                          "PREVSETTLEPRICE", "OI_RUB", "OI_PERCENTAGE", "LASTTRADEMONTH"]
    columns_output_opt = ["SECID", "SHORTNAME", "LASTTRADEDATE", "ASSETCODE", "PREVOPENPOSITION",
                          "PREVSETTLEPRICE", "OI_RUB", "OI_PERCENTAGE", "LASTTRADEMONTH", "UNDERLYING"]


    return {"futures": df_fut[columns_output_fut],
            "options": df_opt[columns_output_opt],
            "future_edition": seqnum_fut,
            "option_edition": seqnum_opt}


def get_dict_matrix(df_cell, df_fut, df_opt):
    # getting columns and rows
    underlying_lst = df_cell['underlying'].unique()
    date_lst = df_cell['year_month'].unique()

    # initializing table
    d = {}
    columns_fut = ["secid", "shortname", "lasttradedate", "prevopenposition", "oi_rub", "oi_percentage"]
    columns_opt = ["secid", "shortname", "lasttradedate", "prevopenposition", "oi_rub", "oi_percentage", "underlying_future"]

    # filling cells
    for row in underlying_lst:
        d[row] = {}
        for col in date_lst:
            d[row][col] = {"cell_name": '',
                                "cell_params": {},
                                "futures": [],
                                "options": []}

    dict_cell = df_cell.set_index(['underlying', 'year_month']).to_dict(orient='index')

    for key, value in dict_cell.items():
        lst_fut = df_fut[(df_fut["assetcode"] == key[0]) & (df_fut["lasttrademonth"] == key[1])][columns_fut].to_dict(orient='records')
        lst_opt = df_opt[(df_opt["assetcode"] == key[0]) & (df_opt["lasttrademonth"] == key[1])][columns_opt].to_dict(orient='records')

        d[key[0]][key[1]] = {
                "cell_name": "{}{}".format(key[0], key[1].replace(" ", "")),
                "cell_params": value,
                "futures": lst_fut,
                "options": lst_opt}
    return d


def get_dict_section_undrl(df_undrl, df_fut):
    dict_undrl_section = df_undrl[['section', 'section_id']] \
        .sort_values(by=['section_id']).to_dict()['section']
    dict_section_undrl = {}

    for value in dict_undrl_section.values():
        dict_section_undrl[value] = []

    index = df_fut[['assetcode', 'oi_rub']].groupby('assetcode').sum()\
            .sort_values('oi_rub', ascending=False).index

    for undrl in index:
        if dict_undrl_section[undrl] in dict_section_undrl:
            dict_section_undrl[dict_undrl_section[undrl]].append(undrl)
        else:
            dict_section_undrl[dict_undrl_section[undrl]] = [undrl]

    return dict_section_undrl