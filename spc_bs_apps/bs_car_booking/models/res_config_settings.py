# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    bs_otp_channel = fields.Selection(
        related='website_id.bs_otp_channel',
        readonly=False,
    )
    bs_booking_expire_hours = fields.Integer(
        related='website_id.bs_booking_expire_hours',
        readonly=False,
    )
    bs_otp_expiry_minutes = fields.Integer(
        related='website_id.bs_otp_expiry_minutes',
        readonly=False,
    )
    bs_otp_resend_seconds = fields.Integer(
        related='website_id.bs_otp_resend_seconds',
        readonly=False,
    )
    bs_otp_max_per_hour = fields.Integer(
        related='website_id.bs_otp_max_per_hour',
        readonly=False,
    )
