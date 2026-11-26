"""Queue and deliver demo notices to the configured student email."""

import datetime as dt
import logging
import smtplib
import ssl
from email.message import EmailMessage
from threading import Event

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models import Defense, DefenseEmail, Thesis

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 3


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


def supersede(db: Session, thesis_id: int) -> None:
    db.execute(
        update(DefenseEmail)
        .where(DefenseEmail.thesis_id == thesis_id, DefenseEmail.status == "pending")
        .values(status="superseded")
    )


def enqueue(db: Session, settings: Settings, thesis: Thesis, defense: Defense, action: str) -> None:
    supersede(db, thesis.thesis_id)
    recipient = settings.gmail_test_recipient
    if thesis.student.email.casefold() != recipient.casefold():
        return
    when = defense.scheduled_at.strftime("%Y-%m-%d %H:%M")
    db.add(
        DefenseEmail(
            thesis_id=thesis.thesis_id,
            recipient=recipient,
            subject=f"[Demo] Thesis defense {action} | Thesis Management",
            body=(
                f"The defense for your demo thesis was {action}.\n\n"
                f"Date and time: {when} (Ecuador mainland time, UTC-05:00)\n"
                f"Duration: {defense.duration_minutes} minutes\n"
            ),
            available_at=_now(),
        )
    )


def _send(settings: Settings, recipient: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = settings.gmail_sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(
            settings.gmail_sender, settings.gmail_app_password.get_secret_value().replace(" ", "")
        )
        smtp.send_message(message)


def deliver_next(settings: Settings, sessions: sessionmaker[Session]) -> bool:
    now = _now()
    with sessions.begin() as db:
        notice = db.scalars(
            select(DefenseEmail)
            .where(DefenseEmail.status == "pending", DefenseEmail.available_at <= now)
            .order_by(DefenseEmail.available_at, DefenseEmail.email_id)
            .limit(1)
            .with_for_update(skip_locked=True)
        ).first()
        if notice is None:
            return False
        if notice.recipient != settings.gmail_test_recipient:
            notice.status = "superseded"
            return True
        if notice.attempts >= MAX_ATTEMPTS:
            notice.status = "failed"
            notice.last_error = "Delivery outcome unknown after the final attempt"
            return True
        notice.attempts += 1
        notice.available_at = now + dt.timedelta(minutes=2)
        email_id, attempt = notice.email_id, notice.attempts
        message = (notice.recipient, notice.subject, notice.body)

    error = None
    retryable = False
    try:
        _send(settings, *message)
    except smtplib.SMTPResponseException as exc:
        error = f"Gmail SMTP returned {exc.smtp_code}"
        retryable = 400 <= exc.smtp_code < 500
    except smtplib.SMTPRecipientsRefused as exc:
        code, _ = next(iter(exc.recipients.values()))
        error = f"SMTP rejected recipient ({code})"
        retryable = 400 <= code < 500
    except (ssl.SSLCertVerificationError, smtplib.SMTPNotSupportedError):
        error = "Gmail secure connection or authentication unavailable"
    except OSError:
        error = "Gmail connection failed"
        retryable = True

    result = {"status": "accepted", "last_error": error}
    if error:
        logger.warning("Defense email %s attempt %s failed: %s", email_id, attempt, error)
        result["status"] = "failed"
        if retryable and attempt < MAX_ATTEMPTS:
            result.update(
                status="pending", available_at=_now() + dt.timedelta(seconds=30 * attempt)
            )
    else:
        logger.info("Gmail accepted defense email %s", email_id)

    with sessions.begin() as db:
        db.execute(
            update(DefenseEmail)
            .where(
                DefenseEmail.email_id == email_id,
                DefenseEmail.status == "pending",
                DefenseEmail.attempts == attempt,
            )
            .values(**result)
        )
    return True


def run_worker(stop: Event, settings: Settings, sessions: sessionmaker[Session]) -> None:
    while not stop.is_set():
        try:
            if deliver_next(settings, sessions):
                continue
        except SQLAlchemyError:
            logger.exception("Could not process defense email queue")
        stop.wait(5)
