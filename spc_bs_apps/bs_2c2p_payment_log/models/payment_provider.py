# -*- coding: utf-8 -*-
from odoo import api, models


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    @api.onchange('state')
    def _onchange_state_switch_is_published(self):
        if self.code == 'to_c_to_p':
            self.is_published = self.state in ('enabled', 'test')
        else:
            super()._onchange_state_switch_is_published()

    @api.model
    def _setup_provider(self, provider_code, **kwargs):
        super()._setup_provider(provider_code, **kwargs)
        if provider_code == 'to_c_to_p':
            self.search([
                ('code', '=', 'to_c_to_p'),
                ('state', 'in', ['enabled', 'test']),
            ]).write({'is_published': True})
