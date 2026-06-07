# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    See LICENSE file for full copyright and licensing details.
#################################################################################

import logging
import hmac
import hashlib
from werkzeug import urls

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_2c2p.const import Available2c2pCurrency
from odoo.addons.payment_2c2p.controllers.main import To_C_To_PController

_logger = logging.getLogger(__name__)


class TxTo_C_To_P(models.Model):
    _inherit = 'payment.transaction'

    @api.model
    def _compute_reference(self, provider_code, prefix=None, separator='-', **kwargs):
        if provider_code == 'to_c_to_p':
            if not prefix:
                prefix = self.sudo()._compute_reference_prefix(separator, **kwargs) or None
            prefix = payment_utils.singularize_reference_prefix(
                prefix=prefix, separator=separator)
        return super()._compute_reference(
            provider_code, prefix=prefix, separator=separator, **kwargs
        )

    @staticmethod
    def get_12_char_amount_for_2c2p(amount):
        return str(format(amount, '.2f')).replace(".", "").rjust(12, '0')

    @staticmethod
    def get_HMACSHA1_has_value(data, keys, secretKey):
        res = ''
        if data and secretKey:
            for k in keys:
                res += data.get(k, '')
            hmac_data = hmac.new(str(secretKey).encode(), str(
                res).encode('UTF-8'), hashlib.sha1)
            res = hmac_data.hexdigest()
        return res

    def _generate_form_values(self):
        vals = dict()
        try:
            website = self.env['website'].sudo().get_current_website()
            base_url = website.get_base_url()
        except:
            base_url = self.get_base_url()
        currency_id = self.currency_id.name
        vals['data'] = vals['version'] = "6.9"
        vals['reference'] = vals['invoice_no'] = self.reference
        vals['user_defined_5'] = currency_id
        vals['currency_name'] = currency_id
        vals['merchant_id'] = self.provider_id.to_c_to_p_merchant_id
        vals['payment_description'] = f"Payment for: {vals['reference']}"
        vals['order_id'] = self.reference
        vals['amount'] = self.get_12_char_amount_for_2c2p(self.amount)
        vals['currency'] = Available2c2pCurrency.get(currency_id, (''))[0]
        vals['user_defined_1'] = f"{self.partner_id.id}"
        vals['user_defined_2'] = self.partner_name
        vals['user_defined_3'] = self.partner_email
        vals['user_defined_4'] = self.partner_phone
        vals['result_url_1'] = urls.url_join(
            base_url, To_C_To_PController._return_url)
        vals['result_url_2'] = urls.url_join(
            base_url, To_C_To_PController._notify_url)
        vals['tx_url'] = self.provider_id._get_to_c_to_p_urls()
        keys = ('version', 'merchant_id', 'payment_description', 'order_id', 'invoice_no', 'currency', 'amount', 'user_defined_1',
                'user_defined_2', 'user_defined_3', 'user_defined_4', 'user_defined_5', 'result_url_1', 'result_url_2')
        vals['hash_value'] = self.get_HMACSHA1_has_value(
            vals, keys, self.provider_id.to_c_to_p_secret_key)
        return vals

    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'to_c_to_p':
            return res
        tx_values = self._generate_form_values()
        return tx_values

    def _extract_amount_data(self, payment_data):
        if self.provider_code != 'to_c_to_p':
            return super()._extract_amount_data(payment_data)
        return None

    def _apply_updates(self, payment_data):
        if self.provider_code != 'to_c_to_p':
            return super()._apply_updates(payment_data)
        status = payment_data.get('payment_status')
        vals = {
            'provider_reference': payment_data.get('transaction_ref'),
        }
        self.write(vals)
        if status == "000":
            self._set_done()
        elif status == "001":
            self._set_pending()
        elif status == "003":
            self._set_canceled()
        else:
            state_message = _('2P2C: Error: %s') % payment_data.get(
                'channel_response_desc')
            self._set_error(state_message)
            _logger.warning(state_message)
