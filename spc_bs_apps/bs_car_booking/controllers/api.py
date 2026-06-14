# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

import base64
import binascii
import logging

from werkzeug.urls import url_encode

from odoo import _, fields, http
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.tools import consteq
from odoo.tools import format_amount

_logger = logging.getLogger(__name__)


class BsCarBookingAPI(http.Controller):
    """JSON-RPC endpoints for the AJAX booking funnel."""

    _ALLOWED_DOCUMENT_SIGNATURES = (
        ('application/pdf', b'%PDF-'),
        ('image/jpeg', b'\xff\xd8\xff'),
        ('image/png', b'\x89PNG\r\n\x1a\n'),
    )

    def _booking_step_url(self, booking, step):
        return '/booking/%s/%s?%s' % (
            booking.id,
            step,
            url_encode({'access_token': booking._portal_ensure_token()}),
        )

    def _check_booking_token(self, booking, access_token=None):
        return bool(access_token and consteq(booking.access_token or '', access_token))

    def _scoped_env(self, model_name):
        return request.env[model_name].sudo().with_context(website_id=request.website.id)

    def _company_domain(self, model_name):
        Model = request.env[model_name]
        if 'company_id' not in Model._fields:
            return []
        return [('company_id', 'in', [False, request.website.company_id.id])]

    def _is_current_company_record(self, record):
        return not getattr(record, 'company_id', False) or record.company_id == request.website.company_id

    # ── Live price for a configuration ──────────────────────────────────
    def _published_ptav_ids(self, model, ptav_ids):
        """Drop any selected attribute values whose car-model option is
        unpublished — the website disables them, this enforces it server-side so
        a crafted request can't book/price a hidden option."""
        ids = [int(p) for p in (ptav_ids or [])]
        if not ids:
            return ids
        unpublished_value_ids = set(request.env['bs.car.model.option'].sudo().search([
            ('model_id', '=', model.id),
            ('website_published', '=', False),
        ]).value_id.ids)
        if not unpublished_value_ids:
            return ids
        ptavs = request.env['product.template.attribute.value'].sudo().browse(ids).exists()
        return [p.id for p in ptavs
                if p.product_attribute_value_id.id not in unpublished_value_ids]
        
    @http.route(['/car_booking/car/price', '/shop/car/price'], type='jsonrpc',
                auth='public', website=True, methods=['POST'])
    def car_price(self, model_id, ptav_ids=None):
        """Return the live price for a selected attribute combination."""
        model = self._scoped_env('bs.car.model').browse(int(model_id))
        if (not model.exists() or not model.website_published or not model.active
                or not self._is_current_company_record(model)):
            return {'success': False, 'error': 'Unknown model.'}
        tmpl = model.product_tmpl_id
        currency = model.currency_id or request.env.company.currency_id
        if not tmpl:
            return {'success': True, 'price': model.base_price or 0.0,
                    'currency_id': currency.id}
        ptav_ids = self._published_ptav_ids(model, ptav_ids)
        combo = request.env['product.template.attribute.value'].sudo().browse(ptav_ids)
        combo = combo.exists().filtered(lambda p: p.product_tmpl_id == tmpl)
        # Price = template list price + each selected value's price_extra (set by
        # action_generate_product). Computed directly from product-core fields so
        # we don't depend on website_sale's _get_combination_info (no shop here).
        list_price = tmpl.list_price or 0.0
        price = list_price + sum(combo.mapped('price_extra'))
        return {
            'success': True,
            'price': price,
            'price_formatted': format_amount(request.env, price, currency),
            'list_price': list_price,
            'currency_id': currency.id,
        }

    # ── Create booking from configurator ────────────────────────────────
    @http.route(['/car_booking/car/book', '/shop/car/book'], type='jsonrpc',
                auth='public', website=True, methods=['POST'])
    def car_book(self, model_id, ptav_ids=None, dealer_id=None, phone=None,
                 email=None, otp_channel=None, pdpa_consent=False, **kw):
        """Create a draft booking from the configurator and send the OTP.

        PDPA consent is captured here (before the OTP is sent), so we never
        contact a customer who has not consented."""
        try:
            model = self._scoped_env('bs.car.model').browse(int(model_id))
            if (not model.exists() or not model.website_published or not model.active
                    or not self._is_current_company_record(model)):
                return {'success': False, 'error': 'Unknown model.'}
            if not model.product_tmpl_id:
                return {
                    'success': False,
                    'error': 'This model is not ready for online booking yet.',
                }
            if not request.env['bs.car.booking']._is_valid_phone(phone):
                return {'success': False,
                        'error': 'Please enter a valid phone number (7–15 digits).'}
            email = (email or '').strip()
            # Website mode: 'sms'/'email' fix the channel (clamping whatever
            # the client sent); 'both' honours the customer's pick (SMS default).
            website_channel = request.env['bs.car.booking.otp'].sudo()._get_otp_channel()
            otp_channel = (otp_channel or '').strip().lower()
            if website_channel in ('sms', 'email'):
                otp_channel = website_channel
            elif otp_channel not in ('sms', 'email'):
                otp_channel = 'sms'
            if otp_channel == 'email' and ('@' not in email or '.' not in email.rsplit('@', 1)[-1]):
                return {'success': False, 'error': 'Please enter a valid email address.'}
            if not pdpa_consent:
                return {'success': False,
                        'error': 'Please accept the privacy policy (PDPA) to continue.'}
            dealer = self._scoped_env('bs.car.dealer').browse(int(dealer_id or 0))
            if not dealer.exists() or not dealer.active or not dealer.website_published \
                    or model.brand_id not in dealer.brand_ids \
                    or not self._is_current_company_record(dealer):
                return {'success': False, 'error': 'Please choose a valid dealer.'}

            vals = {
                'website_id': request.website.id,
                'company_id': request.website.company_id.id,
                'brand_id': model.brand_id.id,
                'model_id': model.id,
                'dealer_id': dealer.id,
                'customer_phone': phone.strip(),
                'deposit_amount': model.deposit_amount or 0.0,
                'currency_id': (model.currency_id or request.env.company.currency_id).id,
                'pdpa_consent': True,
                'pdpa_consent_date': fields.Datetime.now(),
            }
            if email:
                vals['customer_email'] = email
            # Reuse the session's in-progress draft for the same model instead of
            # creating a duplicate when the customer goes Back and re-submits the
            # configurator. Only pre-verification bookings are reused.
            Booking = request.env['bs.car.booking'].sudo()
            prev = Booking.browse(request.session.get('bs_funnel_booking') or 0)
            reuse = (prev.exists() and prev.state in ('draft', 'otp_pending')
                     and not prev.phone_verified and prev.model_id.id == model.id)
            published_ptav_ids = self._published_ptav_ids(model, ptav_ids)
            if reuse:
                booking = prev
                booking.write(vals)
                booking._apply_configuration(published_ptav_ids)
                try:
                    booking.action_send_otp(channel=otp_channel)
                except ValidationError:
                    pass
            else:
                booking = Booking.create(vals)
                request.session['bs_funnel_booking'] = booking.id
                booking._apply_configuration(published_ptav_ids)
                booking.action_send_otp(channel=otp_channel)
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
    def _max_doc_mb(self):
        """Per-document upload limit in MB. Configurable via System Parameter
        `bs_car_booking.max_doc_mb` (default 10)."""
        mb = request.env['ir.config_parameter'].sudo().get_param(
            'bs_car_booking.max_doc_mb', '10')
        try:
            return max(int(mb), 1)
        except (TypeError, ValueError):
            return 10

    def _clean_document_upload(self, upload, max_mb):
        """Validate and normalize a browser-provided base64 document payload."""
        try:
            dtype_id = int(upload.get('document_type_id'))
            data = upload.get('data') or ''
        except (AttributeError, TypeError, ValueError):
            return None, None, None
        if not data:
            return None, None, None
        try:
            raw = base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError):
            raise ValidationError(_('One uploaded document is not a valid file.'))
        if len(raw) > max_mb * 1024 * 1024:
            raise ValidationError(_('A document exceeds the %s MB limit.') % max_mb)
        if not any(raw.startswith(signature) for _mime, signature in self._ALLOWED_DOCUMENT_SIGNATURES):
            raise ValidationError(_('Only PDF, JPEG, and PNG documents are allowed.'))
        filename = (upload.get('filename') or 'document').replace('\\', '/').split('/')[-1]
        return dtype_id, base64.b64encode(raw).decode(), filename[:200]

    @http.route(['/car_booking/booking/info', '/shop/booking/info'], type='jsonrpc',
                auth='public', website=True, methods=['POST'])
    def booking_info(self, booking_id, access_token=None, customer_type=None,
                     name=None, email=None, nrc=None, address=None,
                     company_name=None, tax_id=None, contact_person=None,
                     documents=None, agreements=None, **kw):
        """Save customer info (individual/company), uploaded documents and
        accepted agreements; validate server-side; then create the partner +
        sale order and move to the deposit step."""
        try:
            booking = request.env['bs.car.booking'].sudo().browse(int(booking_id))
            if not booking.exists():
                return {'success': False, 'error': 'Booking not found.'}
            if not self._check_booking_token(booking, access_token):
                return {'success': False, 'error': 'This booking link is no longer valid.'}
            if booking.website_id and booking.website_id != request.website:
                return {'success': False, 'error': 'This booking link is no longer valid.'}
            if booking.state not in ('otp_verified', 'payment_pending'):
                return {'success': False, 'error': 'This booking is not ready for customer info.'}
            if not booking.phone_verified:
                return {'success': False, 'error': 'Please verify your phone first.'}

            ctype = customer_type if customer_type in ('individual', 'company') else 'individual'
            booking.write({
                'customer_type': ctype,
                'customer_name': (name or '').strip(),
                'customer_email': (email or '').strip(),
                'customer_nrc': (nrc or '').strip(),
                'customer_address': (address or '').strip(),
                'company_name': (company_name or '').strip(),
                'tax_id': (tax_id or '').strip(),
                'contact_person': (contact_person or '').strip(),
            })

            # --- Persist uploaded documents (base64), one per document type ---
            Doc = request.env['bs.car.booking.document'].sudo()
            max_mb = self._max_doc_mb()
            for d in (documents or []):
                try:
                    dtype_id, data, filename = self._clean_document_upload(d, max_mb)
                except ValidationError as e:
                    return {'success': False, 'error': str(e)}
                if not data:
                    continue
                # Replace any previous upload for the same type on this booking.
                Doc.search([('booking_id', '=', booking.id),
                            ('document_type_id', '=', dtype_id)]).unlink()
                Doc.create({
                    'booking_id': booking.id,
                    'document_type_id': dtype_id,
                    'attachment': data,
                    'filename': filename,
                })

            # --- Record accepted agreements (with timestamp, legal audit) ---
            Agr = request.env['bs.car.booking.agreement'].sudo()
            accepted_ids = {int(a) for a in (agreements or []) if str(a).isdigit()}
            for agr in booking._applicable_agreements(ctype):
                existing = Agr.search([('booking_id', '=', booking.id),
                                       ('agreement_id', '=', agr.id)], limit=1)
                is_accepted = agr.id in accepted_ids
                vals = {'accepted': is_accepted}
                if is_accepted:
                    vals['accepted_date'] = fields.Datetime.now()
                if existing:
                    existing.write(vals)
                else:
                    Agr.create({'booking_id': booking.id, 'agreement_id': agr.id, **vals})

            # --- Server-side validation (type fields + required docs + agreements) ---
            errors = booking._missing_requirements(ctype)
            if errors:
                return {'success': False, 'error': ' '.join(errors)}

            booking._ensure_partner()
            booking._ensure_sale_order()
            booking._transition_to('payment_pending')
            return {'success': True, 'redirect_url': self._booking_step_url(booking, 'payment')}
        except Exception as e:  # noqa: BLE001
            _logger.exception('Failed to save booking info')
            return {'success': False, 'error': str(e)}

    # ── OTP: send / verify / resend ─────────────────────────────────────
    @http.route(['/car_booking/booking/otp/send', '/shop/booking/otp/send'], type='jsonrpc',
                auth='public', website=True, methods=['POST'])
    def otp_send(self, booking_id, access_token=None, channel=None, **kw):
        """Send/resend the verification OTP.

        *channel* is only a switch FLAG ('sms'/'email') for 'both'-mode
        websites — the destination always comes from the booking record, so
        a tampered request can never redirect codes to an attacker-supplied
        address. Server-side throttling applies regardless."""
        try:
            booking = request.env['bs.car.booking'].sudo().browse(int(booking_id))
            if not booking.exists():
                return {'success': False, 'error': 'Booking not found.'}
            if not self._check_booking_token(booking, access_token):
                return {'success': False, 'error': 'This booking link is no longer valid.'}
            if booking.website_id and booking.website_id != request.website:
                return {'success': False, 'error': 'This booking link is no longer valid.'}
            if booking.state not in ('draft', 'otp_pending') or booking.phone_verified:
                return {'success': False, 'error': 'OTP cannot be resent for this booking.'}
            channel = channel if channel in ('sms', 'email') else None
            booking.action_send_otp(channel=channel)
            sent = booking.otp_ids.sorted('id', reverse=True)[:1]
            destination = sent.email if sent.channel == 'email' else booking.customer_phone
            Otp = request.env['bs.car.booking.otp'].sudo()
            website = booking.website_id
            return {'success': True, 'message': f'OTP sent to {destination}',
                    'channel': sent.channel, 'destination': destination,
                    'expires_in': Otp._get_validity_minutes(website) * 60,
                    'resend_in': max(website.bs_otp_resend_seconds, 0) if website else 30}
        except ValidationError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:  # noqa: BLE001
            _logger.exception('Failed to send OTP')
            return {'success': False, 'error': str(e)}

    @http.route(['/car_booking/booking/otp/verify', '/shop/booking/otp/verify'], type='jsonrpc',
                auth='public', website=True, methods=['POST'])
    def otp_verify(self, booking_id, otp_code, access_token=None, **kw):
        try:
            booking = request.env['bs.car.booking'].sudo().browse(int(booking_id))
            if not booking.exists():
                return {'success': False, 'error': 'Booking not found.'}
            if not self._check_booking_token(booking, access_token):
                return {'success': False, 'error': 'This booking link is no longer valid.'}
            if booking.website_id and booking.website_id != request.website:
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

    @http.route(['/car_booking/booking/otp/resend', '/shop/booking/otp/resend'], type='jsonrpc',
                auth='public', website=True, methods=['POST'])
    def otp_resend(self, booking_id, access_token=None, **kw):
        return self.otp_send(booking_id=booking_id, access_token=access_token, **kw)
