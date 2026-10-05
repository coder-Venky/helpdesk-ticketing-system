import os
import pyotp
import hashlib
import time
from flask import current_app, render_template_string
from flask_mail import Message
from app.extensions import mail, db
from app.models.attachment import Notification


def generate_otp_secret():
    return pyotp.random_base32()


def get_totp(secret):
    return pyotp.TOTP(secret, interval=300)  # 5-minute window


def generate_email_otp(secret):
    totp = get_totp(secret)
    return totp.now()


def verify_email_otp(secret, otp):
    totp = get_totp(secret)
    return totp.verify(otp, valid_window=1)


def generate_reset_token(user_email):
    """Generate a time-limited password reset token."""
    secret = current_app.config.get('SECRET_KEY', 'dev-secret')
    expiry = int(time.time()) + current_app.config.get('PASSWORD_RESET_EXPIRY_SECONDS', 3600)
    data = f"{user_email}:{expiry}:{secret}"
    token = hashlib.sha256(data.encode()).hexdigest()
    return f"{hashlib.md5(user_email.encode()).hexdigest()}.{expiry}.{token}"


def verify_reset_token(token_str):
    """Validate a password reset token. Returns email or None."""
    try:
        parts = token_str.split('.')
        if len(parts) != 3:
            return None
        email_hash, expiry, provided_token = parts
        expiry = int(expiry)
        if time.time() > expiry:
            return None  # Expired
        return email_hash, expiry, provided_token
    except Exception:
        return None


def send_email(subject, recipients, html_body, text_body=None):
    """Send an email. Falls back to console logging in development."""
    if current_app.config.get('MAIL_SUPPRESS_SEND'):
        current_app.logger.info(f"[EMAIL MOCK] To: {recipients} | Subject: {subject}\n{html_body[:200]}")
        return True
    try:
        msg = Message(subject=subject, recipients=recipients, html=html_body, body=text_body)
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Email send failed: {e}")
        return False


def send_otp_email(user, otp):
    html = f"""
    <div style="font-family: Arial; max-width:500px; margin:auto; padding:20px; background:#0f172a; color:#e2e8f0; border-radius:12px;">
      <h2 style="color:#6366f1;">🔐 Your Login OTP</h2>
      <p>Hello <strong>{user.name}</strong>,</p>
      <p>Your One-Time Password is:</p>
      <div style="font-size:36px; font-weight:bold; color:#6366f1; text-align:center; 
                  padding:16px; background:#1e293b; border-radius:8px; letter-spacing:8px;">
        {otp}
      </div>
      <p style="color:#94a3b8; font-size:12px; margin-top:16px;">This OTP expires in 5 minutes. Do not share it.</p>
    </div>
    """
    return send_email('Your IT Help Desk OTP', [user.email], html)


def send_password_reset_email(user, reset_url):
    html = f"""
    <div style="font-family: Arial; max-width:500px; margin:auto; padding:20px; background:#0f172a; color:#e2e8f0; border-radius:12px;">
      <h2 style="color:#6366f1;">🔑 Password Reset Request</h2>
      <p>Hello <strong>{user.name}</strong>,</p>
      <p>Click the button below to reset your password. This link expires in 1 hour.</p>
      <a href="{reset_url}" style="display:block; text-align:center; margin:20px 0; padding:12px 24px; 
         background:#6366f1; color:#fff; text-decoration:none; border-radius:8px; font-weight:bold;">
        Reset Password
      </a>
      <p style="color:#94a3b8; font-size:12px;">If you didn't request this, ignore this email.</p>
    </div>
    """
    return send_email('Password Reset - IT Help Desk', [user.email], html)


def send_ticket_created_email(ticket, creator):
    html = f"""
    <div style="font-family: Arial; max-width:500px; margin:auto; padding:20px; background:#0f172a; color:#e2e8f0; border-radius:12px;">
      <h2 style="color:#10b981;">🎫 Ticket Created Successfully</h2>
      <p>Hello <strong>{creator.name}</strong>,</p>
      <p>Your support ticket has been created:</p>
      <div style="background:#1e293b; padding:16px; border-radius:8px; margin:12px 0;">
        <p><strong>Ticket #:</strong> {ticket.ticket_number}</p>
        <p><strong>Title:</strong> {ticket.title}</p>
        <p><strong>Priority:</strong> {ticket.priority.upper()}</p>
        <p><strong>Status:</strong> Open</p>
      </div>
      <p>Our team will review and respond shortly.</p>
    </div>
    """
    return send_email(f'Ticket Created: {ticket.ticket_number}', [creator.email], html)


def send_ticket_assigned_email(ticket, engineer):
    html = f"""
    <div style="font-family: Arial; max-width:500px; margin:auto; padding:20px; background:#0f172a; color:#e2e8f0; border-radius:12px;">
      <h2 style="color:#f59e0b;">📋 New Ticket Assigned to You</h2>
      <p>Hello <strong>{engineer.name}</strong>,</p>
      <p>A ticket has been assigned to you:</p>
      <div style="background:#1e293b; padding:16px; border-radius:8px; margin:12px 0;">
        <p><strong>Ticket #:</strong> {ticket.ticket_number}</p>
        <p><strong>Title:</strong> {ticket.title}</p>
        <p><strong>Priority:</strong> {ticket.priority.upper()}</p>
        <p><strong>Category:</strong> {ticket.category}</p>
      </div>
    </div>
    """
    return send_email(f'Ticket Assigned: {ticket.ticket_number}', [engineer.email], html)


def send_status_update_email(ticket, old_status, new_status):
    colors = {'open': '#6366f1', 'in_progress': '#f59e0b', 'resolved': '#10b981', 'closed': '#64748b'}
    color = colors.get(new_status, '#6366f1')
    creator = ticket.creator
    html = f"""
    <div style="font-family: Arial; max-width:500px; margin:auto; padding:20px; background:#0f172a; color:#e2e8f0; border-radius:12px;">
      <h2 style="color:{color};">🔄 Ticket Status Updated</h2>
      <p>Hello <strong>{creator.name}</strong>,</p>
      <p>Your ticket status has been updated:</p>
      <div style="background:#1e293b; padding:16px; border-radius:8px; margin:12px 0;">
        <p><strong>Ticket #:</strong> {ticket.ticket_number}</p>
        <p><strong>Title:</strong> {ticket.title}</p>
        <p><strong>Status:</strong> {old_status.replace('_',' ').title()} → <span style="color:{color};">{new_status.replace('_',' ').title()}</span></p>
      </div>
    </div>
    """
    if creator:
        return send_email(f'Status Update: {ticket.ticket_number}', [creator.email], html)


def create_notification(user_id, title, message, link=None, notif_type='info'):
    """Create an in-app notification record."""
    notif = Notification(user_id=user_id, title=title, message=message, link=link, notification_type=notif_type)
    db.session.add(notif)
    db.session.commit()
    return notif
