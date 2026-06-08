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
        string='Fallback Message',
        help='Used when SMS template is missing. Use %(otp_code)s as placeholder.',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Purpose code must be unique.'),
    ]

    @api.constrains('sms_fallback_body')
    def _check_fallback_placeholder(self):
        for rec in self:
            if rec.sms_fallback_body and '%(otp_code)s' not in rec.sms_fallback_body:
                raise ValidationError(
                    _("Fallback message must contain %(otp_code)s placeholder.")
                )
