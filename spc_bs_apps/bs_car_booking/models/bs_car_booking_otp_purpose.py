# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class BsCarBookingOtpPurpose(models.Model):
    _name = 'bs.car.booking.otp.purpose'
    _description = 'OTP Purpose'
    _order = 'sequence, id'

    name = fields.Char(string='Purpose Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True, index=True)
    sms_template_id = fields.Many2one(
        'sms.template',
        string='SMS Template',
        domain=[('model', '=', 'bs.car.booking.otp')],
        help='SMS template used when sending OTP for this purpose.',
    )
    sms_fallback_body = fields.Text(
        string='SMS Fallback Message',
        help='Used when SMS template is missing. Use %(otp_code)s as placeholder.',
    )
    mail_template_id = fields.Many2one(
        'mail.template',
        string='Email Template',
        domain=[('model', '=', 'bs.car.booking.otp')],
        help='Email template used when sending OTP by email for this purpose.',
    )
    mail_fallback_body = fields.Text(
        string='Email Fallback Message',
        help='Used when the email template is missing. Use %(otp_code)s as placeholder.',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        'UNIQUE(code)',
        'Purpose code must be unique.',
    )

    @api.constrains('sms_fallback_body', 'mail_fallback_body')
    def _check_fallback_placeholder(self):
        for rec in self:
            for body in (rec.sms_fallback_body, rec.mail_fallback_body):
                if body and '%(otp_code)s' not in body:
                    raise ValidationError(
                        _("Fallback message must contain %(otp_code)s placeholder.")
                    )
