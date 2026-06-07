# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # Reverse link to the car booking that generated this lead.
    bs_car_booking_id = fields.Many2one('bs.car.booking', string='Car Booking',
                                        readonly=True, copy=False, index=True)

    def action_view_car_booking(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'bs.car.booking',
            'res_id': self.bs_car_booking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
