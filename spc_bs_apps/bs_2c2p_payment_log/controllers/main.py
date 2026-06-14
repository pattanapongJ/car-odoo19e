# -*- coding: utf-8 -*-
import json
import logging
import pprint

from odoo import http
from odoo.http import request
from odoo.addons.payment_2c2p.controllers.main import To_C_To_PController

_logger = logging.getLogger(__name__)


def _build_log_vals(log_type, post):
    return {
        'log_type': log_type,
        'reference': post.get('order_id') or post.get('reference', ''),
        'payment_status': post.get('payment_status', ''),
        'transaction_ref': post.get('transaction_ref', ''),
        'channel_response': post.get('channel_response_desc', ''),
        'raw_data': json.dumps(post, indent=2, default=str),
    }


class BsTo_C_To_PController(To_C_To_PController):

    @http.route(
        To_C_To_PController._notify_url,
        type='http', auth='public', methods=['POST'],
        csrf=False, save_session=False,
    )
    def to_c_to_p_notify(self, **post):
        _logger.info('2c2p Backend Webhook received: %s', pprint.pformat(post))
        try:
            request.env['bs.payment.2c2p.log'].sudo().create(
                _build_log_vals('notify', post)
            )
        except Exception:
            _logger.exception('2c2p: failed to write notify log')
        return super().to_c_to_p_notify(**post)

    @http.route(
        To_C_To_PController._return_url,
        type='http', auth='public', methods=['POST', 'GET'],
        csrf=False, website=True, save_session=False,
    )
    def to_c_to_p_return(self, **post):
        _logger.info('2c2p Frontend Return received: %s', pprint.pformat(post))
        try:
            request.env['bs.payment.2c2p.log'].sudo().create(
                _build_log_vals('return', post)
            )
        except Exception:
            _logger.exception('2c2p: failed to write return log')
        return super().to_c_to_p_return(**post)
