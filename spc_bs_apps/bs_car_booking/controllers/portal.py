# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class CarBookingPortal(CustomerPortal):
    """Expose car bookings in the customer portal (My Account)."""

    def _booking_domain(self, partner):
        return [('partner_id', 'child_of', partner.commercial_partner_id.id)]

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'booking_count' in counters:
            partner = request.env.user.partner_id
            values['booking_count'] = (
                request.env['bs.car.booking'].search_count(self._booking_domain(partner))
                if partner else 0
            )
        return values

    @http.route(['/my/bookings', '/my/bookings/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_my_bookings(self, page=1, **kw):
        partner = request.env.user.partner_id
        Booking = request.env['bs.car.booking']
        domain = self._booking_domain(partner)
        count = Booking.search_count(domain)
        pager = portal_pager(
            url='/my/bookings', total=count, page=page, step=self._items_per_page)
        bookings = Booking.search(
            domain, order='create_date desc',
            limit=self._items_per_page, offset=pager['offset'])
        values = self._prepare_portal_layout_values()
        values.update({
            'bookings': bookings,
            'page_name': 'booking',
            'pager': pager,
            'default_url': '/my/bookings',
        })
        return request.render('bs_car_booking.portal_my_bookings', values)

    @http.route(['/my/booking/<int:booking_id>'], type='http', auth='public', website=True)
    def portal_my_booking(self, booking_id, access_token=None, **kw):
        try:
            booking_sudo = self._document_check_access(
                'bs.car.booking', booking_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        values = {
            'booking': booking_sudo,
            'page_name': 'booking',
            'bs_booking': booking_sudo,
            'access_token': access_token or booking_sudo._portal_ensure_token(),
        }
        return request.render('bs_car_booking.portal_my_booking', values)
