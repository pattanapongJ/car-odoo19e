# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

import logging
import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare
from odoo.tools.mail import formataddr

_logger = logging.getLogger(__name__)

# Canonical phone shape after normalisation: optional +, then 7-15 digits
# (E.164 max). The SAME rule is enforced client-side (phone_utils.js) and on
# the form inputs' pattern attribute — keep the three in sync.
PHONE_RE = re.compile(r'^\+?\d{7,15}$')


class BsCarBooking(models.Model):
    _name = 'bs.car.booking'
    _description = 'Car Booking / Reservation'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'id desc'

    @api.model
    def _get_default_currency(self):
        return self.env.company.currency_id

    # === Booking Reference & Status ===
    name = fields.Char('Booking Reference', readonly=True, copy=False, default='/')
    website_id = fields.Many2one(
        'website', string='Source Website', readonly=True, copy=False, index=True,
        help='Website where this booking was created.')
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
        required=True, readonly=True, copy=False, index=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('otp_pending', 'OTP Pending'),
        ('otp_verified', 'Phone Verified'),
        ('payment_pending', 'Awaiting Deposit'),
        ('confirmed', 'Confirmed'),
        ('in_production', 'In Production'),
        ('ready_delivery', 'Ready for Delivery'),
        ('delivered', 'Delivered'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, copy=False, tracking=True,
       index=True)

    # === Customer Information ===
    # name is captured at the dedicated "customer info" funnel step (after OTP),
    # so it is not required at creation time.
    customer_name = fields.Char('Full Name')
    customer_phone = fields.Char('Phone Number', required=True)
    customer_email = fields.Char('Email')
    customer_nrc = fields.Char('NRC/ID Number', help='National Registration Card or ID')
    customer_address = fields.Text('Address')

    # Customer type drives which fields/documents/agreements are required and
    # how the res.partner is built (company => VAT tax invoice).
    customer_type = fields.Selection([
        ('individual', 'Individual'),
        ('company', 'Company'),
    ], string='Customer Type', default='individual', required=True)
    company_name = fields.Char('Company Name')
    tax_id = fields.Char('Tax ID', help='Company VAT / Tax ID (printed on the invoice).')
    contact_person = fields.Char('Contact Person', help='Authorised person for a company booking.')

    # Uploaded documents + accepted agreements (configurable per customer type).
    document_ids = fields.One2many('bs.car.booking.document', 'booking_id', string='Documents')
    agreement_ids = fields.One2many('bs.car.booking.agreement', 'booking_id', string='Agreements')
    
    # OTP Verification
    phone_verified = fields.Boolean('Phone Verified', default=False, copy=False)
    otp_verified_channel = fields.Selection([
        ('sms', 'SMS'),
        ('email', 'Email'),
    ], string='Verified Via', copy=False, readonly=True,
        help='Channel that delivered the verified OTP. "SMS" proves the phone '
             'number itself; "Email" means the phone was NOT independently '
             'verified (email fallback, e.g. while the SMS gateway is pending).')
    otp_ids = fields.One2many('bs.car.booking.otp', 'booking_id', string='OTP Records')
    otp_count = fields.Integer(compute='_compute_otp_count')

    @api.depends('otp_ids')
    def _compute_otp_count(self):
        for rec in self:
            rec.otp_count = len(rec.otp_ids)

    # PDPA / privacy consent (captured together with OTP confirmation)
    pdpa_consent = fields.Boolean('PDPA Consent', copy=False,
                                  help='Customer agreed to the privacy policy (PDPA).')
    pdpa_consent_date = fields.Datetime('Consent Date', readonly=True, copy=False)

    # CRM
    lead_id = fields.Many2one('crm.lead', string='CRM Lead', copy=False, readonly=True,
                              help='Lead auto-created after OTP + PDPA consent.')

    # === Car Selection ===
    brand_id = fields.Many2one('bs.car.brand', string='Brand', required=True)
    model_id = fields.Many2one('bs.car.model', string='Car Model', required=True,
                               domain="[('brand_id', '=', brand_id)]")

    # === Dealer Selection ===
    dealer_id = fields.Many2one('bs.car.dealer', string='Preferred Dealer',
                                domain="[('brand_ids', 'in', [brand_id])]")

    # === Pricing & Deposit ===
    currency_id = fields.Many2one('res.currency', default=_get_default_currency, required=True)
    car_price = fields.Monetary('Car Price', currency_field='currency_id', readonly=True)
    deposit_amount = fields.Monetary('Deposit Amount', currency_field='currency_id',
                                     help='Required deposit to confirm booking')
    deposit_paid = fields.Monetary('Deposit Paid', currency_field='currency_id', readonly=True)
    deposit_remaining = fields.Monetary('Deposit Remaining', currency_field='currency_id',
                                        compute='_compute_deposit_remaining', store=True)
    
    # === Customer / Partner ===
    partner_id = fields.Many2one('res.partner', string='Customer', copy=False, tracking=True)

    # === Product configuration (native commerce) ===
    product_id = fields.Many2one('product.product', string='Configured Variant', copy=False,
                                 help='Resolved product variant for the chosen trim.')
    option_value_ids = fields.Many2many(
        'product.template.attribute.value', string='Selected Options', copy=False,
        help='Selected no-variant options (color, interior, wheels, add-ons).')
    config_summary = fields.Char('Configuration', compute='_compute_config_summary')

    # === Sale order / invoicing backbone ===
    sale_order_id = fields.Many2one('sale.order', string='Sale Order', copy=False,
                                    readonly=True, tracking=True)
    sale_order_state = fields.Selection(related='sale_order_id.state', string='Order Status')
    amount_total = fields.Monetary('Order Total', currency_field='currency_id',
                                   compute='_compute_order_amounts')
    invoice_ids = fields.Many2many('account.move', string='Invoices',
                                   compute='_compute_order_amounts')
    invoice_count = fields.Integer(compute='_compute_order_amounts')
    transaction_ids = fields.Many2many('payment.transaction', string='Transactions',
                                       related='sale_order_id.transaction_ids')

    # === Delivery Info ===
    estimated_delivery_date = fields.Date('Estimated Delivery Date')
    actual_delivery_date = fields.Date('Actual Delivery Date', readonly=True)

    # === Customer Rating ===
    rating = fields.Integer('Customer Rating', default=0, copy=False,
                            help='1-5 stars submitted by the customer on the confirmation page.')
    rating_comment = fields.Text('Rating Comment', copy=False)
    rating_date = fields.Datetime('Rating Date', readonly=True, copy=False)

    # === Notes ===
    notes = fields.Text('Additional Notes')
    internal_notes = fields.Text('Internal Notes')

    # === Computed display fields ===
    state_label = fields.Char('Status Label', compute='_compute_state_label')

    @api.depends('state')
    def _compute_state_label(self):
        labels = dict(self._fields['state'].selection)
        for rec in self:
            rec.state_label = labels.get(rec.state, rec.state)

    # === Lifecycle helpers ===
    def _allowed_state_targets(self):
        return {
            'draft': ('otp_pending', 'cancelled', 'expired'),
            'otp_pending': ('otp_pending', 'otp_verified', 'cancelled', 'expired'),
            'otp_verified': ('payment_pending', 'cancelled', 'expired'),
            'payment_pending': ('confirmed', 'cancelled', 'expired'),
            'confirmed': ('in_production', 'ready_delivery', 'cancelled'),
            'in_production': ('ready_delivery', 'cancelled'),
            'ready_delivery': ('delivered', 'cancelled'),
            'delivered': (),
            'expired': ('draft',),
            'cancelled': ('draft',),
        }

    def _transition_to(self, target_state):
        """Move bookings through the approved lifecycle only."""
        allowed = self._allowed_state_targets()
        labels = dict(self._fields['state'].selection)
        for rec in self:
            if rec.state == target_state:
                continue
            if target_state not in allowed.get(rec.state, ()):
                raise ValidationError(_(
                    'Cannot move booking %(booking)s from %(current)s to %(target)s.'
                ) % {
                    'booking': rec.name,
                    'current': labels.get(rec.state, rec.state),
                    'target': labels.get(target_state, target_state),
                })
        self.with_context(bs_booking_bypass_state_guard=True).write({'state': target_state})
        self._sync_lead_outcome(target_state)
        return True

    def _has_successful_payment(self):
        self.ensure_one()
        return bool(
            self.deposit_paid
            or self.transaction_ids.filtered(lambda tx: tx.state in ('done', 'authorized'))
        )

    @api.depends('deposit_amount', 'deposit_paid')
    def _compute_deposit_remaining(self):
        for rec in self:
            rec.deposit_remaining = (rec.deposit_amount or 0) - (rec.deposit_paid or 0)

    @api.depends('sale_order_id', 'sale_order_id.amount_total', 'sale_order_id.invoice_ids')
    def _compute_order_amounts(self):
        for rec in self:
            so = rec.sale_order_id
            rec.amount_total = so.amount_total if so else (rec.car_price or 0.0)
            rec.invoice_ids = so.invoice_ids if so else False
            rec.invoice_count = len(so.invoice_ids) if so else 0

    @api.depends('product_id', 'option_value_ids')
    def _compute_config_summary(self):
        for rec in self:
            parts = []
            if rec.product_id and rec.product_id.product_template_attribute_value_ids:
                parts += rec.product_id.product_template_attribute_value_ids.mapped('name')
            parts += rec.option_value_ids.mapped('name')
            rec.config_summary = ', '.join(p for p in parts if p)

    # === Phone helpers (shared by funnel, tracking and throttle) ===
    @api.model
    def _normalize_phone(self, phone):
        """Strip separators (spaces, dashes, dots, parentheses) so user input
        like '081-234 5678' compares equal to a stored '0812345678'."""
        return re.sub(r'[\s\-().]', '', phone or '')

    @api.model
    def _is_valid_phone(self, phone):
        return bool(PHONE_RE.match(self._normalize_phone(phone)))

    # === Constraints ===
    @api.constrains('customer_phone')
    def _check_phone(self):
        for rec in self:
            if rec.customer_phone and not self._is_valid_phone(rec.customer_phone):
                raise ValidationError(_(
                    'Please enter a valid phone number (7–15 digits, optional +, '
                    'spaces and dashes allowed).'))

    # === CRUD ===
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('bs.car.booking') or '/'
            if vals.get('website_id') and not vals.get('company_id'):
                website = self.env['website'].browse(vals['website_id'])
                vals['company_id'] = website.company_id.id or self.env.company.id
        return super().create(vals_list)

    def write(self, vals):
        """Enforce the booking lifecycle at the ORM level: a direct state change
        (RPC, scripts, imports) must follow an allowed transition. Internal
        transitions go through ``_transition_to`` which sets the bypass flag."""
        if 'state' in vals and not self.env.context.get('bs_booking_bypass_state_guard'):
            target = vals['state']
            allowed = self._allowed_state_targets()
            labels = dict(self._fields['state'].selection)
            for rec in self:
                if rec.state != target and target not in allowed.get(rec.state, ()):
                    raise ValidationError(_(
                        'Cannot move booking %(booking)s from %(current)s to %(target)s.'
                    ) % {
                        'booking': rec.name or rec.id,
                        'current': labels.get(rec.state, rec.state),
                        'target': labels.get(target, target),
                    })
        res = super().write(vals)
        # Backend edits to the promised date follow through to the sale order.
        if 'estimated_delivery_date' in vals:
            self._sync_delivery_commitment()
        return res

    @api.onchange('model_id')
    def _onchange_model_id(self):
        """Prefill brand, deposit and currency from the model for backend entry."""
        if self.model_id:
            self.brand_id = self.model_id.brand_id
            if self.model_id.currency_id:
                self.currency_id = self.model_id.currency_id
            if not self.deposit_amount:
                self.deposit_amount = self.model_id.deposit_amount

    # === Actions ===
    def _otp_throttle_or_raise(self, phone, email=None):
        """Shared OTP rate-limit, raises ValidationError when exceeded:
          * resend cooldown vs the last OTP for THIS booking (server-side; the
            JS countdown is cosmetic only), and
          * a per-contact hourly cap across ALL bookings/purposes (a per-booking
            cooldown alone is trivially bypassed by starting a new booking).
            The cap counts per phone AND, for email delivery, per address —
            protecting against both SMS-cost abuse and email bombing.
        """
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        # Per-website limits (Settings → Website → Car Booking); the ICPs stay
        # as fallback for website-less bookings. 0 disables the given limit.
        website = self.website_id
        if website:
            cooldown = max(website.bs_otp_resend_seconds, 0)
        else:
            try:
                cooldown = max(int(ICP.get_param('bs_car_booking.otp_resend_seconds', '30')), 0)
            except (TypeError, ValueError):
                cooldown = 30
        last_otp = self.otp_ids.sorted('create_date', reverse=True)[:1]
        if cooldown and last_otp and last_otp.create_date:
            elapsed = (fields.Datetime.now() - last_otp.create_date).total_seconds()
            if elapsed < cooldown:
                raise ValidationError(_(
                    'Please wait %s seconds before requesting another code.'
                ) % int(cooldown - elapsed))

        if website:
            max_per_hour = max(website.bs_otp_max_per_hour, 0)
        else:
            try:
                max_per_hour = max(int(ICP.get_param('bs_car_booking.otp_max_per_hour', '5')), 0)
            except (TypeError, ValueError):
                max_per_hour = 5
        if not max_per_hour:
            return
        Otp = self.env['bs.car.booking.otp'].sudo()
        since = fields.Datetime.now() - timedelta(hours=1)
        norm_phone = self._normalize_phone(phone)
        norm_email = (email or '').strip().lower()
        for domain, error in (
            ([('phone', '=', norm_phone)] if norm_phone else None,
             _('Too many verification codes requested for this number. Please try again later.')),
            ([('email', '=ilike', norm_email)] if norm_email else None,
             _('Too many verification codes requested for this email. Please try again later.')),
        ):
            if domain and Otp.search_count(domain + [('create_date', '>=', since)]) >= max_per_hour:
                raise ValidationError(error)

    def _resolve_otp_channel(self, channel=None):
        """Final OTP delivery channel for this booking.

        The website mode comes first: 'sms' / 'email' fix the channel
        regardless of what the client sent ('email' is the no-SMS-gateway
        mode). In 'both' mode the customer decides: explicit *channel*
        (their pick on this request) → the last OTP's channel (a resend
        must keep their earlier choice, not silently flip) → SMS.
        """
        self.ensure_one()
        Otp = self.env['bs.car.booking.otp'].sudo()
        website_channel = Otp._get_otp_channel(self.website_id)
        if website_channel in ('sms', 'email'):
            return website_channel
        if channel in ('sms', 'email'):
            return channel
        # Explicit sort: an in-transaction One2many cache does NOT apply the
        # comodel's _order, so otp_ids[:1] may be the OLDEST record.
        last_otp = self.otp_ids.sorted('id', reverse=True)[:1]
        return last_otp.channel if last_otp else 'sms'

    def action_send_otp(self, channel=None):
        """Send the verification OTP via the resolved channel (SMS/email).
        *channel* is the customer's choice from the UI, when given."""
        self.ensure_one()
        if self.state not in ('draft', 'otp_pending'):
            raise ValidationError(_('OTP can only be sent before the phone is verified.'))
        if self.phone_verified:
            raise ValidationError(_('This phone number is already verified.'))
        if not self.customer_phone:
            raise ValidationError(_('Customer phone number is required.'))
        if not self._is_valid_phone(self.customer_phone):
            raise ValidationError(_('The phone number on this booking is not valid.'))
        channel = self._resolve_otp_channel(channel)
        if channel == 'email' and not self.customer_email:
            raise ValidationError(_('An email address is required to receive the verification code.'))
        destination = (self.customer_email if channel == 'email'
                       else self.customer_phone)

        # Rate-limit (resend cooldown + per-contact hourly cap). Shared with the
        # tracking-OTP flow so both funnel verification and tracking re-auth are
        # protected against SMS bombing / cost abuse.
        self._otp_throttle_or_raise(self.customer_phone, email=self.customer_email)

        otp_record = self.env['bs.car.booking.otp'].sudo().send_otp(
            self.customer_phone, self.id, purpose='booking',
            channel=channel, email=self.customer_email,
        )
        self._transition_to('otp_pending')

        if self.env['ir.config_parameter'].sudo().get_param('bs_car_booking.log_otp') == '1':
            _logger.info('OTP generated for %s (otp_id=%s)', destination, otp_record.id)

        message = (_('Verification code sent to %s. Please check your inbox.')
                   if channel == 'email'
                   else _('Verification code sent to %s. Please check your phone.'))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('OTP Sent'),
                'message': message % destination,
                'type': 'info',
                'sticky': False,
            }
        }

    def action_verify_otp(self, otp_code):
        """Verify the OTP code. PDPA consent is captured earlier (at the phone
        step, before the SMS); on success a CRM lead is auto-created."""
        self.ensure_one()
        if self.phone_verified and self.state in ('otp_verified', 'payment_pending'):
            return {'success': True, 'message': _('Phone already verified.')}
        if self.state != 'otp_pending':
            raise ValidationError(_('OTP can only be verified while the booking is waiting for OTP.'))
        if not self.pdpa_consent:
            return {'success': False, 'error': _('Privacy consent (PDPA) is required.')}
        # Newest pending code only (sorted explicitly — see _resolve_otp_channel):
        # after a resend the older still-pending codes must not be accepted.
        otp = self.otp_ids.sorted('id', reverse=True).filtered(
            lambda o: o.state == 'pending' and o.purpose_code == 'booking')
        if not otp:
            raise ValidationError(_('No pending OTP found. Please request a new one.'))

        result = otp[0].verify_otp(otp_code)
        if result['success']:
            self.phone_verified = True
            self.otp_verified_channel = otp[0].channel
            self._transition_to('otp_verified')
            self._create_crm_lead()
        return result

    # === Partner / configuration / sale-order backbone ===
    def _ensure_partner(self):
        """Find or create the res.partner for this booking's customer."""
        self.ensure_one()
        if self.partner_id:
            return self.partner_id
        Partner = self.env['res.partner'].sudo()
        partner = self.env['res.partner']
        if self.customer_email:
            partner = Partner.search([('email', '=', self.customer_email)], limit=1)
        if not partner and self.customer_phone:
            phone_domain = [('phone', '=', self.customer_phone)]
            if 'mobile' in Partner._fields:
                phone_domain = ['|', *phone_domain, ('mobile', '=', self.customer_phone)]
            partner = Partner.search(phone_domain, limit=1)
        if not partner:
            if self.customer_type == 'company':
                # Company => is_company + VAT so the deposit invoice is a proper
                # tax invoice carrying the company's Tax ID.
                partner_vals = {
                    'name': self.company_name or self.customer_name or _('Company Customer'),
                    'is_company': True,
                    'vat': self.tax_id or False,
                    'email': self.customer_email or False,
                    'phone': self.customer_phone or False,
                    'street': self.customer_address or False,
                }
                if 'mobile' in Partner._fields:
                    partner_vals['mobile'] = self.customer_phone or False
                partner = Partner.create(partner_vals)
                if self.contact_person:
                    Partner.create({
                        'name': self.contact_person,
                        'parent_id': partner.id,
                        'type': 'contact',
                        'email': self.customer_email or False,
                        'phone': self.customer_phone or False,
                    })
            else:
                partner_vals = {
                    'name': self.customer_name or _('Website Customer'),
                    'email': self.customer_email or False,
                    'phone': self.customer_phone or False,
                    'street': self.customer_address or False,
                    'comment': self.customer_nrc and _('NRC/ID: %s') % self.customer_nrc or False,
                }
                if 'mobile' in Partner._fields:
                    partner_vals['mobile'] = self.customer_phone or False
                partner = Partner.create(partner_vals)
        else:
            # Reuse an existing partner but make sure a company booking stamps
            # the Tax ID for the invoice.
            if self.customer_type == 'company' and self.tax_id and not partner.vat:
                partner.write({'vat': self.tax_id, 'is_company': True})
        self.partner_id = partner
        return partner

    # === Customer requirements (configurable, per customer type) ===
    def _applicable_document_types(self, customer_type=None):
        """Active document types required/optional for the given customer type."""
        ctype = customer_type or self.customer_type or 'individual'
        company = self.company_id or self.env.company
        types = self.env['bs.car.document.type'].sudo().search([
            ('company_id', 'in', [False, company.id]),
            ('active', '=', True),
        ])
        return types.filtered(lambda d: d._matches(ctype))

    def _applicable_agreements(self, customer_type=None):
        """Active agreements applicable to the given customer type."""
        ctype = customer_type or self.customer_type or 'individual'
        company = self.company_id or self.env.company
        agreements = self.env['bs.car.agreement'].sudo().search([
            ('company_id', 'in', [False, company.id]),
            ('active', '=', True),
        ])
        return agreements.filtered(lambda a: a._matches(ctype))

    def _missing_requirements(self, customer_type):
        """Server-side validation: returns a list of human messages for any
        unmet requirement (type fields, required documents, required agreements)."""
        self.ensure_one()
        errors = []
        if customer_type == 'company':
            if not (self.company_name or '').strip():
                errors.append(_('Company name is required.'))
            if not (self.tax_id or '').strip():
                errors.append(_('Tax ID is required for a company.'))
            if not (self.contact_person or '').strip():
                errors.append(_('Contact person is required for a company.'))
        else:
            if not (self.customer_name or '').strip():
                errors.append(_('Full name is required.'))
            if not (self.customer_nrc or '').strip():
                errors.append(_('NRC/ID number is required.'))
        # Required documents uploaded?
        uploaded_type_ids = set(self.document_ids.mapped('document_type_id').ids)
        for dtype in self._applicable_document_types(customer_type).filtered('required'):
            if dtype.id not in uploaded_type_ids:
                errors.append(_('Document "%s" is required.') % dtype.name)
        # Required agreements accepted?
        accepted_ids = set(self.agreement_ids.filtered('accepted').mapped('agreement_id').ids)
        for agr in self._applicable_agreements(customer_type).filtered('required'):
            if agr.id not in accepted_ids:
                errors.append(_('Please accept "%s".') % agr.name)
        return errors

    def _apply_configuration(self, ptav_ids):
        """Resolve selected template attribute values to a variant + options.

        :param ptav_ids: list of product.template.attribute.value ids selected
            across all attributes (Standard Package + Color/Interior/Wheels/Add-ons).
        """
        self.ensure_one()
        model = self.model_id
        if not model.product_tmpl_id:
            model.sudo().action_generate_product()
        tmpl = model.product_tmpl_id
        trim_attr = self.env.ref('bs_car_booking.attr_trim')

        selected = tmpl.attribute_line_ids.product_template_value_ids.filtered(
            lambda p: p.id in (ptav_ids or []))
        trim_ptav = selected.filtered(lambda p: p.attribute_id == trim_attr)[:1]
        option_ptavs = selected.filtered(lambda p: p.attribute_id != trim_attr)

        # Only the Standard Package attribute creates variants; resolve/create by package while
        # ignoring no-variant attributes (so the combination is "possible").
        variant = tmpl._get_variant_for_combination(trim_ptav) if trim_ptav else tmpl.env['product.product']
        if not variant and trim_ptav and tmpl.has_dynamic_attributes() \
                and tmpl._is_combination_possible(trim_ptav, ignore_no_variant=True):
            variant = self.env['product.product'].sudo().create({
                'product_tmpl_id': tmpl.id,
                'product_template_attribute_value_ids': [(6, 0, trim_ptav.ids)],
            })
        if not variant:
            variant = tmpl.product_variant_id  # base variant fallback

        self.write({
            'product_id': variant.id if variant else False,
            'option_value_ids': [(6, 0, option_ptavs.ids)],
        })
        return variant

    def _ensure_sale_order(self):
        """Create (once) the sale.order that backs this booking."""
        self.ensure_one()
        if self.sale_order_id:
            return self.sale_order_id
        if not self.phone_verified:
            raise ValidationError(_('Please verify the customer phone before checkout.'))
        if self.state not in ('otp_verified', 'payment_pending'):
            raise ValidationError(_('A sale order can only be created after phone verification.'))
        if not self.product_id:
            raise ValidationError(_('Please configure the car before checkout.'))
        partner = self._ensure_partner()
        order_vals = {
            'partner_id': partner.id,
            'client_order_ref': self.name,
            'company_id': self.company_id.id,
            'order_line': [(0, 0, {
                'product_id': self.product_id.id,
                'product_uom_qty': 1.0,
                'product_no_variant_attribute_value_ids': [(6, 0, self.option_value_ids.ids)],
            })],
        }
        if self.website_id and 'website_id' in self.env['sale.order']._fields:
            order_vals['website_id'] = self.website_id.id
        # Native CRM<->Sale link (sale_crm): ties the order to the opportunity
        # so the lead shows Quotations/Orders + revenue automatically.
        if self.lead_id and 'opportunity_id' in self.env['sale.order']._fields:
            order_vals['opportunity_id'] = self.lead_id.id
        order = self.env['sale.order'].sudo().with_company(self.company_id).create(order_vals)
        self.sudo().write({
            'sale_order_id': order.id,
            'car_price': order.amount_total,
        })
        self._update_crm_lead()
        return order

    # === CRM lead (auto-created after OTP + PDPA consent) ===
    def _prepare_crm_lead_vals(self):
        self.ensure_one()
        model = self.model_id
        desc = []
        if self.config_summary:
            desc.append(_('Configuration: %s') % self.config_summary)
        if self.dealer_id:
            desc.append(_('Preferred dealer: %s') % self.dealer_id.name)
        if self.customer_nrc:
            desc.append(_('NRC/ID: %s') % self.customer_nrc)
        vals = {
            'name': _('Car Booking – %(brand)s %(model)s (%(ref)s)') % {
                'brand': model.brand_id.name or '', 'model': model.name or '', 'ref': self.name,
            },
            'contact_name': self.customer_name or False,
            'phone': self.customer_phone or False,
            'email_from': self.customer_email or False,
            'description': '<br/>'.join(desc) or False,
            'expected_revenue': self.amount_total or self.car_price or model.base_price or 0.0,
            'partner_id': self.partner_id.id or False,
            'bs_car_booking_id': self.id,
            'company_id': self.company_id.id,
        }
        medium = self.env.ref('utm.utm_medium_website', raise_if_not_found=False)
        if medium:
            vals['medium_id'] = medium.id
        return vals

    def _create_crm_lead(self):
        """Create the CRM lead once (idempotent), after OTP + PDPA consent."""
        self.ensure_one()
        if self.lead_id or not self.pdpa_consent:
            return self.lead_id
        lead = self.env['crm.lead'].sudo().create(self._prepare_crm_lead_vals())
        self.sudo().lead_id = lead.id
        return lead

    def _update_crm_lead(self):
        """Enrich the lead as more info becomes available (name, email, revenue)."""
        self.ensure_one()
        if not self.lead_id:
            return
        lead = self.lead_id.sudo()
        lead.write({
            'contact_name': self.customer_name or lead.contact_name,
            'email_from': self.customer_email or lead.email_from,
            'partner_id': self.partner_id.id or lead.partner_id.id,
            'expected_revenue': self.amount_total or self.car_price or lead.expected_revenue,
        })

    def _sync_lead_outcome(self, target_state):
        """Keep the linked CRM lead in step with the booking outcome:
        confirmed -> won, expired/cancelled -> lost, reopened (draft) -> restored.
        Defensive on purpose: a CRM hiccup must never abort a booking transition
        or the nightly expiry cron."""
        for rec in self:
            lead = rec.lead_id.sudo()
            if not lead:
                continue
            try:
                if target_state == 'confirmed':
                    if lead.probability < 100:
                        lead.action_set_won()
                elif target_state in ('expired', 'cancelled'):
                    if lead.active:
                        lead.action_set_lost()
                elif target_state == 'draft' and not lead.active:
                    # booking reopened from expired/cancelled -> revive the lead
                    lead.action_unarchive()
            except Exception as exc:  # noqa: BLE001 - CRM must never block the booking
                _logger.warning('CRM lead sync failed for booking %s -> %s: %s',
                                rec.name, target_state, str(exc))

    def action_submit_rating(self, rating, comment=''):
        """Store customer rating (1-5) and push to the linked CRM lead."""
        self.ensure_one()
        if not (1 <= int(rating) <= 5):
            raise ValidationError(_('Rating must be between 1 and 5.'))
        if self.state not in ('confirmed', 'in_production', 'ready_delivery', 'delivered'):
            raise ValidationError(_('Ratings can only be submitted for confirmed bookings.'))
        self.sudo().write({
            'rating': int(rating),
            'rating_comment': (comment or '').strip() or False,
            'rating_date': fields.Datetime.now(),
        })
        if self.lead_id:
            self.lead_id.sudo().write({
                'bs_booking_rating': int(rating),
                'bs_booking_rating_comment': (comment or '').strip() or False,
            })

    def action_view_lead(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crm.lead',
            'res_id': self.lead_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _on_deposit_paid(self, transaction):
        """Called from payment.transaction._post_process when a deposit is paid."""
        self.ensure_one()
        so = self.sale_order_id
        paid_amount = (so.amount_paid if so else 0.0) or transaction.amount
        self.write({'deposit_paid': paid_amount})
        if self.deposit_amount and float_compare(
            self.deposit_paid,
            self.deposit_amount,
            precision_rounding=self.currency_id.rounding,
        ) < 0:
            _logger.info(
                'Booking %s deposit payment is partial: paid=%s required=%s',
                self.name, self.deposit_paid, self.deposit_amount,
            )
            return False
        if self.state != 'payment_pending':
            _logger.info('Booking %s paid while in state %s; confirmation skipped.',
                         self.name, self.state)
            return False
        self._transition_to('confirmed')
        self._set_estimated_delivery()
        self._update_crm_lead()
        self._notify_confirmed()
        return True

    def _send_booking_notification(self, sms_template_ref, mail_template_ref):
        """Send both SMS and email using the provided template xmlids.
        Failures are logged, never raised — notifications must not block."""
        self.ensure_one()
        # --- SMS ---
        # Only send SMS when the phone was truly verified via SMS OTP.
        # otp_verified_channel == 'email' means the phone has NOT been
        # proven to receive SMS (email fallback, e.g. no SMS gateway).
        if self.customer_phone and self.otp_verified_channel == 'sms' and sms_template_ref:
            try:
                tmpl = self.env.ref(sms_template_ref, raise_if_not_found=False)
                if tmpl:
                    body = tmpl._render_field('body', [self.id])[self.id]
                    self.env['sms.sms'].sudo().create({
                        'number': self.customer_phone, 'body': body,
                    }).send()
            except Exception as e:
                _logger.warning('Failed to send SMS [%s]: %s', sms_template_ref, str(e))
        # --- Email ---
        if self.customer_email and mail_template_ref:
            try:
                tmpl = self.env.ref(mail_template_ref, raise_if_not_found=False)
                if tmpl:
                    subject = tmpl._render_field('subject', [self.id])[self.id]
                    body_html = tmpl._render_field('body_html', [self.id])[self.id]
                    vals = {
                        'subject': subject,
                        'body_html': body_html,
                        'email_to': self.customer_email,
                        # Honour the template flag: OTP mails are auto-deleted,
                        # confirm/delivery mails are kept as audit trail.
                        'auto_delete': tmpl.auto_delete,
                    }
                    company = (self.website_id.company_id
                               or self.company_id
                               or self.env.company).sudo()
                    email = (company.email
                             or self.env['ir.mail_server'].sudo()._get_default_from_address())
                    if email:
                        # Display name = brand (website name), not the company
                        # legal name — that one belongs on tax invoices.
                        brand = self.website_id.name or company.name
                        vals['email_from'] = (
                            formataddr((brand, email)) if brand else email)
                    self.env['mail.mail'].sudo().create(vals).send(raise_exception=False)
            except Exception as e:
                _logger.warning('Failed to send email [%s]: %s', mail_template_ref, str(e))

    def _notify_confirmed(self):
        self._send_booking_notification(
            'bs_car_booking.sms_template_booking_confirmed',
            'bs_car_booking.mail_template_booking_confirmed',
        )

    # === Delivery estimate ===
    def _get_package_variant(self):
        """The bs.car.variant (standard package) behind this booking, found by
        the configured product's Trim attribute value; falls back to the
        model's first active package."""
        self.ensure_one()
        trim_attr = self.env.ref('bs_car_booking.attr_trim', raise_if_not_found=False)
        variants = self.model_id.variant_ids.filtered('active')
        if self.product_id and trim_attr:
            ptav = self.product_id.product_template_attribute_value_ids.filtered(
                lambda v: v.attribute_id == trim_attr)[:1]
            if ptav:
                match = variants.filtered(lambda v: v.name == ptav.name)[:1]
                if match:
                    return match
        return variants[:1]

    def _set_estimated_delivery(self):
        """On confirmation: default the promised date from the package's
        ``estimated_delivery_days`` (kept when staff already set one) and
        mirror it on the sale order."""
        for booking in self:
            if not booking.estimated_delivery_date:
                variant = booking._get_package_variant()
                days = variant.estimated_delivery_days or 30
                booking.estimated_delivery_date = (
                    fields.Date.context_today(booking) + timedelta(days=days))
        self._sync_delivery_commitment()

    def _sync_delivery_commitment(self):
        """Mirror the booking's promised date onto the sale order's
        ``commitment_date`` — the native "Delivery Date" the rest of Odoo
        (SO form, reports, stock scheduling when installed) understands."""
        for booking in self:
            so = booking.sale_order_id
            if so and booking.estimated_delivery_date:
                so.commitment_date = fields.Datetime.to_datetime(
                    booking.estimated_delivery_date)

    def action_confirm_booking(self):
        """Confirm a booking whose required deposit has already been received."""
        self.ensure_one()
        if self.state != 'payment_pending':
            raise ValidationError(_('Only bookings awaiting deposit can be confirmed manually.'))
        if not self.sale_order_id:
            raise ValidationError(_('Create the sale order before confirming this booking.'))
        if self.deposit_amount and float_compare(
            self.deposit_paid,
            self.deposit_amount,
            precision_rounding=self.currency_id.rounding,
        ) < 0:
            raise ValidationError(_('The required deposit has not been paid yet.'))
        if self.sale_order_id and self.sale_order_id.state in ('draft', 'sent'):
            self.sale_order_id.with_context(send_email=False).action_confirm()
        self._transition_to('confirmed')
        self._set_estimated_delivery()
        self._notify_confirmed()
        return True

    def action_start_production(self):
        """Move a confirmed booking into dealer/import/preparation work."""
        self.ensure_one()
        if self.state != 'confirmed':
            raise ValidationError(_('Only confirmed bookings can enter production/preparation.'))
        self._transition_to('in_production')
        return True

    def action_ready_delivery(self):
        """Mark the booked vehicle ready for customer handover."""
        self.ensure_one()
        if self.state not in ('confirmed', 'in_production'):
            raise ValidationError(_('Only confirmed or in-production bookings can be ready for delivery.'))
        self._transition_to('ready_delivery')
        self._notify_ready_delivery()
        return True

    def _notify_ready_delivery(self):
        self._send_booking_notification(
            'bs_car_booking.sms_template_ready_delivery',
            'bs_car_booking.mail_template_ready_delivery',
        )

    def action_view_sale_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_otps(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('OTP Records'),
            'res_model': 'bs.car.booking.otp',
            'view_mode': 'list,form',
            'domain': [('booking_id', '=', self.id)],
            'context': {'create': False},
        }

    def action_view_invoices(self):
        self.ensure_one()
        invoices = self.invoice_ids
        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'name': _('Deposit Invoices'),
        }
        if len(invoices) == 1:
            action.update(res_id=invoices.id, view_mode='form')
        else:
            action.update(view_mode='list,form', domain=[('id', 'in', invoices.ids)])
        return action

    def action_cancel(self):
        """Cancel the booking."""
        self.ensure_one()
        if self.state in ('delivered',):
            raise ValidationError(_('Cannot cancel a delivered booking.'))
        if self._has_successful_payment():
            raise ValidationError(_(
                'This booking already has a successful payment. Process the refund/accounting '
                'cancellation first, then cancel the booking.'
            ))
        if self.sale_order_id and self.sale_order_id.state not in ('cancel',):
            if self.sale_order_id.state in ('draft', 'sent', 'sale'):
                self.sale_order_id.action_cancel()
            else:
                raise ValidationError(_('Cancel or settle the linked sale order before cancelling.'))
        self._transition_to('cancelled')

    def action_set_draft(self):
        """Reset to draft."""
        self.ensure_one()
        if self.state not in ('cancelled', 'expired'):
            raise ValidationError(_('Only cancelled or expired bookings can be reset to draft.'))
        if self._has_successful_payment():
            raise ValidationError(_('Paid bookings cannot be reset to draft.'))
        if self.sale_order_id and self.sale_order_id.state not in ('cancel',):
            raise ValidationError(_('Cancel the linked sale order before resetting to draft.'))
        self.otp_ids.filtered(lambda otp: otp.state == 'pending').write({'state': 'expired'})
        self.write({
            'phone_verified': False,
            'sale_order_id': False,
            'deposit_paid': 0.0,
        })
        self._transition_to('draft')

    def action_mark_delivered(self):
        """Mark booking as delivered."""
        self.ensure_one()
        if self.state != 'ready_delivery':
            raise ValidationError(_('Only bookings ready for delivery can be delivered.'))
        self._transition_to('delivered')
        self.actual_delivery_date = fields.Date.today()
        return True

    @api.model
    def action_expire_stale_bookings(self):
        """Expire unpaid bookings that were abandoned before confirmation.

        Each booking's website may set its own expiry window (Settings →
        Website → Car Booking). Falls back to the global System Parameter
        ``bs_car_booking.expire_after_hours`` (default 72) when the website
        has no value configured."""
        global_default = self.env['ir.config_parameter'].sudo().get_param(
            'bs_car_booking.expire_after_hours', '72')
        try:
            global_default_hours = max(int(global_default), 1)
        except (TypeError, ValueError):
            global_default_hours = 72

        stale_bookings = self.sudo().search([
            ('state', 'in', ('draft', 'otp_pending', 'otp_verified', 'payment_pending')),
            ('deposit_paid', '=', 0.0),
        ])
        now = fields.Datetime.now()
        expired_count = 0
        for booking in stale_bookings:
            # In cron context get_current_website() would be arbitrary — only
            # the booking's own website can override the global default.
            hours = booking.website_id.bs_booking_expire_hours or global_default_hours
            if not booking.create_date:
                continue
            cutoff = booking.create_date + timedelta(hours=max(hours, 1))
            if now < cutoff:
                continue
            if booking._has_successful_payment():
                continue
            if booking.sale_order_id and booking.sale_order_id.state in ('draft', 'sent'):
                booking.sale_order_id.action_cancel()
            elif booking.sale_order_id and booking.sale_order_id.state not in (False, 'cancel'):
                continue
            booking.otp_ids.filtered(lambda otp: otp.state == 'pending').write({'state': 'expired'})
            booking._transition_to('expired')
            expired_count += 1
        return expired_count

    # === Portal / website helpers ===
    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = f'/my/booking/{rec.id}'

    # === Portal helpers ===
