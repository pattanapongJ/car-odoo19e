# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

import logging
import secrets
import string
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BsCarBookingOtp(models.Model):
    _name = 'bs.car.booking.otp'
    _description = 'Car Booking OTP Verification'
    _order = 'id desc'

    phone = fields.Char('Phone Number', required=True, index=True)
    otp_code = fields.Char('OTP Code', required=True)
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

    # SMS tracking
    sms_id = fields.Many2one('sms.sms', string='SMS Record')

    @api.model
    def _generate_otp(self, length=6):
        return ''.join(secrets.choice(string.digits) for _ in range(length))

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
    def send_otp(self, phone, booking_id=None, purpose='booking'):
        """Send OTP via SMS. The message body is resolved from the purpose's
        sms.template, falling back to sms_fallback_body if the template is missing.

        Args:
            phone (str): Customer phone number.
            booking_id (int): ID of the related bs.car.booking record.
            purpose (str): Purpose code defined in bs.car.booking.otp.purpose.

        Returns:
            bs.car.booking.otp record.
        """
        # 1. Validate purpose
        purpose_rec = self._get_purpose(purpose)

        # 2. Prepare OTP
        phone = phone.strip().replace(' ', '')
        otp_code = self._generate_otp()
        expire_datetime = fields.Datetime.now() + timedelta(minutes=5)

        otp_record = self.create({
            'phone': phone,
            'otp_code': otp_code,
            'booking_id': booking_id,
            'purpose_id': purpose_rec.id,
            'expire_datetime': expire_datetime,
        })

        # 3. Resolve SMS body from template or fallback
        template = purpose_rec.sms_template_id
        if template:
            body = template._render_field('body', [otp_record.id])[otp_record.id]
        elif purpose_rec.sms_fallback_body:
            body = purpose_rec.sms_fallback_body % {'otp_code': otp_code}
            _logger.warning(
                'SMS template missing for purpose [%s], using fallback.', purpose
            )
        else:
            raise UserError(
                _("No SMS template or fallback body configured for purpose '%s'. "
                  "Please check Settings > Car Booking > OTP Purposes.")
                % purpose_rec.name
            )

        # 4. Send SMS
        try:
            sms_record = self.env['sms.sms'].create({'number': phone, 'body': body})
            otp_record.sms_id = sms_record.id
            sms_record.send()
            _logger.info(
                'OTP SMS [%s] sent to %s (sms_id=%s)', purpose, phone, sms_record.id
            )
        except Exception as e:
            _logger.error(
                'Failed to send OTP SMS [%s] to %s: %s', purpose, phone, str(e)
            )

        return otp_record

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

        if self.otp_code == code.strip():
            self.state = 'verified'
            self.verified_datetime = fields.Datetime.now()
            return {'success': True, 'message': _('Phone verified successfully!')}

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
