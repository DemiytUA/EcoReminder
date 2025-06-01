from flask import render_template, request, redirect, url_for, session, before_render_template
from werkzeug.security import generate_password_hash, check_password_hash
from flask_apscheduler import APScheduler
from sqlalchemy import desc
from flask_mail import Message
from datetime import datetime, timedelta

import time


from db_models import *
from config import *

from zoneinfo import ZoneInfo

def to_kyiv_time(dt):
    kyiv_tz = ZoneInfo('Europe/Kyiv')
    if dt.tzinfo is None:
        # Наївний час — додаємо таймзону Києва
        return dt.replace(tzinfo=kyiv_tz)
    else:
        # Якщо є таймзона — конвертуємо у Київську
        return dt.astimezone(kyiv_tz)


scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

def send_scheduled_email(email, subject, body, id):
    with app.app_context():
        msg = Message(subject, recipients=[email])
        msg.body = body
        mail.send(msg)

        notification = Notification.query.filter_by(id=id).first()
        db.session.delete(notification)
        db.session.commit()

def get_notifications_for_week(email):
    days = ['Mon.', 'Tues.', 'Wed.', 'Thurs.', 'Fri.', 'Sat.', 'Sun.']

    today = datetime.today()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)

    notifications = Notification.query.filter(
        Notification.email == email,
        Notification.time >= start_of_week,
        Notification.time <= end_of_week
    ).order_by(Notification.time).all()

    week_dict = {day: [] for day in days}

    for note in notifications:
        day_index = note.time.weekday()  # 0-Пн ... 6-Нд
        day_name = days[day_index]
        week_dict[day_name].append(note)

    return week_dict



# email : [code, time]
verification_codes = {

}

def get_user():
    user_email = session.get('user_email')
    user = User.query.filter_by(email=user_email).first()
    return user


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        form = request.form.get('form_name')

        if form == 'send':
            email = request.form['email']
            password = request.form['password']

            user = User.query.filter_by(email=email).first()
            if not user or not user.confirmed:
                password_hash = generate_password_hash(password)
                user = User(email=email, password=password_hash)
                db.session.add(user)
                db.session.commit()

                code = ''.join(secrets.choice('0123456789') for _ in range(6))
                msg_confim = Message('Email address confirmation', recipients=[email])
                msg_confim.html = f'''
                    <h2>Email address confirmation</h2>
                    <p>Please write this code on website:</p>
                    <bold>{code}</bold>
                '''
                mail.send(msg_confim)

                verification_codes[email] = [code, time.time()]

                return redirect(url_for('verify', email=email))
            else:
                return redirect(url_for('login'))



    return render_template('register.html')


@app.route('/verify/<email>', methods=['GET', 'POST'])
def verify(email):
    if request.method == 'POST':
        code = request.form['code']
        user_verification_data = verification_codes.get(email)

        if user_verification_data:
            if user_verification_data[0] == code and (time.time() - user_verification_data[1]) <= 120:
                user = User.query.filter_by(email=email).first()
                if user:
                    del verification_codes[email]

                    user.confirmed = True
                    db.session.commit()

                    session['user_email'] = email

                    return redirect(url_for('home'))
                else:
                    return redirect(url_for('register'))
    return render_template('verify.html', email=email)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()
        if user:
            if check_password_hash(user.password, password) and user.confirmed:
                session['user_email'] = email
                return redirect(url_for('home'))
        else:
            return redirect(url_for('register'))
    return render_template('login.html')


@app.route('/home', methods=['GET', 'POST'])
def home():
    if not get_user():
        return redirect(url_for('login'))

    if request.method == 'POST':
        return redirect(url_for('time_set'))

    now = datetime.now()
    last_notification = (
        Notification.query
        .filter(Notification.email == get_user().email, Notification.time >= now)
        .order_by(Notification.time.asc())
        .first()
    )

    return render_template('home.html', time=last_notification.time if last_notification else None)


@app.route('/time-set', methods=['GET', 'POST'])
def time_set():
    if not get_user():
        return redirect(url_for('login'))

    notifications_by_day = get_notifications_for_week(get_user().email)
    print(notifications_by_day)

    return render_template('time_set.html', notifications_by_day=notifications_by_day)


@app.route('/edit-time', methods=['GET', 'POST'])
def edit_time():
    days = [
        ('Mon.', 'monday'),
        ('Tues.', 'tuesday'),
        ('Wed.', 'wednesday'),
        ('Thurs.', 'thursday'),
        ('Fri.', 'friday'),
        ('Sat.', 'saturday'),
        ('Sun.', 'sunday')
    ]

    user = get_user()
    if not user:
        return redirect(url_for('login'))

    if request.method == 'POST':

        user_email = session.get('user_email')

        datetime_ = request.form['datetime']
        comment = request.form['comment']

        datetime_ = datetime.strptime(datetime_, '%Y-%m-%dT%H:%M')
        datetime_ = to_kyiv_time(datetime_)

        notification = Notification(email=user_email, time=datetime_, comment=comment)
        db.session.add(notification)
        db.session.commit()

        job_id = f"email_{user_email}_{int(datetime_.timestamp())}"
        scheduler.add_job(func=send_scheduled_email,
                          trigger='date',
                          run_date=datetime_,
                          args=[user_email, 'Тема листа', comment, notification.id],
                          id=job_id)

        return redirect(url_for('time_set'))



    return render_template('edit_time.html', days=days)


@app.route('/timetable', methods=['GET', 'POST'])
def timetable():
    if not get_user():
        return redirect(url_for('login'))

    user_email = session.get('user_email')
    notifications = Notification.query.filter_by(email=user_email).order_by(desc(Notification.id)).limit(3).all()
    print(notifications)
    return render_template('timetable.html', notifications=notifications)


@app.route('/garden', methods=['GET', 'POST'])
def garden_home():
    if not get_user():
        return redirect(url_for('login'))

    return render_template('garden_home.html')


@app.route('/garden/<name>', methods=['GET', 'POST'])
def garden(name):
    user = get_user()
    if not user:
        return redirect(url_for('login'))

    grow_tree = getattr(user, name)

    if grow_tree == 0:
        btn_text = 'Plant - 3'
    elif grow_tree == 4:
        btn_text = 'Grow - 1'
    else:
        btn_text = '🌳 Ready!'

    if request.method == 'POST':
        grow_tree = getattr(user, name)
        if grow_tree < 4:
            setattr(user, name, grow_tree + 1)
            db.session.commit()
        return redirect(url_for('garden', name=name))


    return render_template('garden.html', name=name, user=user if user else None, grow_tree=grow_tree, btn_text=btn_text)



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=80, debug=True)
