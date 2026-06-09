# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

import logging

from werkzeug.urls import url_encode

from odoo import http
from odoo.http import request
from odoo.addons.sale.controllers.portal import CustomerPortal
from odoo.tools import consteq

_logger = logging.getLogger(__name__)


class BsCarBookingWebsite(CustomerPortal):
    """Premium car-dealer funnel: catalog → configure → OTP → info → deposit → done."""

    def _booking_step_url(self, booking, step):
        """Return a tokenized public funnel URL for a booking step."""
        return '/booking/%s/%s?%s' % (
            booking.id,
            step,
            url_encode({'access_token': booking._portal_ensure_token()}),
        )

    def _can_access_booking(self, booking, access_token=None):
        """Allow public funnel access only through the portal token."""
        if access_token and consteq(booking.access_token or '', access_token):
            return True
        user = request.env.user
        if user._is_public():
            return False
        if user.has_group('base.group_user'):
            return True
        partner = user.partner_id.commercial_partner_id
        return bool(
            booking.partner_id
            and booking.partner_id.commercial_partner_id == partner
        )

    def _get_booking_or_404(self, booking_id, access_token=None):
        booking = request.env['bs.car.booking'].sudo().browse(booking_id)
        if not booking.exists() or not self._can_access_booking(booking, access_token):
            return False
        return booking

    # ── Catalog ─────────────────────────────────────────────────────────
    @http.route('/cars', type='http', auth='public', website=True, sitemap=True)
    def car_listing(self, brand_id=None, body_type=None, price_min=None, price_max=None, **kw):
        Model = request.env['bs.car.model'].sudo()
        domain = [('website_published', '=', True), ('active', '=', True)]
        if brand_id:
            domain.append(('brand_id', '=', int(brand_id)))
        if body_type:
            domain.append(('body_type', '=', body_type))
        # Price filters (from the home "Browse" tiles); tolerate bad input.
        try:
            if price_min:
                domain.append(('base_price', '>=', float(price_min)))
            if price_max:
                domain.append(('base_price', '<', float(price_max)))
        except (ValueError, TypeError):
            pass
        models = Model.search(domain, order='sequence, id')
        brands = request.env['bs.car.brand'].sudo().search([
            ('active', '=', True), ('model_ids.website_published', '=', True),
        ])
        # Body-type pills (distinct types across all published models).
        published = Model.search([('website_published', '=', True), ('active', '=', True)])
        type_labels = dict(Model._fields['body_type'].selection)
        body_types = [(bt, type_labels.get(bt, bt))
                      for bt in dict.fromkeys(published.mapped('body_type')) if bt]
        return request.render('bs_car_booking.car_listing_page', {
            'models': models, 'brands': brands,
            'active_brand_id': int(brand_id) if brand_id else False,
            'active_body_type': body_type or False,
            'body_types': body_types,
        })

    # ── Compare models ──────────────────────────────────────────────────
    @http.route('/compare', type='http', auth='public', website=True, sitemap=True)
    def car_compare(self, **kw):
        # Accept both repeated (?ids=1&ids=2, from the picker form) and
        # comma-separated (?ids=1,2,3, shareable) forms; cap at 4 columns.
        raw = request.httprequest.args.getlist('ids')
        ids = []
        for chunk in raw:
            for part in str(chunk).split(','):
                if part.strip().isdigit():
                    n = int(part)
                    if n not in ids:
                        ids.append(n)
        Model = request.env['bs.car.model'].sudo()
        selected = Model.browse(ids[:4]).filtered(
            lambda c: c.exists() and c.website_published and c.active)
        all_models = Model.search(
            [('website_published', '=', True), ('active', '=', True)],
            order='sequence, id')
        return request.render('bs_car_booking.car_compare_page', {
            'selected': selected,
            'all_models': all_models,
            'compare_rows': selected._get_compare_rows() if len(selected) > 1 else [],
            'page_title': 'Compare models',
        })

    # ── Editorial stories ──────────────────────────────────────────────
    @http.route('/stories', type='http', auth='public', website=True, sitemap=True)
    def stories_index(self, **kw):
        stories = request.env['bs.car.story'].sudo()._get_website_stories(limit=24)
        return request.render('bs_car_booking.story_index_page', {
            'stories': stories,
            'page_title': 'Stories',
        })

    @http.route('/story/<int:story_id>', type='http', auth='public', website=True, sitemap=True)
    def story_detail(self, story_id, **kw):
        Story = request.env['bs.car.story'].sudo()
        story = Story.browse(story_id)
        if not story.exists() or not story.active or not story.website_published:
            return request.not_found()
        stories = Story._get_website_stories(limit=200)
        ordered_ids = list(stories.ids)
        current_index = ordered_ids.index(story.id) if story.id in ordered_ids else -1
        prev_story = stories[current_index - 1] if current_index > 0 else False
        next_story = stories[current_index + 1] if 0 <= current_index < len(stories) - 1 else False
        return request.render('bs_car_booking.story_detail_page', {
            'story': story,
            'prev_story': prev_story,
            'next_story': next_story,
            'page_title': story.name,
        })

    # ── Car detail (marketing) ──────────────────────────────────────────
    @http.route('/car/<int:model_id>', type='http', auth='public', website=True, sitemap=True)
    def car_detail(self, model_id, **kw):
        car = request.env['bs.car.model'].sudo().browse(model_id)
        if not car.exists() or not car.website_published:
            return request.not_found()
        dealers = request.env['bs.car.dealer'].sudo().search([
            ('active', '=', True), ('website_published', '=', True),
            ('brand_ids', 'in', [car.brand_id.id]),
        ])
        variants = car.variant_ids.filtered(lambda v: v.website_published and v.active)
        return request.render('bs_car_booking.car_detail_page', {
            'car': car, 'variants': variants, 'dealers': dealers, 'page_title': car.name,
            # Enables per-car SEO/OpenGraph meta + the editor SEO/publish panel.
            'main_object': car,
        })

    # ── Configure & start booking ───────────────────────────────────────
    @http.route('/car/<int:model_id>/book', type='http', auth='public', website=True, sitemap=False)
    def booking_form(self, model_id, **kw):
        car = request.env['bs.car.model'].sudo().browse(model_id)
        if not car.exists() or not car.website_published:
            return request.not_found()
        if not car.product_tmpl_id:
            car.sudo().action_generate_product()
        dealers = request.env['bs.car.dealer'].sudo().search([
            ('active', '=', True), ('website_published', '=', True),
            ('brand_ids', 'in', [car.brand_id.id]),
        ])
        tmpl = car.product_tmpl_id.sudo()
        return request.render('bs_car_booking.booking_configurator_page', {
            'car': car,
            'tmpl': tmpl,
            'attribute_lines': tmpl.valid_product_template_attribute_line_ids,
            'dealers': dealers,
            'base_price': car.base_price,
        })

    # ── OTP verification ────────────────────────────────────────────────
    @http.route('/booking/<int:booking_id>/verify', type='http', auth='public', website=True, sitemap=False)
    def otp_verification(self, booking_id, access_token=None, **kw):
        booking = self._get_booking_or_404(booking_id, access_token)
        if not booking:
            return request.not_found()
        if booking.state in ('cancelled', 'expired'):
            return request.redirect(self._booking_step_url(booking, 'confirmation'))
        if booking.phone_verified:
            return request.redirect(self._booking_step_url(booking, 'info'))
        return request.render('bs_car_booking.otp_verification_page', {
            'booking': booking,
            'access_token': booking._portal_ensure_token(),
        })

    # ── Customer info ───────────────────────────────────────────────────
    @http.route('/booking/<int:booking_id>/info', type='http', auth='public', website=True, sitemap=False)
    def booking_customer_info(self, booking_id, access_token=None, **kw):
        booking = self._get_booking_or_404(booking_id, access_token)
        if not booking:
            return request.not_found()
        if booking.state in ('cancelled', 'expired'):
            return request.redirect(self._booking_step_url(booking, 'confirmation'))
        if not booking.phone_verified:
            return request.redirect(self._booking_step_url(booking, 'verify'))
        # Once paid/confirmed the info is locked — pressing Back must not land on
        # an editable form (the payment step already guards this the same way).
        if booking.state in ('confirmed', 'in_production', 'ready_delivery', 'delivered'):
            return request.redirect(self._booking_step_url(booking, 'confirmation'))
        # Offer (explicit opt-in) to fill the form from the logged-in user's
        # own account — never auto-filled, to avoid leaking PII on a shared device.
        user = request.env.user
        account_partner = user.partner_id if not user._is_public() else False
        # All applicable document types + agreements for both customer types;
        # the form shows/hides each by its `applies_to` as the customer toggles.
        doc_types = request.env['bs.car.document.type'].sudo().search([])
        agreements = request.env['bs.car.agreement'].sudo().search([])
        ICP = request.env['ir.config_parameter'].sudo()
        try:
            max_doc_mb = max(int(ICP.get_param('bs_car_booking.max_doc_mb', '10')), 1)
        except (TypeError, ValueError):
            max_doc_mb = 10
        return request.render('bs_car_booking.booking_info_page', {
            'booking': booking,
            'access_token': booking._portal_ensure_token(),
            'account_partner': account_partner,
            'doc_types': doc_types,
            'agreements': agreements,
            'max_doc_mb': max_doc_mb,
            # Rehydration when the customer navigates Back: which docs are already
            # uploaded and which agreements were already accepted (saved on the
            # booking), so we don't make them redo completed work.
            'uploaded_doc_type_ids': booking.document_ids.mapped('document_type_id').ids,
            'accepted_agreement_ids': booking.agreement_ids.filtered('accepted').mapped('agreement_id').ids,
        })

    # ── Deposit payment (reuses native payment.form via sale order) ─────
    @http.route('/booking/<int:booking_id>/payment', type='http', auth='public', website=True, sitemap=False)
    def booking_payment(self, booking_id, access_token=None, **kw):
        booking = self._get_booking_or_404(booking_id, access_token)
        if not booking:
            return request.not_found()
        if booking.state in ('cancelled', 'expired'):
            return request.redirect(self._booking_step_url(booking, 'confirmation'))
        if not booking.phone_verified:
            return request.redirect(self._booking_step_url(booking, 'verify'))
        # A company booking has no customer_name (it uses company_name +
        # contact_person), so check the right field per type — otherwise the
        # payment page bounced company bookings straight back to the info step.
        _named = booking.company_name if booking.customer_type == 'company' else booking.customer_name
        if not _named:
            return request.redirect(self._booking_step_url(booking, 'info'))
        if booking.state in ('confirmed', 'in_production', 'ready_delivery', 'delivered'):
            return request.redirect(self._booking_step_url(booking, 'confirmation'))

        order_sudo = booking.sale_order_id.sudo() or booking.sudo()._ensure_sale_order().sudo()
        deposit = booking.deposit_amount or order_sudo._get_prepayment_required_amount()
        values = self._get_payment_values(
            order_sudo, is_down_payment=True, payment_amount=deposit)
        # Land back on our premium confirmation page after payment.
        values['landing_route'] = self._booking_step_url(booking, 'confirmation')
        # NOTE: do NOT overwrite ``access_token`` here — payment.form consumes the
        # payment token from _get_payment_values (derived from partner/amount/currency).
        # The booking's own portal token is exposed separately for our step links.
        values.update({
            'booking': booking,
            'deposit_amount': deposit,
            'booking_access_token': booking._portal_ensure_token(),
        })
        return request.render('bs_car_booking.deposit_payment_page', values)

    # ── Confirmation ────────────────────────────────────────────────────
    @http.route('/booking/<int:booking_id>/confirmation', type='http', auth='public', website=True, sitemap=False)
    def booking_confirmation(self, booking_id, access_token=None, **kw):
        booking = self._get_booking_or_404(booking_id, access_token)
        if not booking:
            return request.not_found()
        return request.render('bs_car_booking.booking_confirmation_page', {
            'booking': booking,
            'access_token': booking._portal_ensure_token(),
        })
