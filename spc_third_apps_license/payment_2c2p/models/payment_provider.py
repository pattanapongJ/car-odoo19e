# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    See LICENSE file for full copyright and licensing details.
#################################################################################


from odoo import api, fields, models, _
from odoo.addons.payment_2c2p.const import Available2c2pCurrency


class AcquirerTo_C_To_P(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('to_c_to_p', '2c2p')],
        ondelete={'to_c_to_p': 'cascade'})
    to_c_to_p_merchant_id = fields.Char(
        '2c2p Merchant ID', required_if_provider='to_c_to_p', groups='base.group_user')
    to_c_to_p_secret_key = fields.Char(
        '2c2p Secret Key', required_if_provider='to_c_to_p', groups='base.group_user')

    def _get_supported_currencies(self):
        """ Override of `payment` to return the supported currencies. """
        supported_currencies = super()._get_supported_currencies()
        if self.code == 'to_c_to_p':
            supported_currencies = supported_currencies.filtered(
                lambda c: c.name in Available2c2pCurrency
            )
        return supported_currencies

    def _get_to_c_to_p_urls(self):
        return 'https://t.2c2p.com/RedirectV3/Payment' \
            if self.state == "enabled" else \
            'https://demo2.2c2p.com/2C2PFrontEnd/RedirectV3/payment'
