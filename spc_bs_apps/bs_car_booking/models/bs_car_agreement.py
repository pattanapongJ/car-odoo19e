# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import fields, models


class BsCarAgreement(models.Model):
    """Admin-configurable agreement/policy the customer must accept (T&C,
    Refund Policy, Cancellation Policy, ...). Each links to a website page."""
    _name = 'bs.car.agreement'
    _description = 'Booking Agreement / Policy'
    _order = 'sequence, id'

    name = fields.Char('Agreement', required=True, translate=True,
                       help='Internal name, e.g. "Terms & Conditions".')
    cta_label = fields.Char('Checkbox Label', required=True, translate=True,
                            help='Text shown next to the checkbox, e.g. '
                                 '"I accept the Terms & Conditions".')
    page_url = fields.Char('Policy Page URL', help='Website page with the full '
                           'text, e.g. /terms. The label links to it.')
    applies_to = fields.Selection([
        ('individual', 'Individual'),
        ('company', 'Company'),
        ('both', 'Both'),
    ], string='Applies To', default='both', required=True)
    required = fields.Boolean('Required', default=True,
                              help='Must be ticked to continue.')
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)

    def _matches(self, customer_type):
        self.ensure_one()
        return self.applies_to in ('both', customer_type)


class BsCarBookingAgreement(models.Model):
    """Records that a booking's customer accepted a given agreement, and when
    (legal audit trail, like the PDPA consent)."""
    _name = 'bs.car.booking.agreement'
    _description = 'Booking Agreement Acceptance'
    _order = 'sequence, id'

    booking_id = fields.Many2one('bs.car.booking', string='Booking',
                                 required=True, ondelete='cascade', index=True)
    agreement_id = fields.Many2one('bs.car.agreement', string='Agreement',
                                   required=True, ondelete='restrict')
    name = fields.Char(related='agreement_id.name', store=True)
    sequence = fields.Integer(related='agreement_id.sequence', store=True)
    accepted = fields.Boolean('Accepted', default=False)
    accepted_date = fields.Datetime('Accepted On', readonly=True)

    _sql_constraints = [
        ('uniq_booking_agreement', 'unique(booking_id, agreement_id)',
         'This agreement is already recorded for the booking.'),
    ]
