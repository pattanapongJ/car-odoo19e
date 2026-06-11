# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.
"""Public booking tracking — let a customer follow their booking WITHOUT an
account, while keeping the data behind ownership re-verification.

Flow:  /track  (enter reference + phone)
         -> /track/lookup   match ref+phone, send a one-time code (generic reply)
         -> /track/verify   check the code, then hand off to the existing
                            token-gated status page /my/booking/<id>

Security notes (see also bs.car.booking._match_for_tracking):
  * Booking references are sequential and guessable, so a reference ALONE never
    resolves a booking — we require reference AND the phone on file.
  * /track/lookup returns the SAME generic reply whether or not anything
    matched, so it cannot be used to enumerate references or phone numbers.
  * The matched booking id is kept in the server-side session, never sent to
    the browser, until the OTP is verified — so the code can't be skipped.
  * OTP sending is throttled (resend cooldown + per-phone hourly cap); lookups
    are additionally capped per session to slow brute force.
"""

import logging

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)

_SESSION_BOOKING_KEY = 'bs_track_booking_id'
_SESSION_ATTEMPTS_KEY = 'bs_track_attempts'
_MAX_LOOKUPS_PER_SESSION = 12


class BsCarBookingTracking(http.Controller):

    def _lookup_message(self):
        """Identical reply for match and no-match (anti-enumeration), but
        channel-SPECIFIC so the customer knows where to look: the delivery
        channel is a property of the WEBSITE setting, not of the booking, so
        naming it reveals nothing about whether a booking matched."""
        mode = request.env['bs.car.booking.otp'].sudo()._get_otp_channel()
        if mode == 'email':
            return ("If a booking matches those details, a verification code "
                    "has been sent to the email address on the booking "
                    "(or by SMS if the booking has no email).")
        if mode == 'sms':
            return ("If a booking matches those details, a verification code "
                    "has been sent by SMS to the phone number on the booking.")
        return ("If a booking matches those details, a verification code has "
                "been sent to the phone number or email address on the booking.")

    def _lookup_reply(self):
        """Uniform lookup/resend payload. expires_in/resend_in are website-
        setting based (identical for every visitor), so the countdowns leak
        nothing about whether a booking matched."""
        website = request.env['website'].get_current_website()
        validity = request.env['bs.car.booking.otp'].sudo()._get_validity_minutes(website)
        return {'ok': True, 'message': self._lookup_message(),
                'expires_in': validity * 60,
                'resend_in': max(website.bs_otp_resend_seconds, 0)}

    @http.route('/track', type='http', auth='public', website=True, sitemap=True)
    def track_page(self, **kw):
        """Public 'Track my booking' landing page (reference + phone form)."""
        return request.render('bs_car_booking.tracking_page', {
            # Channel hint for the static copy — website-mode-based, so it is
            # the same for every visitor (no per-booking information).
            'otp_mode': request.env['bs.car.booking.otp'].sudo()._get_otp_channel(),
        })

    @http.route('/track/lookup', type='jsonrpc', auth='public', website=True)
    def track_lookup(self, reference=None, phone=None, **kw):
        """Match reference+phone and send a tracking code. Always replies the
        same generic message (never reveals whether the booking exists)."""
        # Per-session lookup cap — slows enumeration even though replies are
        # already generic and OTPs are per-phone capped.
        attempts = request.session.get(_SESSION_ATTEMPTS_KEY, 0) + 1
        request.session[_SESSION_ATTEMPTS_KEY] = attempts
        if attempts > _MAX_LOOKUPS_PER_SESSION:
            return self._lookup_reply()

        booking = request.env['bs.car.booking'].sudo()._match_for_tracking(
            reference, phone)
        if booking:
            try:
                booking._send_tracking_otp()
                # Remember the match server-side only; the browser never learns
                # the booking id until the code is verified.
                request.session[_SESSION_BOOKING_KEY] = booking.id
            except ValidationError:
                # Throttled — keep the reply generic so timing/Throttle state
                # can't be used to confirm a match.
                pass
            except Exception as e:  # noqa: BLE001 - SMS gateway optional in dev
                _logger.warning('Tracking OTP send failed: %s', str(e))
        return self._lookup_reply()

    @http.route('/track/verify', type='jsonrpc', auth='public', website=True)
    def track_verify(self, code=None, **kw):
        """Verify the tracking code for the session's matched booking and hand
        off to the token-gated status page."""
        booking_id = request.session.get(_SESSION_BOOKING_KEY)
        if not booking_id or not (code or '').strip():
            return {'success': False, 'error': 'Please request a code first.'}
        booking = request.env['bs.car.booking'].sudo().browse(booking_id)
        if not booking.exists():
            request.session.pop(_SESSION_BOOKING_KEY, None)
            return {'success': False, 'error': 'Please request a code first.'}
        result = booking._verify_tracking_otp(code)
        if result.get('success'):
            token = booking._portal_ensure_token()
            # Clear the one-time handoff state.
            request.session.pop(_SESSION_BOOKING_KEY, None)
            request.session.pop(_SESSION_ATTEMPTS_KEY, None)
            result['redirect_url'] = '/my/booking/%s?access_token=%s' % (
                booking.id, token)
        return result

    @http.route('/track/resend', type='jsonrpc', auth='public', website=True)
    def track_resend(self, **kw):
        """Resend the tracking code for the session's matched booking."""
        booking_id = request.session.get(_SESSION_BOOKING_KEY)
        if booking_id:
            booking = request.env['bs.car.booking'].sudo().browse(booking_id)
            if booking.exists():
                try:
                    booking._send_tracking_otp()
                except ValidationError as e:
                    return {'ok': False, 'message': str(e)}
                except Exception as e:  # noqa: BLE001
                    _logger.warning('Tracking OTP resend failed: %s', str(e))
        return self._lookup_reply()
