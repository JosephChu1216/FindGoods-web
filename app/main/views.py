from flask import render_template, redirect, url_for, session, flash, request
from flask_login import login_user, current_user, login_required, logout_user
from sqlalchemy.orm import load_only
import app
from . import main
from .forms import LoginForm, RegisterForm, PhotoForm
from .. import db, mongo
from ..Image_recognition import img_recognition, pred_list
from ..models import Item, User, Recomm, Plform
import os
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.sql.expression import func
import random
import datetime
from tensorflow.keras import models


def get_recommendations(itemid, cosine_sim, indices, n, df2):
    if itemid not in indices.index:
        print("furniture not in database.")
        return
    else:
        idx = indices[itemid]
    # cosine similarity scores of movies in descending order
    scores = pd.Series(cosine_sim[idx]).sort_values(ascending=False)
    # top n most similar movies indexes
    # use 1:n because 0 is the same movie entered
    top_n_idx = list(scores.iloc[1:n].index)
    return df2['title'].iloc[top_n_idx]


def price_tran(p):
    int_price = str(int(p))
    if len(int_price) > 3:
        return int_price[:-3] + ',' + int_price[-3:]
    else:
        return int_price


def pfno_tran(pf):
    if pf == 10:
        return 'IKEA'
    else:
        return 'TRPLUS'


os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
net = models.load_model(os.path.join(app.config['default'].UPLOAD_FOLDER, "model-densenet121-final.h5"))


@main.route('/register.html', methods=['GET', 'POST'])
def register():
    loginform = LoginForm()
    reform = RegisterForm()
    if reform.validate_on_submit():
        users = [d.username.lower() for d in User.query.options(load_only(User.username))]
        # print(len(users))
        if reform.username_r.data.lower() not in users:
            if len(users) == 0:
                user = User(id="1".zfill(4),
                            email=reform.email.data.lower(),
                            username=reform.username_r.data,
                            password=reform.password_r.data,
                            sex=reform.sex.data,
                            age=reform.age.data,
                            area=reform.area.data,
                            career=reform.career.data)
            else:
                first_data = User.query.order_by(User.id.desc()).first()
                new_id = str(int(first_data.id) + 1).zfill(4)
                user = User(id=new_id,
                            email=reform.email.data.lower(),
                            username=reform.username_r.data,
                            password=reform.password_r.data,
                            sex=reform.sex.data,
                            age=reform.age.data,
                            area=reform.area.data,
                            career=reform.career.data)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            print(session)
            return redirect(url_for('.index'))
        flash('Username has been used!')

    elif loginform.validate_on_submit():
        user = User.query.filter_by(username=loginform.username.data).first()
        print(user.id)
        if user is not None and user.verify_password(loginform.password.data):
            login_user(user, remember=loginform.remember_me.data)
            print(session)
            # return redirect(url_for('.protected'))
            return redirect(url_for('.index'))
        flash('Invalid username or password.')
    return render_template('register.html', loginform=loginform, reform=reform)


@main.route('/logout')
@login_required
def logout():
    logout_user()
    print(session)
    # flash('You have been logged out, see you next time!!')
    return redirect(url_for('.register'))


@main.route('/', methods=['GET', 'POST'])
@main.route('/index.html', methods=['GET', 'POST'])
def index():
    if current_user.is_authenticated:
        user = User.query.get(current_user.id)
        theid = (user.id.strip('0'))
        username = user.username
        redata = [[d.item1, d.item2, d.item3, d.item4, d.item5, d.item6, d.item7, d.item8, d.item9, d.item10] for d in
                  db.session.query(Recomm).filter(Recomm.userId == theid)]
        # print(recdata[0])
        result = [[d.ITEMNAME, d.IMG_URL, pfno_tran(d.PFNO), price_tran(d.PRICE), d.BRAND, d.CATE, d.TAGS, d.ITEMID] for
                  d in
                  db.session.query(Item).filter(Item.ITEMID.in_(redata[0]))]
        # print(result[:8])
    else:
        username = ''
        result = []
    tags = ('vasesbowl', 'frame', 'lamps', 'footstool', 'Cushion', 'mugs', 'desk')
    dataInfo = [[d.ITEMNAME, d.IMG_URL, a.PFNAME, price_tran(d.PRICE), d.BRAND, d.CATE, d.TAGS, d.ITEMID] for d, a in
                db.session.query(Item, Plform)]
    random.shuffle(dataInfo)
    # print(dataInfo[0])
    info = {}
    for i in tags:
        if i not in info.items():
            info[i] = list()
        for data in dataInfo:
            if data[5] == i:
                info[i].append(data)
    return render_template('index.html', username=username, dataInfo=info, tags=tags, recdata=result[:8])


# 冷啟動，此用者偏好選單
@main.route('/main_select')
def index3():
    dataInfo = []
    return render_template('main_select.html', dataInfo=dataInfo)


# content-base推薦
@main.route('/recommend/<itemid>')
def recommend(itemid):
    if current_user.is_authenticated:
        user = User.query.get(current_user.id)
        username = user.username
        date_now = "D" + str(datetime.date.today()).replace("-", "")  # 紀錄當下時間
        # 紀錄會員點擊並儲存至mongodb
        if list(mongo.db[date_now].find({'_id': user.id.lstrip("0")})):
            click_timestamp = "click." + str(round(datetime.datetime.now().timestamp()))
            mongo.db[date_now].update_one({"name": username}, {"$set": {click_timestamp: itemid}})
        else:
            mongo.db[date_now].insert_one({'_id': user.id.lstrip("0"), "name": username,
                                           "click": {str(round(datetime.datetime.now().timestamp())): itemid}})
    else:
        username = ''
    data = [[d.ITEMID, d.TAGS] for d in db.session.query(Item)]
    df2 = pd.DataFrame(data, columns=['title', 'keywords'])
    # print(df2)
    count = CountVectorizer()
    count_matrix = count.fit_transform(df2['keywords'])
    cosine_sim2 = cosine_similarity(count_matrix, count_matrix)
    indices = pd.Series(df2.index, index=df2['title'])
    # print(indices)
    userselect = [[d.ITEMNO, d.ITEMID, d.ITEMNAME, d.IMG_URL, d.URL, str(round(d.PRICE)), d.BRAND, d.CATE, d.TAGS] for d
                  in db.session.query(Item).filter(Item.ITEMID == itemid)]
    recomItem = get_recommendations(int(itemid), cosine_sim2, indices, 6, df2).values.tolist()
    dataInfo = [[d.ITEMNAME, d.IMG_URL, pfno_tran(d.PFNO), price_tran(d.PRICE), d.BRAND, d.CATE, d.TAGS, d.ITEMID] for d in
                db.session.query(Item).filter(Item.ITEMID.in_(recomItem))]
    dataInfo_same_cate = [[d.ITEMNAME, d.IMG_URL, pfno_tran(d.PFNO), price_tran(d.PRICE), d.BRAND, d.CATE, d.TAGS, d.ITEMID] for d
                          in db.session.query(Item).filter(Item.CATE == userselect[0][7])]
    dataInfo_push = []
    for n in dataInfo:
        if n[0] != userselect[0][2] and n[5] == userselect[0][7]:
            dataInfo_push.append(n)
    while len(dataInfo_push) < 4:
        dataInfo_push.append(random.choice(dataInfo_same_cate))
        if len(dataInfo_push) == 4:
            break
    return render_template('contentbase.html', username=username, userselect=userselect, dataInfo_push=dataInfo_push)


@main.route('/myaccount.html', methods=['GET'])
def myaccount():
    if current_user.is_authenticated:
        user = User.query.get(current_user.id)
        username = user.username
        userInfo = []
        for d in User.query.filter(User.id == current_user.id):
            userInfo.append(["Username", d.username])
            userInfo.append(["Email", d.email])
            userInfo.append(["Sex", d.sex])
            userInfo.append(["Age", d.age])
            userInfo.append(["Living Place", d.area])
            userInfo.append(["Occupation", d.career])
    else:
        username = ''
        userInfo = ''
    return render_template('myaccount.html', username=username, userInfo=userInfo)


@main.route('/products/<tags>', methods=['GET'])
@main.route('/products/<tags>/<int:page>', methods=['GET'])
def view(tags):
    if current_user.is_authenticated:
        user = User.query.get(current_user.id)
        username = user.username
    else:
        username = ''
    page = request.args.get('page', 1, type=int)
    dataInfo = Item.query.filter(Item.CATE == tags).order_by(func.random()).paginate(page=int(page), per_page=20)
    # .order_by(func.random())
    # random.shuffle(dataInfo)
    for i in dataInfo.items:
        i.PFNO = pfno_tran(i.PFNO)
        i.PRICE = price_tran(i.PRICE)
    return render_template('products.html', username=username, dataInfo=dataInfo, tags=tags)


@main.route('/search.html', methods=['GET', 'POST'])
def search():
    if current_user.is_authenticated:
        user = User.query.get(current_user.id)
        username = user.username
    else:
        username = ''
    imgform = PhotoForm()
    if imgform.validate_on_submit():
        image = imgform.image.data
        # print(image)
        filename = image.filename
        # print(filename)
        image.save(os.path.join(app.config['default'].UPLOAD_FOLDER, filename))
        uploadfile_path = 'img/uploads/' + filename
        x = img_recognition(filename)
        pred = net.predict(x)[0]
        pre_list = pred_list(pred)
        candidate_list = []
        for cls in pre_list:
            if cls[0] >= 0.9:
                pre_item = cls[1]
                pre_acc = "Confidence: " + str(cls[0])
                pre_item_list_all = [[d.ITEMNAME, d.IMG_URL, pfno_tran(d.PFNO), price_tran(d.PRICE), d.BRAND, d.CATE, d.TAGS, d.ITEMID] for d in
                                     Item.query.filter(Item.CATE == pre_item)]
                item_num = len(pre_item_list_all) - 1
                p = pre_item_list_all[random.randint(0, item_num)]
                p.append(pre_item)
                p.append(pre_acc)
                candidate_list.append(p)
            else:
                pass
        return render_template('search.html', username=username, uploadfile_path=uploadfile_path, imgform=imgform,
                               candidate_list=candidate_list)
    elif imgform.errors:
        print("error")
        flash(imgform.errors['image'][0])
    return render_template('search.html', username=username, imgform=imgform)


@main.route('/trend.html', methods=['GET'])
def trend():
    if current_user.is_authenticated:
        user = User.query.get(current_user.id)
        username = user.username
    else:
        username = ''
    return render_template('trend.html', username=username)


@main.route('/about.html', methods=['GET'])
def about():
    if current_user.is_authenticated:
        user = User.query.get(current_user.id)
        username = user.username
    else:
        username = ''
    return render_template('about.html', username=username)
