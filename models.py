from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class AdminSettings(db.Model):
    __tablename__ = "admin_settings"

    id = db.Column(db.Integer, primary_key=True)
    password_hash = db.Column(db.String(255), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Space(db.Model):
    __tablename__ = "spaces"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(50), nullable=False, unique=True)
    space_type = db.Column(db.String(30), nullable=False)
    color = db.Column(db.String(7), nullable=False, default="#1a4f8b")
    active = db.Column(db.Boolean, nullable=False, default=True)

    requests = db.relationship("ReservationRequest", back_populates="space")
    bookings = db.relationship("Booking", back_populates="space")

    def __repr__(self):
        return f"<Space {self.name}>"


class ReservationRequest(db.Model):
    __tablename__ = "reservation_requests"

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), nullable=False, unique=True, index=True)
    professor_name = db.Column(db.String(120), nullable=False)
    professor_email = db.Column(db.String(120), nullable=False)
    turma = db.Column(db.String(50), nullable=False)
    materia = db.Column(db.String(120), nullable=False)
    plano_aula = db.Column(db.Text, nullable=False)
    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=False)
    space_id = db.Column(db.Integer, db.ForeignKey("spaces.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING)
    rejection_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)

    space = db.relationship("Space", back_populates="requests")
    booking = db.relationship("Booking", back_populates="request", uselist=False)

    @property
    def is_pending(self):
        return self.status == self.STATUS_PENDING


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(
        db.Integer, db.ForeignKey("reservation_requests.id"), nullable=True, unique=True
    )
    professor_name = db.Column(db.String(120), nullable=False)
    turma = db.Column(db.String(50), nullable=False)
    materia = db.Column(db.String(120), nullable=False)
    plano_aula = db.Column(db.Text, nullable=False)
    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=False)
    space_id = db.Column(db.Integer, db.ForeignKey("spaces.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    space = db.relationship("Space", back_populates="bookings")
    request = db.relationship("ReservationRequest", back_populates="booking")
