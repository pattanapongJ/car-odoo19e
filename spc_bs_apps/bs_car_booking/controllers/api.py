# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

import logging

from werkzeug.urls import url_encode

from odoo import fields, http
from odoo.http import request
from odoo.tools import consteq
from odoo.tools import format_amount

_logger = logging.getLogger(__name__)


class BsCarBookingAPI(http.Controller):
    """JSON-RPC endpoints for the AJAX booking funnel."""

    def _booking_step_url(self, booking, step):
        return '/booking/%s/%s?%s' % (
            booking.id,
            step,
            url_encode({'access_token': booking._portal_ensure_token()}),
        )

    def _check_booking_token(self, booking, access_token=None):
        return bool(access_token and consteq(booking.access_token or '', access_token))

    # ── Live price for a configuration ──────────────────────────────────
    @http.route('/shop/car/price', type='jsonrpc', auth='public', website=True, methods=['POST'])
    def car_price(self, model_id, ptav_ids=None):
        """Return the live price for a selected attribute combination."""
        model = request.env['bs.car.model'].sudo().browse(int(model_id))
        if not model.exists() or not model.website_published or not model.active:
            return {'success': False, 'error': 'Unknown model.'}
        tmpl = model.product_tmpl_id
        currency = model.currency_id or request.env.company.currency_id
        if not tmpl:
            return {'success': True, 'price': model.base_price or 0.0,
                    'currency_id': currency.id}
        ptav_ids = [int(p) for p in (ptav_ids or [])]
        combo = request.env['product.template.attribute.value'].sudo().browse(ptav_ids)
        combo = combo.exists().filtered(lambda p: p.product_tmpl_id == tmpl)
        info = tmpl.sudo()._get_combination_info(combination=combo)
        price = info.get('price') or 0.0
        return {
            'success': True,
            'price': price,
            'price_formatted': format_amount(request.env, price, currency),
            'list_price': info.get('list_price'),
            'currency_id': currency.id,
        }

    # ── Create booking from configurator ────────────────────────────────
    @http.route('/shop/car/book', type='jsonrpc', auth='public', website=True, methods=['POST'])
    def car_book(self, model_id, ptav_ids=None, dealer_id=None, phone=None,
                 pdpa_consent=False, **kw):
        """Create a draft booking from the configurator and send the OTP.

        PDPA consent is captured here (before the OTP SMS is sent), so we never
        contact a customer who has not consented."""
        try:
            model = request.env['bs.car.model'].sudo().browse(int(model_id))
            if not model.exists() or not model.website_published or not model.active:
                return {'success': False, 'error': 'Unknown model.'}
            if not phone or len(phone.strip()) < 7:
                return {'success': False, 'error': 'Please enter a valid phone number.'}
            if not pdpa_consent:
                return {'success': False,
                        'error': 'Please accept the privacy policy (PDPA) to continue.'}
            dealer = request.env['bs.car.dealer'].sudo().browse(int(dealer_id or 0))
            if not dealer.exists() or not dealer.active or not dealer.website_published \
                    or model.brand_id not in dealer.brand_ids:
                return {'success': False, 'error': 'Please choose a valid dealer.'}

            booking = request.env['bs.car.booking'].sudo().create({
                'brand_id': model.brand_id.id,
                'model_id': model.id,
                'dealer_id': dealer.id,
                'customer_phone': phone.strip(),
                'deposit_amount': model.deposit_amount or 0.0,
                'currency_id': (model.currency_id or request.env.company.currency_id).id,
                'pdpa_consent': True,
                'pdpa_consent_date': fields.Datetime.now(),
            })
            booking._apply_configuration([int(p) for p in (ptav_ids or [])])
            booking.action_send_otp()
            token = booking._portal_ensure_token()
            return {
                'success': True,
                'booking_id': booking.id,
                'booking_ref': booking.name,
                'access_token': token,
                'redirect_url': self._booking_step_url(booking, 'verify'),
            }
        except Exception as e:  # noqa: BLE001
            _logger.exception('Failed to create booking')
            return {'success': False, 'error': str(e)}

    # ── Customer info step ──────────────────────────────────────────────
    @http.route('/shop/booking/info', type='jsonrpc', auth='public', website=True, methods=['POST'])
    def booking_info(self, booking_id, access_token=None, name=None, email=None,
                     nrc=None, address=None, **kw):
        """Save customer info, create the partner + sale order, go to deposit."""
        try:
            booking = request.env['bs.car.booking'].sudo().browse(int(booking_id))
            if not booking.exists():
                return {'success': False, 'error': 'Booking not found.'}
            if not self._check_booking_token(booking, access_token):
                return {'success': False, 'error': 'This booking link is no longer valid.'}
            if booking.state not in ('otp_verified', 'payment_pending'):
                return {'success': False, 'error': 'This booking is not ready for customer info.'}
            if not booking.phone_verified:
                return {'success': False, 'error': 'Please verify your phone first.'}
            if not name or not name.strip():
                return {'success': False, 'error': 'Full name is required.'}
            booking.write({
                'customer_name': name.strip(),
                'customer_email': (email or '').strip(),
                'customer_nrc': (nrc or '').strip(),
                'customer_address': (address or '').strip(),
            })
            booking._ensure_partner()
            booking._ensure_sale_order()
            booking._transition_to('payment_pending')
            return {'success': True, 'redirect_url': self._booking_step_url(booking, 'payment')}
        except Exception as e:  # noqa: BLE001
            _logger.exception('Failed to save booking info')
            return {'success': False, 'error': str(e)}

    # ── OTP: send / verify / resend ─────────────────────────────────────
    @http.route('/shop/booking/otp/send', type='jsonrpc', auth='public', website=True, methods=['POST'])
    def otp_send(self, booking_id, access_token=None, **kw):
        try:
            booking = request.env['bs.car.booking'].sudo().browse(int(booking_id))
            if not booking.exists():
                return {'success': False, 'error': 'Booking not found.'}
            if not self._check_booking_token(booking, access_token):
                return {'success': False, 'error': 'This booking link is no longer valid.'}
            if booking.state not in ('draft', 'otp_pending') or booking.phone_verified:
                return {'success': False, 'error': 'OTP cannot be resent for this booking.'}
            booking.action_send_otp()
            return {'success': True, 'message': f'OTP sent to {booking.customer_phone}',
                    'expires_in': 300}
        except Exception as e:  # noqa: BLE001
            _logger.exception('Failed to send OTP')
            return {'success': False, 'error': str(e)}

    @http.route('/shop/booking/otp/verify', type='jsonrpc', auth='public', website=True, methods=['POST'])
    def otp_verify(self, booking_id, otp_code, access_token=None, **kw):
        try:
            booking = request.env['bs.car.booking'].sudo().browse(int(booking_id))
            if not booking.exists():
                return {'success': False, 'error': 'Booking not found.'}
            if not self._check_booking_token(booking, access_token):
                return {'success': False, 'error': 'This booking link is no longer valid.'}
            if booking.state != 'otp_pending':
                return {'success': False, 'error': 'This booking is not waiting for OTP.'}
            result = booking.action_verify_otp((otp_code or '').strip())
            if result.get('success'):
                result['redirect_url'] = self._booking_step_url(booking, 'info')
            return result
        except Exception as e:  # noqa: BLE001
            _logger.exception('OTP verification failed')
            return {'success': False, 'error': str(e)}

    @http.route('/shop/booking/otp/resend', type='jsonrpc', auth='public', website=True, methods=['POST'])
    def otp_resend(self, booking_id, access_token=None, **kw):
        return self.otp_send(booking_id=booking_id, access_token=access_token, **kw)
