# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

import logging

from werkzeug.urls import url_encode

from odoo import fields, http
from odoo.http import request
from odoo.addons.sale.controllers.portal import CustomerPortal
from odoo.tools import consteq

_logger = logging.getLogger(__name__)


class BsCarBookingWebsite(CustomerPortal):
    """Premium car-dealer funnel: catalog → configure → OTP → info → deposit → done."""

    def _scoped_env(self, model_name):
        return request.env[model_name].sudo().with_context(website_id=request.website.id)

    def _company_domain(self, model_name):
        Model = request.env[model_name]
        if 'company_id' not in Model._fields:
            return []
        return [('company_id', 'in', [False, request.website.company_id.id])]

    def _public_domain(self, model_name):
        return [('website_published', '=', True), ('active', '=', True)] + self._company_domain(model_name)

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
        if booking.website_id and booking.website_id != request.website:
            return False
        return booking

    # ── Catalog ─────────────────────────────────────────────────────────
    @http.route('/cars', type='http', auth='public', website=True, sitemap=True)
    def car_listing(self, brand_id=None, body_type=None, price_min=None, price_max=None, **kw):
        Model = self._scoped_env('bs.car.model')
        domain = self._public_domain('bs.car.model')
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
        brands = self._scoped_env('bs.car.brand').search([
            ('active', '=', True),
            ('website_published', '=', True),
            ('model_ids.website_published', '=', True),
        ] + self._company_domain('bs.car.brand'))
        # Body-type pills (distinct types across all published models).
        published = Model.search(self._public_domain('bs.car.model'))
        type_labels = dict(Model._fields['body_type'].selection)
        body_types = [(bt, type_labels.get(bt, bt))
                      for bt in dict.fromkeys(published.mapped('body_type')) if bt]
        return request.render('bs_car_booking.car_listing_page', {
            'models': models, 'brands': brands,
            'active_brand_id': int(brand_id) if brand_id else False,
            'active_body_type': body_type or False,
            'body_types': body_types,
        })

    # ── Editorial stories ──────────────────────────────────────────────
    @http.route('/stories', type='http', auth='public', website=True, sitemap=True)
    def stories_index(self, **kw):
        stories = self._scoped_env('bs.car.story')._get_website_stories(limit=24)
        return request.render('bs_car_booking.story_index_page', {
            'stories': stories,
            'page_title': 'News',
        })

    @http.route('/story/<int:story_id>', type='http', auth='public', website=True, sitemap=True)
    def story_detail(self, story_id, **kw):
        Story = self._scoped_env('bs.car.story')
        story = Story.browse(story_id)
        if (not story.exists() or not story.active or not story.website_published
                or (story.company_id and story.company_id != request.website.company_id)):
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
        car = self._scoped_env('bs.car.model').browse(model_id)
        if (not car.exists() or not car.website_published
                or (car.company_id and car.company_id != request.website.company_id)):
            return request.not_found()
        dealers = self._scoped_env('bs.car.dealer').search([
            ('active', '=', True), ('website_published', '=', True),
            ('brand_ids', 'in', [car.brand_id.id]),
        ] + self._company_domain('bs.car.dealer'))
        variants = car.variant_ids.filtered(lambda v: v.website_published and v.active)
        return request.render('bs_car_booking.car_detail_page', {
            'car': car, 'variants': variants, 'dealers': dealers, 'page_title': car.name,
            # Enables per-car SEO/OpenGraph meta + the editor SEO/publish panel.
            'main_object': car,
        })

    # ── Configure & start booking ───────────────────────────────────────
    @http.route('/car/<int:model_id>/book', type='http', auth='public', website=True, sitemap=False)
    def booking_form(self, model_id, **kw):
        car = self._scoped_env('bs.car.model').browse(model_id)
        if (not car.exists() or not car.website_published
                or (car.company_id and car.company_id != request.website.company_id)):
            return request.not_found()
        dealers = self._scoped_env('bs.car.dealer').search([
            ('active', '=', True), ('website_published', '=', True),
            ('brand_ids', 'in', [car.brand_id.id]),
        ] + self._company_domain('bs.car.dealer'))
        tmpl = car.product_tmpl_id.sudo()
        options = request.env['bs.car.model.option'].sudo().search([('model_id', '=', car.id)])
        # Attribute values whose car-model option is unpublished: still shown in
        # the configurator, but rendered disabled (not selectable).
        unpublished_value_ids = options.filtered(
            lambda o: not o.website_published).value_id.ids
        # Per-exterior availability: {exterior value id: [interior value id, ...]}.
        # Only exterior options that restrict their interiors appear here; an
        # exterior absent from the map offers every interior.
        exterior_interiors = {
            o.value_id.id: o.interior_option_ids.value_id.ids
            for o in options if o.interior_option_ids
        }
        return request.render('bs_car_booking.booking_configurator_page', {
            'car': car,
            'tmpl': tmpl,
            'product_missing': not bool(tmpl),
            'standard_package_attr': request.env.ref('bs_car_booking.attr_trim', raise_if_not_found=False),
            'interior_attr': request.env.ref('bs_car_booking.attr_interior', raise_if_not_found=False),
            'attribute_lines': tmpl.valid_product_template_attribute_line_ids if tmpl else [],
            'dealers': dealers,
            'base_price': car.base_price,
            # 'sms' or 'email' — decides whether the form must collect an email.
            'otp_channel': request.env['bs.car.booking.otp'].sudo()._get_otp_channel(),
            'unpublished_value_ids': unpublished_value_ids,
            'exterior_interiors': exterior_interiors,
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
        # Reflect what was actually sent: the latest OTP's channel/destination.
        Otp = request.env['bs.car.booking.otp'].sudo()
        last_otp = booking.otp_ids.sorted('id', reverse=True)[:1]
        website_mode = Otp._get_otp_channel()
        otp_channel = last_otp.channel if last_otp else \
            ('email' if website_mode == 'email' else 'sms')
        # Countdown shows the REAL remaining lifetime (the page may be
        # reopened later), capped to the configured validity.
        expires_in = Otp._get_validity_minutes(booking.website_id) * 60
        if last_otp and last_otp.expire_datetime:
            remaining = (last_otp.expire_datetime - fields.Datetime.now()).total_seconds()
            expires_in = max(0, min(int(remaining), expires_in))
        # 'both'-mode websites may switch the delivery channel from the verify
        # page; switching TO email needs an address already on the booking
        # (the switch is a flag only — never an attacker-supplied address).
        switch_channel = False
        if website_mode == 'both':
            if otp_channel == 'email':
                switch_channel = 'sms'
            elif booking.customer_email:
                switch_channel = 'email'
        return request.render('bs_car_booking.otp_verification_page', {
            'booking': booking,
            'access_token': booking._portal_ensure_token(),
            'otp_channel': otp_channel,
            'otp_destination': (last_otp.email or booking.customer_email
                                if otp_channel == 'email' else booking.customer_phone),
            'otp_switch_channel': switch_channel,
            'otp_expires_in': expires_in,
            'otp_resend_in': (max(booking.website_id.bs_otp_resend_seconds, 0)
                              if booking.website_id else 30),
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
        company_domain = [('company_id', 'in', [False, booking.company_id.id])]
        doc_types = request.env['bs.car.document.type'].sudo().search(
            company_domain + [('active', '=', True)])
        agreements = request.env['bs.car.agreement'].sudo().search(
            company_domain + [('active', '=', True)])
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

    # ── Customer Rating ─────────────────────────────────────────────────
    @http.route('/booking/<int:booking_id>/submit_rating', type='json', auth='public', website=True, methods=['POST'])
    def booking_submit_rating(self, booking_id, access_token=None, rating=0, comment='', **kw):
        booking = self._get_booking_or_404(booking_id, access_token)
        if not booking:
            return {'error': 'Not found'}
        try:
            booking.action_submit_rating(rating, comment)
        except Exception as exc:
            return {'error': str(exc)}
        return {'success': True}

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
