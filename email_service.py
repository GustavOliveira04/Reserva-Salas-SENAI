from flask import current_app, render_template
from flask_mail import Message

from models import ReservationRequest


def _mail_configured():
    username = current_app.config.get("MAIL_USERNAME") or ""
    password = current_app.config.get("MAIL_PASSWORD") or ""
    admin_email = (current_app.config.get("ADMIN_EMAIL") or "").strip()
    placeholders = {"seu-email@gmail.com", "sua-senha-de-app", "", "admin@escola.edu.br"}
    return (
        username not in placeholders
        and password not in placeholders
        and admin_email not in placeholders
    )


def _require_mail():
    if not _mail_configured():
        raise RuntimeError(
            "Configure no .env: ADMIN_EMAIL (quem recebe solicitações), "
            "MAIL_USERNAME e MAIL_PASSWORD (conta que envia os e-mails)."
        )


def send_admin_request_email(request: ReservationRequest):
    """Envia a solicitação para o e-mail do administrador."""
    _require_mail()
    from app import mail

    base_url = current_app.config["BASE_URL"]
    approve_url = f"{base_url}/aprovar/{request.token}"
    reject_url = f"{base_url}/recusar/{request.token}"

    html_body = render_template(
        "emails/admin_request.html",
        request=request,
        approve_url=approve_url,
        reject_url=reject_url,
    )

    msg = Message(
        subject=f"Nova solicitação de reserva — {request.space.name}",
        recipients=[current_app.config["ADMIN_EMAIL"]],
        html=html_body,
    )
    mail.send(msg)
    return True


def send_admin_password_reset_email(reset_url):
    """Envia o link de redefinição de senha para o e-mail do administrador."""
    _require_mail()
    from app import mail

    html_body = render_template("emails/admin_password_reset.html", reset_url=reset_url)
    msg = Message(
        subject="Redefinição de senha — Reserva de Espaços",
        recipients=[current_app.config["ADMIN_EMAIL"]],
        html=html_body,
    )
    mail.send(msg)
    return True


def send_professor_approved_email(request: ReservationRequest):
    """Envia feedback de aprovação para o e-mail informado no formulário."""
    _require_mail()
    from app import mail

    html_body = render_template("emails/professor_approved.html", request=request)
    msg = Message(
        subject=f"Reserva aprovada — {request.space.name}",
        recipients=[request.professor_email],
        html=html_body,
    )
    mail.send(msg)
    return True


def send_professor_rejected_email(request: ReservationRequest):
    """Envia feedback de recusa para o e-mail informado no formulário."""
    _require_mail()
    from app import mail

    html_body = render_template("emails/professor_rejected.html", request=request)
    msg = Message(
        subject=f"Reserva recusada — {request.space.name}",
        recipients=[request.professor_email],
        html=html_body,
    )
    mail.send(msg)
    return True
