# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

import logging
import secrets
import string
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class BsCarBookingOtp(models.Model):
    _name = 'bs.car.booking.otp'
    _description = 'Car Booking OTP Verification'
    _order = 'id desc'

    phone = fields.Char('Phone Number', required=True, index=True)
    otp_code = fields.Char('OTP Code', required=True)
    booking_id = fields.Many2one('bs.car.booking', string='Booking', ondelete='cascade')
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
        """Generate a cryptographically-secure numeric OTP code."""
        return ''.join(secrets.choice(string.digits) for _ in range(length))

    @api.model
    def send_otp(self, phone, booking_id=None):
        """Send OTP to the given phone number via SMS.
        
        This uses Odoo's built-in SMS gateway (IAP or third-party provider).
        For production, configure an SMS provider in Settings > SMS.
        
        Returns the OTP record.
        """
        # Clean phone number
        phone = phone.strip().replace(' ', '')
        
        # Generate OTP
        otp_code = self._generate_otp()
        expire_minutes = 5
        expire_datetime = fields.Datetime.now() + timedelta(minutes=expire_minutes)
        
        # Create OTP record
        otp_record = self.create({
            'phone': phone,
            'otp_code': otp_code,
            'booking_id': booking_id,
            'expire_datetime': expire_datetime,
        })
        
        # Send SMS via Odoo's SMS gateway
        message = _('Your car booking verification code is: %s. Valid for %s minutes.') % (
            otp_code, expire_minutes
        )
        
        try:
            sms_record = self.env['sms.sms'].create({
                'number': phone,
                'body': message,
            })
            otp_record.sms_id = sms_record.id
            _logger.info('OTP SMS sent to %s (sms_id=%s)', phone, sms_record.id)
        except Exception as e:
            _logger.error('Failed to send OTP SMS to %s: %s', phone, str(e))
            # Still return OTP record - in dev mode user can see OTP in log
            # In production, the SMS gateway must be configured
        
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
