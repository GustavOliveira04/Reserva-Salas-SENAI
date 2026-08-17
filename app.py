import calendar
import re
import secrets
import smtplib
import unicodedata
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_mail import Mail
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash
from config import Config
from email_service import (
    send_admin_password_reset_email,
    send_admin_request_email,
    send_professor_approved_email,
    send_professor_rejected_email,
)
from models import AdminSettings, Booking, ReservationRequest, Space, db

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
mail = Mail(app)

RESET_TOKEN_SALT = "admin-password-reset"
RESET_TOKEN_MAX_AGE = 1800  # 30 minutos


def get_reset_serializer():
    return URLSafeTimedSerializer(app.config["SECRET_KEY"])


def seed_admin_settings():
    if AdminSettings.query.get(1) is None:
        db.session.add(
            AdminSettings(
                id=1,
                password_hash=generate_password_hash(app.config["ADMIN_PASSWORD"]),
            )
        )
        db.session.commit()


def cleanup_expired_bookings():
    """Remove do calendário as reservas cujo horário de término já passou."""
    Booking.query.filter(Booking.end_datetime < datetime.now()).delete(
        synchronize_session=False
    )
    db.session.commit()


@app.before_request
def _remove_expired_bookings():
    cleanup_expired_bookings()


def admin_login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapped


SPACES_SEED = [
    ("Laboratório 1", "lab-1", "laboratorio"),
    ("Laboratório 2", "lab-2", "laboratorio"),
    ("Laboratório 3", "lab-3", "laboratorio"),
    ("Auditório", "auditorio", "auditorio"),
    ("Biblioteca", "biblioteca", "biblioteca"),
]

# Paleta de azuis usada para colorir os espaços no calendário. Ao cadastrar um
# novo espaço, a próxima cor da lista é atribuída automaticamente (cíclico).
SPACE_COLOR_PALETTE = [
    "#1a4f8b",
    "#2564a8",
    "#3a7bc4",
    "#0d3766",
    "#4a86c4",
    "#123a63",
    "#5f8fc2",
    "#2f6094",
]

SPACE_TYPES = [
    ("laboratorio", "Laboratório"),
    ("auditorio", "Auditório"),
    ("biblioteca", "Biblioteca"),
    ("sala", "Sala de reunião / outro"),
]

WEEKDAYS_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
MONTHS_PT = [
    "",
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
]


def seed_spaces():
    if Space.query.count() == 0:
        for index, (name, slug, space_type) in enumerate(SPACES_SEED):
            color = SPACE_COLOR_PALETTE[index % len(SPACE_COLOR_PALETTE)]
            db.session.add(
                Space(name=name, slug=slug, space_type=space_type, color=color, active=True)
            )
        db.session.commit()


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "espaco"


def unique_slug(base_slug):
    slug = base_slug
    counter = 2
    while Space.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def next_space_color():
    return SPACE_COLOR_PALETTE[Space.query.count() % len(SPACE_COLOR_PALETTE)]


def parse_datetime_field(date_str, time_str=None, default_time="00:00"):
    if not date_str:
        raise ValueError("Data obrigatória.")
    time_value = time_str or default_time
    return datetime.strptime(f"{date_str} {time_value}", "%Y-%m-%d %H:%M")


def bookings_overlap(space_id, start_dt, end_dt, exclude_booking_id=None):
    query = Booking.query.filter(
        Booking.space_id == space_id,
        Booking.start_datetime < end_dt,
        Booking.end_datetime > start_dt,
    )
    if exclude_booking_id:
        query = query.filter(Booking.id != exclude_booking_id)
    return query.first() is not None


def get_bookings_for_month(year, month):
    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)

    start_range = datetime.combine(first_day, datetime.min.time())
    end_range = datetime.combine(last_day, datetime.max.time())

    bookings = (
        Booking.query.filter(
            Booking.start_datetime <= end_range,
            Booking.end_datetime >= start_range,
        )
        .order_by(Booking.start_datetime)
        .all()
    )

    by_date = {}
    for booking in bookings:
        current = booking.start_datetime.date()
        last = booking.end_datetime.date()
        while current <= last:
            if current.year == year and current.month == month:
                by_date.setdefault(current, []).append(booking)
            current += timedelta(days=1)

    return by_date


def build_calendar_weeks(year, month, bookings_by_date):
    cal = calendar.Calendar(firstweekday=0)
    weeks = []
    today = date.today()

    for week in cal.monthdatescalendar(year, month):
        week_data = []
        for day in week:
            week_data.append(
                {
                    "date": day,
                    "in_month": day.month == month,
                    "is_today": day == today,
                    "bookings": bookings_by_date.get(day, []) if day.month == month else [],
                }
            )
        weeks.append(week_data)

    return weeks


def prev_next_month(year, month):
    if month == 1:
        return year - 1, 12
    return year, month - 1


def next_month_values(year, month):
    if month == 12:
        return year + 1, 1
    return year, month + 1


def approve_reservation(reservation):
    if reservation.status == ReservationRequest.STATUS_APPROVED:
        return "approved", "Esta solicitação já foi aprovada."

    if reservation.status == ReservationRequest.STATUS_REJECTED:
        return "rejected", "Esta solicitação já foi recusada anteriormente."

    if bookings_overlap(
        reservation.space_id,
        reservation.start_datetime,
        reservation.end_datetime,
    ):
        reservation.status = ReservationRequest.STATUS_REJECTED
        reservation.rejection_reason = (
            "Recusada automaticamente: o horário passou a conflitar com outra "
            "reserva já confirmada para o mesmo espaço."
        )
        reservation.processed_at = datetime.utcnow()
        db.session.commit()
        try:
            send_professor_rejected_email(reservation)
        except Exception:
            pass
        return "conflict", "Conflito de horário detectado. A solicitação foi recusada automaticamente."

    booking = Booking(
        request_id=reservation.id,
        professor_name=reservation.professor_name,
        turma=reservation.turma,
        materia=reservation.materia,
        plano_aula=reservation.plano_aula,
        start_datetime=reservation.start_datetime,
        end_datetime=reservation.end_datetime,
        space_id=reservation.space_id,
    )
    reservation.status = ReservationRequest.STATUS_APPROVED
    reservation.processed_at = datetime.utcnow()
    db.session.add(booking)
    db.session.commit()

    try:
        send_professor_approved_email(reservation)
    except Exception:
        return "approved", "Reserva aprovada, mas houve erro ao enviar e-mail ao professor."

    return "approved", "Reserva aprovada. O professor foi notificado no e-mail informado no formulário."


def reject_reservation(reservation, reason=""):
    if reservation.status == ReservationRequest.STATUS_REJECTED:
        return "rejected", "Esta solicitação já foi recusada."

    if reservation.status == ReservationRequest.STATUS_APPROVED:
        return "approved", "Esta solicitação já foi aprovada e não pode ser recusada."

    reservation.status = ReservationRequest.STATUS_REJECTED
    reservation.rejection_reason = reason.strip() or None
    reservation.processed_at = datetime.utcnow()
    db.session.commit()

    try:
        send_professor_rejected_email(reservation)
    except Exception:
        return "rejected", "Solicitação recusada, mas houve erro ao enviar e-mail ao professor."

    return "rejected", "Solicitação recusada. O professor foi notificado no e-mail informado no formulário."


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("is_admin"):
        return redirect(url_for("admin_solicitacoes"))

    next_url = request.args.get("next") or url_for("admin_solicitacoes")

    if request.method == "POST":
        password = request.form.get("password", "")
        next_url = request.form.get("next") or next_url
        settings = AdminSettings.query.get(1)
        if settings and check_password_hash(settings.password_hash, password):
            session["is_admin"] = True
            flash("Login realizado com sucesso.", "success")
            return redirect(next_url)
        flash("Senha incorreta.", "danger")

    return render_template("admin_login.html", next_url=next_url)


@app.route("/admin/esqueci-senha", methods=["GET", "POST"])
def admin_forgot_password():
    if request.method == "POST":
        serializer = get_reset_serializer()
        token = serializer.dumps({"purpose": RESET_TOKEN_SALT}, salt=RESET_TOKEN_SALT)
        reset_url = url_for("admin_reset_password", token=token, _external=True)

        try:
            send_admin_password_reset_email(reset_url)
            flash(
                "Link de redefinição enviado para o e-mail do administrador. "
                "Ele expira em 30 minutos.",
                "success",
            )
            return redirect(url_for("admin_login"))
        except smtplib.SMTPAuthenticationError as exc:
            app.logger.exception("Falha de autenticação SMTP ao enviar redefinição de senha")
            smtp_code = getattr(exc, "smtp_code", "?")
            smtp_error = getattr(exc, "smtp_error", b"")
            if isinstance(smtp_error, bytes):
                smtp_error = smtp_error.decode("utf-8", errors="replace")
            flash(
                "Não foi possível enviar o e-mail: o Gmail recusou o login do remetente. "
                f"Resposta do Gmail: [{smtp_code}] {smtp_error}",
                "warning",
            )
        except Exception as exc:
            app.logger.exception("Falha ao enviar e-mail de redefinição de senha")
            flash(
                "Não foi possível enviar o e-mail de redefinição. "
                "Verifique a configuração SMTP no arquivo .env e reinicie o servidor. "
                f"Detalhe: {exc}",
                "warning",
            )

    return render_template("admin_forgot_password.html")


@app.route("/admin/redefinir-senha/<token>", methods=["GET", "POST"])
def admin_reset_password(token):
    serializer = get_reset_serializer()
    try:
        serializer.loads(token, salt=RESET_TOKEN_SALT, max_age=RESET_TOKEN_MAX_AGE)
    except SignatureExpired:
        flash("Este link de redefinição expirou. Solicite um novo.", "danger")
        return redirect(url_for("admin_forgot_password"))
    except BadSignature:
        flash("Link de redefinição inválido.", "danger")
        return redirect(url_for("admin_forgot_password"))

    if request.method == "POST":
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors = []
        if len(new_password) < 6:
            errors.append("A nova senha deve ter pelo menos 6 caracteres.")
        if new_password != confirm_password:
            errors.append("As senhas não coincidem.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("admin_reset_password.html", token=token)

        settings = AdminSettings.query.get(1)
        if not settings:
            settings = AdminSettings(id=1, password_hash=generate_password_hash(new_password))
            db.session.add(settings)
        else:
            settings.password_hash = generate_password_hash(new_password)
        db.session.commit()

        session.pop("is_admin", None)
        flash("Senha redefinida com sucesso! Faça login com a nova senha.", "success")
        return redirect(url_for("admin_login"))

    return render_template("admin_reset_password.html", token=token)


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    flash("Você saiu da área de administração.", "success")
    return redirect(url_for("index"))


@app.route("/admin")
@admin_login_required
def admin_solicitacoes():
    pending = (
        ReservationRequest.query.filter_by(status=ReservationRequest.STATUS_PENDING)
        .order_by(ReservationRequest.created_at.desc())
        .all()
    )
    bookings = Booking.query.order_by(Booking.start_datetime.desc()).all()
    return render_template("admin_solicitacoes.html", requests=pending, bookings=bookings)


@app.route("/admin/solicitacoes/<int:request_id>/excluir", methods=["POST"])
@admin_login_required
def excluir_solicitacao(request_id):
    reservation = ReservationRequest.query.get_or_404(request_id)
    db.session.delete(reservation)
    db.session.commit()
    flash("Solicitação excluída.", "success")
    return redirect(url_for("admin_solicitacoes"))


@app.route("/admin/reservas/<int:booking_id>/excluir", methods=["POST"])
@admin_login_required
def excluir_reserva(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.request:
        db.session.delete(booking.request)
    db.session.delete(booking)
    db.session.commit()
    flash("Reserva excluída do calendário.", "success")
    return redirect(url_for("admin_solicitacoes"))


@app.route("/admin/espacos")
@admin_login_required
def admin_espacos():
    spaces = Space.query.order_by(Space.id).all()
    return render_template("admin_espacos.html", spaces=spaces, space_types=SPACE_TYPES)


@app.route("/admin/espacos/novo", methods=["POST"])
@admin_login_required
def criar_espaco():
    name = request.form.get("name", "").strip()
    space_type = request.form.get("space_type", "sala").strip()

    if not name:
        flash("Informe um nome para o espaço.", "danger")
        return redirect(url_for("admin_espacos"))

    if Space.query.filter_by(name=name).first():
        flash(f'Já existe um espaço chamado "{name}".', "danger")
        return redirect(url_for("admin_espacos"))

    if space_type not in dict(SPACE_TYPES):
        space_type = "sala"

    slug = unique_slug(slugify(name))
    space = Space(
        name=name,
        slug=slug,
        space_type=space_type,
        color=next_space_color(),
        active=True,
    )
    db.session.add(space)
    db.session.commit()
    flash(f'Espaço "{name}" adicionado com sucesso.', "success")
    return redirect(url_for("admin_espacos"))


@app.route("/admin/espacos/<int:space_id>/alternar", methods=["POST"])
@admin_login_required
def alternar_espaco(space_id):
    space = Space.query.get_or_404(space_id)
    space.active = not space.active
    db.session.commit()
    status = "reativado" if space.active else "interditado"
    flash(f'Espaço "{space.name}" foi {status}.', "success")
    return redirect(url_for("admin_espacos"))


@app.route("/")
def index():
    today = date.today()
    year = request.args.get("year", type=int, default=today.year)
    month = request.args.get("month", type=int, default=today.month)

    if month < 1 or month > 12:
        flash("Mês inválido.", "danger")
        return redirect(url_for("index"))

    bookings_by_date = get_bookings_for_month(year, month)
    weeks = build_calendar_weeks(year, month, bookings_by_date)
    spaces = Space.query.order_by(Space.id).all()

    prev_y, prev_m = prev_next_month(year, month)
    next_y, next_m = next_month_values(year, month)

    return render_template(
        "index.html",
        weeks=weeks,
        year=year,
        month=month,
        month_name=MONTHS_PT[month],
        weekdays=WEEKDAYS_PT,
        spaces=spaces,
        prev_year=prev_y,
        prev_month=prev_m,
        next_year=next_y,
        next_month=next_m,
    )


@app.route("/api/disponibilidade")
def api_disponibilidade():
    space_id = request.args.get("space_id", type=int)
    today = date.today()
    year = request.args.get("year", type=int, default=today.year)
    month = request.args.get("month", type=int, default=today.month)

    if not space_id or month < 1 or month > 12:
        return jsonify({"error": "Parâmetros inválidos."}), 400

    if not Space.query.get(space_id):
        return jsonify({"error": "Espaço não encontrado."}), 404

    bookings_by_date = get_bookings_for_month(year, month)
    weeks = build_calendar_weeks(year, month, bookings_by_date)

    days = []
    for week in weeks:
        for day in week:
            occupied = day["in_month"] and any(
                b.space_id == space_id for b in day["bookings"]
            )
            days.append(
                {
                    "date": day["date"].isoformat(),
                    "day": day["date"].day,
                    "in_month": day["in_month"],
                    "is_today": day["is_today"],
                    "occupied": occupied,
                }
            )

    prev_y, prev_m = prev_next_month(year, month)
    next_y, next_m = next_month_values(year, month)

    return jsonify(
        {
            "year": year,
            "month": month,
            "month_name": MONTHS_PT[month],
            "weekdays": WEEKDAYS_PT,
            "days": days,
            "prev_year": prev_y,
            "prev_month": prev_m,
            "next_year": next_y,
            "next_month": next_m,
        }
    )


@app.route("/reservar", methods=["GET", "POST"])
def reservar():
    spaces = Space.query.filter_by(active=True).order_by(Space.id).all()
    min_date_obj = date.today() + timedelta(days=app.config["RESERVATION_MIN_ADVANCE_DAYS"])
    min_date = min_date_obj.isoformat()
    min_date_br = min_date_obj.strftime("%d/%m/%Y")

    if request.method == "POST":
        professor_name = request.form.get("professor_name", "").strip()
        professor_email = request.form.get("professor_email", "").strip()
        turma = request.form.get("turma", "").strip()
        materia = request.form.get("materia", "").strip()
        plano_aula = request.form.get("plano_aula", "").strip()
        start_date = request.form.get("start_date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_date = request.form.get("end_date", "").strip()
        end_time = request.form.get("end_time", "23:59").strip()
        space_id = request.form.get("space_id", type=int)

        errors = []
        if not professor_name:
            errors.append("Informe o nome do professor.")
        if not professor_email or "@" not in professor_email:
            errors.append("Informe um e-mail válido do professor.")
        if not turma:
            errors.append("Informe o número da turma.")
        if not materia:
            errors.append("Informe a matéria ou unidade curricular.")
        if not plano_aula:
            errors.append("Informe o plano de aula.")
        if not space_id:
            errors.append("Selecione um espaço para reserva.")

        try:
            start_dt = parse_datetime_field(start_date, start_time)
            end_dt = parse_datetime_field(end_date, end_time or "23:59")
        except ValueError:
            errors.append("Datas ou horários inválidos.")
            start_dt = end_dt = None

        if start_dt and end_dt and end_dt < start_dt:
            errors.append("A data/hora de término deve ser posterior ao início.")

        min_advance_days = app.config["RESERVATION_MIN_ADVANCE_DAYS"]
        min_allowed_dt = datetime.now() + timedelta(days=min_advance_days)
        if start_dt and start_dt < min_allowed_dt:
            errors.append(
                f"Solicitações precisam ser feitas com pelo menos {min_advance_days} dias de "
                f"antecedência. Data mais próxima disponível: {min_allowed_dt.strftime('%d/%m/%Y')}."
            )

        space = Space.query.get(space_id) if space_id else None
        if space_id and not space:
            errors.append("Espaço selecionado não encontrado.")

        if space and not space.active:
            errors.append(f"O espaço \"{space.name}\" está indisponível para novas reservas no momento.")

        if space and start_dt and end_dt and bookings_overlap(space.id, start_dt, end_dt):
            errors.append(
                f"Colisão de horários: já existe uma reserva confirmada para "
                f"\"{space.name}\" nesse período. Escolha outro horário, dia ou espaço."
            )

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "reservar.html", spaces=spaces, form=request.form, min_date=min_date,
                min_date_br=min_date_br, min_advance_days=min_advance_days,
            )

        reservation = ReservationRequest(
            token=secrets.token_urlsafe(32),
            professor_name=professor_name,
            professor_email=professor_email,
            turma=turma,
            materia=materia,
            plano_aula=plano_aula,
            start_datetime=start_dt,
            end_datetime=end_dt,
            space_id=space.id,
        )
        db.session.add(reservation)
        db.session.commit()

        try:
            send_admin_request_email(reservation)
            flash(
                "Solicitação enviada ao administrador! "
                "Você receberá o retorno no e-mail informado quando for analisada.",
                "success",
            )
        except smtplib.SMTPAuthenticationError as exc:
            app.logger.exception("Falha de autenticação SMTP na solicitação #%s", reservation.id)
            smtp_code = getattr(exc, "smtp_code", "?")
            smtp_error = getattr(exc, "smtp_error", b"")
            if isinstance(smtp_error, bytes):
                smtp_error = smtp_error.decode("utf-8", errors="replace")
            flash(
                "Solicitação registrada, mas o Gmail recusou o login do e-mail remetente. "
                "Gere uma Senha de app (Conta Google → Segurança → Verificação em duas etapas → "
                "Senhas de app) e coloque-a em MAIL_PASSWORD no .env — a senha normal da conta não funciona. "
                f"Resposta do Gmail: [{smtp_code}] {smtp_error}",
                "warning",
            )
        except Exception as exc:
            app.logger.exception("Falha ao enviar e-mail da solicitação #%s", reservation.id)
            flash(
                "Solicitação registrada, mas houve erro ao enviar o e-mail. "
                "Verifique a configuração SMTP no arquivo .env e reinicie o servidor. "
                f"Detalhe: {exc}",
                "warning",
            )

        return redirect(url_for("index"))

    return render_template(
        "reservar.html", spaces=spaces, form={}, min_date=min_date,
        min_date_br=min_date_br, min_advance_days=app.config["RESERVATION_MIN_ADVANCE_DAYS"],
    )


@app.route("/aprovar/<token>")
def aprovar(token):
    reservation = ReservationRequest.query.filter_by(token=token).first_or_404()
    action, message = approve_reservation(reservation)

    category = "success"
    if action == "rejected":
        category = "warning"
    elif action == "conflict":
        category = "danger"
    elif "erro" in message.lower():
        category = "warning"

    flash(message, category)
    return render_template("acao_admin.html", reservation=reservation, action=action)


@app.route("/recusar/<token>", methods=["GET", "POST"])
def recusar(token):
    reservation = ReservationRequest.query.filter_by(token=token).first_or_404()

    if reservation.status != ReservationRequest.STATUS_PENDING:
        action, message = reject_reservation(reservation)
        category = "warning"
        flash(message, category)
        return render_template("acao_admin.html", reservation=reservation, action=action)

    if request.method == "POST":
        reason = request.form.get("reason", "")
        action, message = reject_reservation(reservation, reason=reason)

        category = "success"
        if action == "approved":
            category = "warning"
        elif "erro" in message.lower():
            category = "warning"

        flash(message, category)
        return render_template("acao_admin.html", reservation=reservation, action=action)

    return render_template("admin_reject_reason.html", reservation=reservation)


with app.app_context():
    db.create_all()
    seed_spaces()
    seed_admin_settings()


if __name__ == "__main__":
    app.run(debug=True)
