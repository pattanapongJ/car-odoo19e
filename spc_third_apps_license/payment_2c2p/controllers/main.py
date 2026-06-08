# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    See LICENSE file for full copyright and licensing details.
#################################################################################

import logging
import pprint

from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class To_C_To_PController(http.Controller):
    _notify_url = '/payment/2c2p/notify/'
    _return_url = '/payment/2c2p/return/'

    @http.route(_notify_url, type='http', auth='public', methods=['POST'], csrf=False, save_session=False)
    def to_c_to_p_notify(self, **post):
        _logger.info(
            'Beginning 2c2p notify form_feedback with post data %s', pprint.pformat(post))
        tx_sudo = request.env['payment.transaction'].sudo().search([
            ('reference', '=', post.get('order_id'))
        ])
        if tx_sudo and tx_sudo.state != 'done':
            try:
                post.update({
                    'reference': post.get('order_id')
                })
                request.env['payment.transaction'].sudo()._process(
                    'to_c_to_p', post)
            except ValidationError:
                _logger.exception('Unable to validate the 2C2P Payment')

    @http.route(_return_url, type='http', auth="public", methods=['POST', 'GET'], csrf=False, website=True, save_session=False)
    def to_c_to_p_return(self, **post):
        _logger.info(
            'Beginning 2c2p return response form_feedback with post data %s', pprint.pformat(post))
        try:
            post.update({
                'reference': post.get('order_id')
            })
            request.env['payment.transaction'].sudo()._process(
                'to_c_to_p', post)
        except ValidationError:
            _logger.exception('Unable to validate the 2C2P Payment')
        return request.redirect('/payment/status')
