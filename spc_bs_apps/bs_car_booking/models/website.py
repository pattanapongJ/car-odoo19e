# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import fields, models


class Website(models.Model):
    _inherit = 'website'

    bs_otp_channel = fields.Selection(
        [
            ('sms', 'SMS only'),
            ('email', 'Email only'),
            ('both', 'Customer choice (SMS or Email)'),
        ],
        string='OTP Delivery Channel',
        default='sms',
        help='How booking verification codes are delivered for this website. '
             '"SMS only" / "Email only" fix the channel (use "Email only" while '
             'no SMS gateway, e.g. Twilio, is active). "Customer choice" shows '
             'a toggle on the booking form, SMS preselected.',
    )
    bs_booking_expire_hours = fields.Integer(
        string='Booking Expiry (hours)',
        default=72,
        help='Unpaid draft bookings older than this many hours are '
             'automatically expired by the nightly cron.',
    )
    bs_otp_expiry_minutes = fields.Integer(
        string='OTP Validity (minutes)',
        default=5,
        help='Lifetime of verification codes sent from this website. '
             'Shown in the SMS/email copy and drives the countdown.',
    )
    bs_otp_resend_seconds = fields.Integer(
        string='OTP Resend Cooldown (seconds)',
        default=30,
        help='Minimum wait between two codes for the same booking. '
             '0 disables the cooldown.',
    )
    bs_otp_max_per_hour = fields.Integer(
        string='OTP Hourly Cap (per contact)',
        default=5,
        help='Maximum codes per hour for one phone number or email address, '
             'counted across ALL bookings (abuse protection). 0 disables the '
             'cap. NOTE: the count is global but the cap value follows the '
             'booking website — keep it aligned across websites, an abuser '
             'enters via the most permissive one.',
    )
