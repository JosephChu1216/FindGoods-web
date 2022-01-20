from flask import render_template, redirect, url_for, session, flash, request
from flask_login import login_user, current_user, login_required, logout_user
from sqlalchemy.orm import load_only
import app
from . import main
from .forms import LoginForm, RegisterForm, PhotoForm
from .. import db, mongo
from ..Image_recognition import img_recognition, pred_list
from ..models import Item, User, Recomm
import os
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.sql.expression import func
import random
import datetime
from tensorflow.keras import models
import unicodedata


# @main.route('/protected')
# @login_required
# def protected():
#     """
#  在login_user(user)之後，我們就可以透過current_user.id來取得用戶的相關資訊了
#  """
#     #  current_user確實的取得了登錄狀態
#     if current_user.is_active:
#         return 'Logged in as: ' + current_user.id + 'Login is_active:True'
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
    # def get_recommendations(itemid, n=10, cosine_sim=cosine_sim2):
    #     if itemid not in indices.index:
    #         print("furniture not in database.")
    #         return
    #     else:
    #         idx = indices[itemid]
    #     # cosine similarity scores of movies in descending order
    #     scores = pd.Series(cosine_sim[idx]).sort_values(ascending=False)
    #     # top n most similar movies indexes
    #     # use 1:n because 0 is the same movie entered
    #     top_n_idx = list(scores.iloc[1:n].index)
    #     return df2['title'].iloc[top_n_idx]


def chr_width(c):
    if unicodedata.east_asian_width(c) in ('F', 'W', 'A'):
        return 2
    else:
        return 1


def ch_length(unistr):
    return sum([chr_width(char) for char in unistr])


os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
net = models.load_model(os.path.join(app.config['default'].UPLOAD_FOLDER, "model-resnet50-final.h5"))


@main.route('/register.html', methods=['GET', 'POST'])
def register():
    loginform = LoginForm()
    reform = RegisterForm()
    if reform.validate_on_submit():
        users = [d.username for d in User.query.options(load_only(User.username))]
        # print(len(users))
        if reform.username_r.data not in users:
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
        recdata = [[d.item1, d.item2, d.item3, d.item4, d.item5, d.item6, d.item7, d.item8, d.item9, d.item10] for d in
                   db.session.query(Recomm).filter(Recomm.userId == theid)]
        # print(recdata[0])
        result = [[d.ITEMNAME, d.IMG_URL, d.URL, str(round(d.PRICE))[:-3] + ',' + str(round(d.PRICE))[-3:] if len(str(round(d.PRICE))) > 3 else str(round(d.PRICE)), d.BRAND, d.CATE, d.TAGS, d.ITEMID] for d in
                  db.session.query(Item).filter(Item.ITEMID.in_(recdata[0]))]
        # print(result)
    else:
        username = ''
        result = []
    tags = ('vasesbowl', 'frame', 'lamps', 'footstool', 'Cushion', 'mugs', 'desk')
    dataInfo = [[d.ITEMNAME, d.IMG_URL, d.URL, str(round(d.PRICE))[:-3] + ',' + str(round(d.PRICE))[-3:] if len(str(round(d.PRICE))) > 3 else str(round(d.PRICE)), d.BRAND, d.CATE, d.TAGS, d.ITEMID] for d in db.session.query(Item)]
    random.shuffle(dataInfo)
    # print(dataInfo[0])
    info = {}
    for i in tags:
        if i not in info.items():
            info[i] = list()
        for data in dataInfo:
            if data[5] == i:
                data.append(ch_length(data[0]))
                info[i].append(data)
    # print(info)
    # print(info['vasesbowl'])
    # print(tags[0])
    # print(dataInfo[0])
    # dataInfo = []
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
        date_now = "D" + str(datetime.date.today()).replace("-", "")
        if list(mongo.db[date_now].find({'_id': user.id.lstrip("0")})):
            click_itemid = "click." + itemid
            mongo.db[date_now].update({"name": username}, {"$set": {click_itemid: 1}})
        else:
            mongo.db[date_now].insert({'_id': user.id.lstrip("0"), "name": username, "click": {itemid: 1}})
        # if click_read(date_now, user.id.strip("0")):
        #     click_update(date_now, username, itemid)
        # else:
        #     dbdata = {'_id': user.id.strip("0"), "name": username, "click": [{itemid: 1}]}
        #     click_insert(date_now, dbdata)
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
    # user_select = [[d.ITEMID, d.CATE] for d in db.session.query(Item).filter(Item.ITEMID == itemid)]
    userselect = [[d.ITEMNO, d.ITEMID, d.ITEMNAME, d.IMG_URL, d.URL, str(round(d.PRICE))[:-3] + ',' + str(round(d.PRICE))[-3:] if len(str(round(d.PRICE))) > 3 else str(round(d.PRICE)), d.BRAND, d.CATE, d.TAGS] for d in db.session.query(Item).filter(Item.ITEMID == itemid)]
    recomItem = get_recommendations(int(itemid), cosine_sim2, indices, 6, df2).values.tolist()
    dataInfo = [[d.ITEMNAME, d.IMG_URL, d.URL, str(round(d.PRICE))[:-3] + ',' + str(round(d.PRICE))[-3:] if len(str(round(d.PRICE))) > 3 else str(round(d.PRICE)), d.BRAND, d.CATE, d.TAGS, d.ITEMID] for d in db.session.query(Item).filter(Item.ITEMID.in_(recomItem))]
    dataInfo_same_cate = [[d.ITEMNAME, d.IMG_URL, d.URL, str(round(d.PRICE))[:-3] + ',' + str(round(d.PRICE))[-3:] if len(str(round(d.PRICE))) > 3 else str(round(d.PRICE)), d.BRAND, d.CATE, d.TAGS, d.ITEMID] for d in db.session.query(Item).filter(Item.CATE == userselect[0][7])]
    dataInfo_push = []
    for n in dataInfo:
        if n[0] != userselect[0][2] and n[5] == userselect[0][7]:
            dataInfo_push.append(n)
    while len(dataInfo_push) < 4:
        dataInfo_push.append(random.choice(dataInfo_same_cate))
        if len(dataInfo_push) == 4:
            break
    # print(dataInfo)
    # dataInfo = []
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
    print(dataInfo)
    for n in dataInfo.items:
        if n.PFNO == 10:
            n.PFNO = 'IKEA'
        else:
            n.PFNO = 'TRPLUS'
    return render_template('products.html', username=username, dataInfo=dataInfo, tags=tags)
# def show_product(tags):
#     if current_user.is_authenticated:0
#         user = User.query.get(current_user.id)
#         username = user.username
#     else:
#         username = ''
#     dataInfo = [[d.ITEMNAME, d.IMG_URL, d.URL, str(d.PRICE), d.CATE, d.BRAND, p.PFNAME, d.ITEMID] for d, p in
#                       db.session.query(Item, Plform).filter(Item.CATE == tags).filter(Item.PFNO == Plform.PFNO)]
#     return render_template('products.html', username=username, dataInfo=dataInfo, tags=tags)


@main.route('/search.html', methods=['GET', 'POST'])
def search():
    if current_user.is_authenticated:
        user = User.query.get(current_user.id)
        username = user.username
    else:
        username = ''
    imgform = PhotoForm()
    # print(imgform.image.data)
    # print(app.config['default'].UPLOAD_FOLDER)
    if imgform.validate_on_submit():
        image = imgform.image.data
        # print(image)
        filename = image.filename
        # print(filename)
        image.save(os.path.join(app.config['default'].UPLOAD_FOLDER, filename))
        uploadfile_path = 'img/uploads/' + filename
        # print(uploadfile_path)
        # print(os.getcwd())
        pre_list = img_recognition('model-resnet50-final.h5', filename)
        x = img_recognition(filename)
        pred = net.predict(x)[0]
        pre_list = pred_list(pred)
        pre_item = pre_list[0][1]
        pre_acc = "Accuracy: " + str(pre_list[0][0])
        if pre_list[0][0] >= 0.9:
            pre_item_list_all = [[d.ITEMID, d.IMG_URL, d.ITEMNAME, str(round(d.PRICE))[:-3] + ',' + str(round(d.PRICE))[-3:] if len(str(round(d.PRICE))) > 3 else str(round(d.PRICE))] for d in Item.query.filter(Item.CATE == pre_item)]
            item_num = len(pre_item_list_all)-1
            p = pre_item_list_all[random.randint(0, item_num)]
            # print(p[1])
        else:
            p = None
        return render_template('search.html', username=username, uploadfile_path=uploadfile_path, imgform=imgform, pre_item=pre_item, pre_acc=pre_acc, p=p)
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
