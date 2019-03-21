
from flask import Flask
from flask import render_template
from flask import request       # POST GET するなら必要

from sqlalchemy import *
from sqlalchemy.orm import *
from sqlalchemy.ext.declarative import declarative_base

import sqlite3
import glob
import os

import configparser

Base = declarative_base()

app = Flask(__name__)

ini_path = "./info.ini"


def make_bbs_name(num):
    return "bbs_" + str(num).zfill(8)


class BBS_Thread_Body(Base):
    __tablename__ = "bbs_thread"

    no = Column(Integer, primary_key=True)
    msg = Column(String(255), default=" ")

    def __repr__(selef):
        return "<BBS Thread body(no='%s', msg='%s')>" % (self.no, self.msg)


# スレ表示
@app.route('/view/<name>', methods=['POST', 'GET'])
def thread_view(name=None):

    # iniからタイトルとか拾う
    base_name = make_bbs_name(int(name))
    ini_name = "./bbs/"+base_name+".ini"
    db_name = "sqlite:///bbs/"+base_name+".db"

    # スレッドがあるかチェック
    if os.path.exists(ini_name) == False:
        return render_template('not_found.html')

    config = configparser.ConfigParser()
    config.read(ini_name)
    title = config.get("THREAD", "title")

    # データベース準備
    engine = create_engine(db_name)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # レス入力がある場合
    if request.method == "POST":
        #        max_no = session.
        res = request.form["res"]
        session.add(BBS_Thread_Body(msg=res))
        session.commit()

    value_list = []
    res = session.query(BBS_Thread_Body).all()
    for v in res:
        value_list.append([v.no, v.msg])

    return render_template('view.html', value_list=value_list, title=title, thread_no=name)


@app.route("/make", methods=['POST', 'GET'])
def make_new_data():

    #
    #   thread.db と thread.ini が対になる形
    #

    if request.method == "POST":
        title = request.form["title"]

        # スレ番号取得
        config = configparser.ConfigParser()
        config.read(ini_path)
        thread_no = int(config.get("BBS", "MakingCounter"))

        base_name = make_bbs_name(thread_no)
        ini_name = "./bbs/"+base_name+".ini"
        db_name = "sqlite:///bbs/"+base_name+".db"

        # ini 生成
        config2 = configparser.ConfigParser()
        config2.add_section("THREAD")
        config2.set("THREAD", "no", str(thread_no))
        config2.set("THREAD", "title", title)
        config2.set("THREAD", "db", base_name + ".db")
        with open(ini_name, 'w') as file:
            config2.write(file)

        # データベース生成
        engine = create_engine(db_name)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        session.add(BBS_Thread_Body(msg="dummy"))
        session.flush()
        session.commit()

        # カウンタ更新
        thread_no += 1
        config.set("BBS", "MakingCounter", str(thread_no))
        with open(ini_path, 'w') as file:
            config.write(file)

    return render_template("make_threads.html")


@app.route("/")
def hello():
    value_list = []

    # 設定ファイル ないなら作る
    if os.path.exists(ini_path) == False:
        config = configparser.ConfigParser()
        config.add_section("BBS")
        config.set("BBS", "MakingCounter", str(0))
        with open(ini_path, 'w') as file:
            config.write(file)

    # BBSヘッダの データベース確認
    for f in glob.glob("./bbs/*.ini"):
        # ヘッダから情報チェック
        config = configparser.ConfigParser()
        config.read(f)
        value_list.append([
            config.get("THREAD", "no"),
            config.get("THREAD", "title"),
        ])
        pass

    return render_template("index.html", value_list=value_list)


if __name__ == "__main__":
    app.run()
