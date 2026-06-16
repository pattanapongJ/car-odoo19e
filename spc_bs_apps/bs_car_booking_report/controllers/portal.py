# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

import base64

from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import content_disposition, request
from odoo.addons.portal.controllers.portal import CustomerPortal


class CarBookingReportPortal(CustomerPortal):
    """Portal downloads for a car booking: the booking-form contract PDF and
    each customer-uploaded document. Access is gated by the same access-token
    check the booking portal page already uses (auth='public' + token)."""

    def _bs_check_booking(self, booking_id, access_token):
        # Raises AccessError/MissingError when the token (or login) does not
        # grant access — caught by the routes and turned into a redirect.
        return self._document_check_access('bs.car.booking', booking_id, access_token)

    @http.route(['/my/booking/<int:booking_id>/booking_form'],
                type='http', auth='public', website=True)
    def portal_booking_form_pdf(self, booking_id, access_token=None, **kw):
        """Download the booking-form (contract) PDF for this booking."""
        try:
            booking = self._bs_check_booking(booking_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        pdf_content, _dummy = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'bs_car_booking_report.report_booking_individual', [booking.id])
        filename = '%s_booking_form.pdf' % (booking.name or 'booking').replace('/', '-')
        return request.make_response(pdf_content, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf_content)),
            ('Content-Disposition', content_disposition(filename)),
        ])

    @http.route(['/my/booking/<int:booking_id>/document/<int:document_id>'],
                type='http', auth='public', website=True)
    def portal_booking_document(self, booking_id, document_id, access_token=None, **kw):
        """Download one customer-uploaded document attached to this booking."""
        try:
            booking = self._bs_check_booking(booking_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        # Only documents belonging to THIS booking are reachable.
        doc = booking.document_ids.filtered(lambda d: d.id == document_id)
        if not doc or not doc.attachment:
            return request.redirect(booking.get_portal_url())
        data = base64.b64decode(doc.attachment)
        filename = doc.filename or ('%s.bin' % (doc.name or 'document'))
        return request.make_response(data, headers=[
            ('Content-Type', 'application/octet-stream'),
            ('Content-Length', len(data)),
            ('Content-Disposition', content_disposition(filename)),
        ])
