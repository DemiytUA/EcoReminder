from config import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(50), nullable=False)
    confirmed = db.Column(db.Boolean, nullable=False, default=False)

    drops = db.Column(db.Integer, nullable=False, default=0)

    apple = db.Column(db.Integer, nullable=False, default=0)
    cherry = db.Column(db.Integer, nullable=False, default=0)
    peony = db.Column(db.Integer, nullable=False, default=0)


    def __repr__(self):
        return f'<User id={self.id}, email={self.email}>'


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(50), nullable=False)

    time = db.Column(db.DateTime, nullable=False)
    comment = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f'<Notification id={self.id}, email={self.email}, time={self.time}, comment={self.comment}>'