
from flask import Flask
from flask import render_template
from flask import request       # POST GET するなら必要
from flask import redirect
from flask import url_for

from sqlalchemy import *
from sqlalchemy.orm import *
from sqlalchemy.ext.declarative import declarative_base

import sqlite3
import glob
import os

import configparser
from datetime import datetime


Base = declarative_base()

app = Flask(__name__)

INI_PATH = "./info.ini"


class BBS_Thread_Body(Base):
    __tablename__ = "bbs_thread"

    no = Column(Integer, primary_key=True)
    msg = Column(String(255), default=" ")
    time_stamp = Column(String(255), default=" ")

    # 書き込みの状態　0..なし 1...あり  2...削除済み
    stat = Column(Integer, default=0)

    pwd = Column(String(255), default="")

    def __repr__(selef):
        return "<BBS Thread body(no='%s', msg='%s',time='%s')>" % (self.no, self.msg, self.time_stamp)


def make_bbs_name(num):
    return "bbs_" + str(num).zfill(8)


def make_ini_name(num):
    base_name = make_bbs_name(num)
    return "./bbs/"+base_name+".ini"


def make_db_name(num):
    base_name = make_bbs_name(num)
    return "./bbs/"+base_name+".db"


def make_db_connection(num):
    return "sqlite:///" + make_db_name(num)


def get_bbs_header():
    value_list = []
   # BBSヘッダの データベース確認
    for f in glob.glob("./bbs/*.ini"):
        # ヘッダから情報チェック
        config = configparser.ConfigParser()
        config.read(f)
        value_list.append([
            config.get("THREAD", "no"),
            config.get("THREAD", "title"),
        ])
    return value_list


# データベース削除
def delete_thread_data(num):
    info = get_thread_info(num)
    try:
        os.remove(info["ini"])
    except PermissionError:
        pass

    try:
        os.remove(info["db"])
    except PermissionError:
        pass

# スレデータ用意


def get_thread_data(num):
    value_list = []
    info = get_thread_info(num)

    if info["isExist"] == True:
        # データベース準備
        engine = create_engine(info["db_connect"])
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        res = session.query(BBS_Thread_Body).all()
        for v in res:
            value_list.append([v.no, v.msg, v.time_stamp, v.stat])

    return value_list


# スレ番号からスレッドタイトルとか情報取得
def get_thread_info(num):

    ini_name = make_ini_name(num)
    db_name = make_db_name(num)
    db_connect = make_db_connection(num)
    title = ""
    no = 0
    isExist = False

    if os.path.exists(ini_name) == True:

        config = configparser.ConfigParser()
        config.read(ini_name)
        title = config.get("THREAD", "title")
        no = config.get("THREAD", "no")
        pwd = config.get("THREAD", "pwd")
        isExist = True

    return {"isExist": isExist, "title": title,  "db": db_name, "db_connect": db_connect,  "ini": ini_name, "pwd": pwd}

# スレ表示
@app.route('/view/<name>', methods=['POST'])
def thread_view_02(name=None):

    thread_no = int(name)
    info = get_thread_info(thread_no)

    if info["isExist"] == False:
        return render_template('not_found.html')

    # レス入力がある場合
    if request.method == "POST":
        # データベース準備
        if info["isExist"] == True:
            engine = create_engine(info["db_connect"])
            Base.metadata.create_all(engine)
            Session = sessionmaker(bind=engine)
            session = Session()

            res = request.form["res"]
            pwd = request.form["pwd"]
            t_stamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            session.add(BBS_Thread_Body(
                msg=res, time_stamp=t_stamp, stat=1, pwd=pwd))
            session.commit()

    return redirect(url_for("thread_view", name=name))


# スレ表示
@app.route('/view/<name>')
def thread_view(name=None):

    thread_no = int(name)
    value_list = get_thread_data(thread_no)
    info = get_thread_info(thread_no)

    if len(value_list) == 0 or info["isExist"] == False:
        return render_template('not_found.html')

    return render_template('view.html', value_list=value_list, title=info["title"], thread_no=thread_no)


# スレ削除
@app.route('/delete_thread')
def delete_thread():

    value_list = get_bbs_header()
    return render_template("delete_thread.html", value_list=value_list)


# スレ削除
@app.route('/delete_thread',  methods=['POST'])
def delete_thread_02():

    if request.method == "POST":
        checks = request.form.getlist("select")

        if len(checks) == 0:
            pass
        else:
            num = checks[0]
            pwd = request.form["pwd"]
            info = get_thread_info(num)

            msg = ""
            if pwd == info["pwd"]:
                delete_thread_data(str(num))
                msg = "スレッドを削除しました"
            else:
                msg = "パスワードが違います"

            value_list = get_bbs_header()
            return render_template("delete_thread.html", value_list=value_list, msg=msg)

    return redirect("/")


# レスの削除
@app.route("/tools/<name>", methods=["POST"])
def delete_message(name):

    thread_no = int(name)
    info = get_thread_info(thread_no)

    if info["isExist"] == False:
        return render_template('not_found.html')

    if request.method == "POST":
        checks = request.form.getlist("select")
        pwd = request.form["pwd"]
        engine = create_engine(info["db_connect"])
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        for no in checks:
            res = session.query(BBS_Thread_Body).filter(
                BBS_Thread_Body.no == no).first()

            if res.pwd == pwd:
                res.stat = 2
        # データを確定
        session.commit()

    return redirect(url_for("thread_view", name=name))


@app.route("/make", methods=['POST', 'GET'])
def make_new_data():

    #
    #   thread.db と thread.ini が対になる形
    #

    if request.method == "POST":
        title = request.form["title"]
        message = request.form["message"]
        t_stamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        pwd = request.form["pwd"]

        # 各種入力チェック
        if len(str(title)) == 0:
            msg = "エラー！タイトルを入力してください"
            return render_template("make_threads.html", msg=msg)

        if len(str(message)) == 0:
            msg = "エラー！本文を入力してください"
            return render_template("make_threads.html", msg=msg)

        if len(str(pwd)) == 0:
            msg = "エラー！パスワードを入力してください"
            return render_template("make_threads.html", msg=msg)

        # スレ番号取得
        config = configparser.ConfigParser()
        config.read(INI_PATH)
        thread_no = int(config.get("BBS", "MakingCounter"))

        base_name = make_bbs_name(thread_no)
        ini_name = make_ini_name(thread_no)
        db_connect = make_db_connection(thread_no)

        # ini 生成
        config2 = configparser.ConfigParser()
        config2.add_section("THREAD")
        config2.set("THREAD", "no", str(thread_no))
        config2.set("THREAD", "title", title)
        config2.set("THREAD", "db", base_name + ".db")
        config2.set("THREAD", "pwd", pwd)
        with open(ini_name, 'w') as file:
            config2.write(file)

        # データベース生成
        engine = create_engine(db_connect)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        session.add(BBS_Thread_Body(
            msg=message, time_stamp=t_stamp, stat=1, pwd=pwd))
        session.flush()
        session.commit()

        # カウンタ更新
        thread_no += 1
        config.set("BBS", "MakingCounter", str(thread_no))
        with open(INI_PATH, 'w') as file:
            config.write(file)

        return redirect("/")

    return render_template("make_threads.html")


@app.route("/")
def hello():
    value_list = []

    # 設定ファイル ないなら作る
    if os.path.exists(INI_PATH) == False:
        config = configparser.ConfigParser()
        config.add_section("BBS")
        config.set("BBS", "MakingCounter", str(0))
        with open(INI_PATH, 'w') as file:
            config.write(file)

    value_list = get_bbs_header()

    return render_template("index.html", value_list=value_list)


if __name__ == "__main__":
    app.run()
