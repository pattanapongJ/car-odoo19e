# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

import logging
import hashlib
import secrets
import string
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import consteq
from odoo.tools.mail import formataddr

_logger = logging.getLogger(__name__)


class BsCarBookingOtp(models.Model):
    _name = 'bs.car.booking.otp'
    _description = 'Car Booking OTP Verification'
    _order = 'id desc'

    phone = fields.Char('Phone Number', required=True, index=True)
    # Delivery channel of THIS code. SMS verifies the phone number itself;
    # email is the alternative while no SMS gateway is available (e.g. Twilio
    # registration pending). The website mode (``website.bs_otp_channel``,
    # Settings → Website → Car Booking) decides what is offered: 'sms'/'email'
    # fix the channel, 'both' lets the customer choose.
    channel = fields.Selection([
        ('sms', 'SMS'),
        ('email', 'Email'),
    ], default='sms', required=True, index=True)
    email = fields.Char('Email', index=True,
                        help='Destination address when the OTP is sent by email.')
    otp_code = fields.Char('OTP Code', compute='_compute_otp_code',
                           help='Runtime-only value used while rendering SMS/email templates.')
    otp_hash = fields.Char('OTP Hash', copy=False)
    otp_salt = fields.Char('OTP Salt', copy=False)
    booking_id = fields.Many2one('bs.car.booking', string='Booking', ondelete='cascade')
    # Why purpose_id (not Selection): purpose list is admin-managed in the DB.
    # New flows can be added from Settings > Car Booking > OTP Purposes without code change.
    # Each purpose carries its own sms.template and fallback message.
    purpose_id = fields.Many2one(
        'bs.car.booking.otp.purpose',
        string='Purpose',
        ondelete='restrict',
        index=True,
    )
    purpose_code = fields.Char(
        related='purpose_id.code',
        string='Purpose Code',
        store=True,
        index=True,
    )
    state = fields.Selection([
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('expired', 'Expired'),
        ('failed', 'Failed'),
    ], default='pending', required=True, copy=False)

    attempts = fields.Integer('Attempts', default=0)
    max_attempts = fields.Integer('Max Attempts', default=3)
    expire_datetime = fields.Datetime('Expires At', required=True)
    verified_datetime = fields.Datetime('Verified At')

    # Delivery tracking
    sms_id = fields.Many2one('sms.sms', string='SMS Record')
    mail_id = fields.Many2one('mail.mail', string='Email Record')

    validity_minutes = fields.Integer(compute='_compute_validity_minutes',
                                      help='Lifetime of this code, for message rendering.')

    @api.depends('expire_datetime', 'create_date')
    def _compute_validity_minutes(self):
        for otp in self:
            start = otp.create_date or fields.Datetime.now()
            if otp.expire_datetime and otp.expire_datetime > start:
                otp.validity_minutes = max(round((otp.expire_datetime - start).total_seconds() / 60), 1)
            else:
                otp.validity_minutes = self._get_validity_minutes()

    @api.model
    def _get_validity_minutes(self, website=None):
        """Code lifetime in minutes: the website's setting
        (``website.bs_otp_expiry_minutes``), falling back to the System
        Parameter ``bs_car_booking.otp_expiry_minutes`` (default 5) for
        website-less contexts."""
        website = website or self.env['website'].get_current_website()
        if website and website.bs_otp_expiry_minutes > 0:
            return website.bs_otp_expiry_minutes
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'bs_car_booking.otp_expiry_minutes', '5')
        try:
            return max(int(raw), 1)
        except (TypeError, ValueError):
            return 5

    @api.model
    def _generate_otp(self, length=6):
        return ''.join(secrets.choice(string.digits) for _ in range(length))

    @api.model
    def _hash_otp(self, otp_code, salt):
        return hashlib.sha256(f'{salt}:{otp_code}'.encode()).hexdigest()

    def _compute_otp_code(self):
        """Expose the raw OTP only during the SMS rendering call that created it."""
        plain_codes = self.env.context.get('bs_otp_plain_codes') or {}
        for otp in self:
            otp.otp_code = plain_codes.get(otp.id) or ''

    def init(self):
        """Clear legacy plaintext OTP values left by earlier stored-field versions."""
        self.env.cr.execute("""
            SELECT 1
              FROM information_schema.columns
             WHERE table_name = %s
               AND column_name = %s
        """, [self._table, 'otp_code'])
        if self.env.cr.fetchone():
            self.env.cr.execute(f'UPDATE "{self._table}" SET otp_code = NULL WHERE otp_code IS NOT NULL')

    @api.model
    def _get_purpose(self, purpose_code):
        """Resolve and validate purpose by code. Raises UserError if not supported."""
        purpose_rec = self.env['bs.car.booking.otp.purpose'].search(
            [('code', '=', purpose_code), ('active', '=', True)],
            limit=1,
        )
        if not purpose_rec:
            raise UserError(
                _("OTP purpose '%s' is not configured or not active. "
                  "Please check Settings > Car Booking > OTP Purposes.")
                % purpose_code
            )
        return purpose_rec

    @api.model
    def _get_otp_channel(self, website=None):
        """Delivery mode configured for *website* (defaults to the current
        website — pass the booking's website from backend/cron contexts where
        ``get_current_website`` would return the wrong one).
        'sms' / 'email': the channel is fixed ('email' while no SMS gateway
        is active). 'both': the customer picks, SMS preselected."""
        website = website or self.env['website'].get_current_website()
        channel = (website.bs_otp_channel or 'sms').strip().lower()
        return channel if channel in ('sms', 'email', 'both') else 'sms'

    @api.model
    def send_otp(self, phone, booking_id=None, purpose='booking', channel=None, email=None):
        """Send an OTP via SMS or email. The message body is resolved from the
        purpose's sms/mail template, falling back to the purpose's fallback
        body when the template is missing.

        Args:
            phone (str): Customer phone number (always stored — it is the
                identity being verified, even when delivery is by email).
            booking_id (int): ID of the related bs.car.booking record.
            purpose (str): Purpose code defined in bs.car.booking.otp.purpose.
            channel (str): 'sms' or 'email'; defaults to the configured channel.
            email (str): Destination address, required for the email channel.

        Returns:
            bs.car.booking.otp record.
        """
        # 1. Validate purpose + channel
        purpose_rec = self._get_purpose(purpose)
        channel = channel or self._get_otp_channel()
        email = (email or '').strip()
        if channel == 'email' and not email:
            raise UserError(_('An email address is required to send the verification code by email.'))

        # 2. Prepare OTP (lifetime follows the booking's website setting)
        booking_website = (self.env['bs.car.booking'].sudo().browse(booking_id).website_id
                           if booking_id else None)
        # Stored normalised so throttle counts and gateway numbers are uniform.
        phone = self.env['bs.car.booking']._normalize_phone(phone)
        otp_code = self._generate_otp()
        otp_salt = secrets.token_hex(16)
        expire_datetime = fields.Datetime.now() + timedelta(
            minutes=self._get_validity_minutes(booking_website))

        otp_record = self.create({
            'phone': phone,
            'channel': channel,
            'email': email or False,
            'otp_hash': self._hash_otp(otp_code, otp_salt),
            'otp_salt': otp_salt,
            'booking_id': booking_id,
            'purpose_id': purpose_rec.id,
            'expire_datetime': expire_datetime,
        })

        # 3. Deliver (failures are logged, never block the funnel)
        if channel == 'email':
            otp_record._send_by_email(purpose_rec, otp_code)
        else:
            otp_record._send_by_sms(purpose_rec, otp_code)
        return otp_record

    def _send_by_sms(self, purpose_rec, otp_code):
        self.ensure_one()
        template = purpose_rec.sms_template_id
        if template:
            body = template.with_context(
                bs_otp_plain_codes={self.id: otp_code},
            )._render_field('body', [self.id])[self.id]
        elif purpose_rec.sms_fallback_body:
            body = purpose_rec.sms_fallback_body % {
                'otp_code': otp_code, 'validity_minutes': self.validity_minutes}
            _logger.warning(
                'SMS template missing for purpose [%s], using fallback.', purpose_rec.code
            )
        else:
            raise UserError(
                _("No SMS template or fallback body configured for purpose '%s'. "
                  "Please check Settings > Car Booking > OTP Purposes.")
                % purpose_rec.name
            )
        try:
            sms_record = self.env['sms.sms'].create({'number': self.phone, 'body': body})
            self.sms_id = sms_record.id
            sms_record.send()
            _logger.info(
                'OTP SMS [%s] sent to %s (sms_id=%s)', purpose_rec.code, self.phone, sms_record.id
            )
        except Exception as e:
            _logger.error(
                'Failed to send OTP SMS [%s] to %s: %s', purpose_rec.code, self.phone, str(e)
            )

    def _get_sender_company(self):
        """The brand identity behind this OTP: the booking website's company,
        falling back to the booking's company, then the current company."""
        self.ensure_one()
        booking = self.booking_id
        return (booking.website_id.company_id
                or booking.company_id
                or self.env.company).sudo()

    def _get_sender_brand(self):
        """Customer-facing brand name for emails (From display name and
        signature): the website name ("Hongqi Thailand"), NOT the company
        legal name — that one belongs on tax invoices, not marketing mails."""
        self.ensure_one()
        return (self.booking_id.website_id.name
                or self._get_sender_company().name or '')

    def _get_sender_site(self):
        """Human-readable site the message 'comes from' (e.g.
        'hongqithailand.com'): the booking website's domain without the
        scheme, else the website name, else the company name."""
        self.ensure_one()
        website = self.booking_id.website_id
        domain = (website.domain or '').strip()
        if domain:
            return domain.split('//')[-1].strip('/')
        return website.name or self._get_sender_company().name or ''

    def _get_email_from(self):
        """Sender for OTP mails: the booking website's company address, so
        each brand site mails from its own identity. Falls back to the
        booking/current company, then the system default-from. Without an
        explicit sender, sends from the public website user crash with
        "You must either provide a sender address explicitly or configure
        mail.catchall.domain/mail.default.from"."""
        self.ensure_one()
        company = self._get_sender_company()
        email = (company.email
                 or self.env['ir.mail_server'].sudo()._get_default_from_address())
        if not email:
            _logger.warning(
                'No sender address for OTP mails: set the email of company '
                '"%s" or the mail.default.from system parameter.', company.name)
            return False
        # Display name = brand (website name), address = company mailbox.
        brand = self._get_sender_brand()
        return formataddr((brand, email)) if brand else email

    def _send_by_email(self, purpose_rec, otp_code):
        self.ensure_one()
        template = purpose_rec.mail_template_id
        if template:
            ctx_template = template.with_context(bs_otp_plain_codes={self.id: otp_code})
            subject = ctx_template._render_field('subject', [self.id])[self.id]
            body_html = ctx_template._render_field('body_html', [self.id])[self.id]
        elif purpose_rec.mail_fallback_body:
            subject = _('%s — your verification code') % (self._get_sender_brand() or 'Verification')
            text = purpose_rec.mail_fallback_body % {
                'otp_code': otp_code, 'validity_minutes': self.validity_minutes}
            body_html = (
                '<div style="font-family:Arial,sans-serif;font-size:14px;color:#161616;">'
                '<p>%s</p>'
                '<p style="font-size:30px;font-weight:bold;letter-spacing:6px;margin:16px 0;">%s</p>'
                '</div>'
            ) % (text, otp_code)
            _logger.warning(
                'Email template missing for purpose [%s], using fallback.', purpose_rec.code
            )
        else:
            raise UserError(
                _("No email template or fallback body configured for purpose '%s'. "
                  "Please check Settings > Car Booking > OTP Purposes.")
                % purpose_rec.name
            )
        try:
            vals = {
                'subject': subject,
                'body_html': body_html,
                'email_to': self.email,
                # The body carries the one-time code: drop the record once
                # delivered so the code is not retained in the mail queue.
                # (Failed sends keep the record for delivery debugging.)
                'auto_delete': True,
            }
            email_from = self._get_email_from()
            if email_from:
                vals['email_from'] = email_from
            mail = self.env['mail.mail'].sudo().create(vals)
            self.mail_id = mail.id
            mail.send(raise_exception=False)
            _logger.info(
                'OTP email [%s] sent to %s (mail_id=%s)', purpose_rec.code, self.email, mail.id
            )
        except Exception as e:
            _logger.error(
                'Failed to send OTP email [%s] to %s: %s', purpose_rec.code, self.email, str(e)
            )

    def verify_otp(self, code):
        """Verify the OTP code entered by the user."""
        self.ensure_one()

        if self.state == 'verified':
            return {'success': False, 'error': _('OTP already verified.')}

        if self.state == 'expired':
            return {'success': False, 'error': _('OTP has expired. Please request a new one.')}

        if fields.Datetime.now() > self.expire_datetime:
            self.state = 'expired'
            return {'success': False, 'error': _('OTP has expired. Please request a new one.')}

        self.attempts += 1

        if self.attempts > self.max_attempts:
            self.state = 'failed'
            return {'success': False, 'error': _('Too many attempts. Please request a new OTP.')}

        entered_code = (code or '').strip()
        if self.otp_hash and consteq(self.otp_hash, self._hash_otp(entered_code, self.otp_salt)):
            self.state = 'verified'
            self.verified_datetime = fields.Datetime.now()
            message = (_('Email verified successfully!') if self.channel == 'email'
                       else _('Phone verified successfully!'))
            return {'success': True, 'message': message}

        return {'success': False, 'error': _('Invalid OTP code. Please try again. (%s/%s attempts)') % (
            self.attempts, self.max_attempts
        )}

    @api.model
    def cleanup_expired(self):
        """Cron job to mark expired OTPs."""
        expired = self.search([
            ('state', '=', 'pending'),
            ('expire_datetime', '<', fields.Datetime.now()),
        ])
        expired.write({'state': 'expired'})
        return True
