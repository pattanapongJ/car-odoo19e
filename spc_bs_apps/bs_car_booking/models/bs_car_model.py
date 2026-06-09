# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

import json
import logging
import re
from datetime import date, datetime, timedelta

from markupsafe import Markup

from odoo import api, fields, models, tools
from odoo.addons.website.models import ir_http
from odoo.http import request

YOUTUBE_RE = re.compile(r'(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|shorts/|v/))([\w-]{11})')
VIMEO_RE = re.compile(r'vimeo\.com/(?:video/)?(\d+)')

_logger = logging.getLogger(__name__)

# Attribute xmlids whose values are sourced from per-model option lines.
OPTION_ATTRIBUTE_REFS = (
    'bs_car_booking.attr_color',
    'bs_car_booking.attr_interior',
    'bs_car_booking.attr_wheels',
    'bs_car_booking.attr_addons',
)

# (option value xmlid, default extra price) used to seed demo configurations.
DEMO_OPTION_PRICES = [
    ('val_color_white', 0), ('val_color_black', 0), ('val_color_grey', 0),
    ('val_color_blue', 1500), ('val_color_red', 2000), ('val_color_silver', 1500),
    ('val_int_black', 0), ('val_int_white', 1500), ('val_int_cream', 2000),
    ('val_wheel_aero', 0), ('val_wheel_sport', 1500),
    ('val_wheel_induction', 2500), ('val_wheel_perf', 4000),
    ('val_addon_fsd', 8000), ('val_addon_tow', 1000),
    ('val_addon_connect', 500), ('val_addon_ppf', 1500),
]


class BsCarModel(models.Model):
    _name = 'bs.car.model'
    _description = 'Car Model'
    _inherit = ['website.seo.metadata']
    _order = 'brand_id, sequence, name'

    def _default_website_meta(self):
        """Per-car SEO/OpenGraph defaults: car image as og:image, model
        description as the meta description, product-style og:type."""
        self.ensure_one()
        website = ir_http.get_request_website()
        if website:
            res = super()._default_website_meta()
        else:
            res = {
                'default_opengraph': {
                    'og:type': 'product',
                    'og:title': self.name,
                },
                'default_twitter': {
                    'twitter:card': 'summary_large_image',
                    'twitter:title': self.name,
                },
            }
        desc = self.description and tools.html2plaintext(self.description).strip()[:200] or ''
        res['default_opengraph']['og:type'] = 'product'
        if desc:
            res['default_opengraph']['og:description'] = desc
            res['default_twitter']['twitter:description'] = desc
        if self.image:
            img_url = self.env['website'].image_url(self, 'image')
            res['default_opengraph']['og:image'] = img_url
            res['default_twitter']['twitter:image'] = img_url
        return res

    def _website_jsonld(self):
        """Schema.org Vehicle/Product structured data for rich search results.
        Returned as Markup so the template emits it raw inside a JSON-LD script."""
        self.ensure_one()
        try:
            website = request.website
        except (AttributeError, RuntimeError):
            website = False
        if not website:
            return Markup('')
        base = website.domain or request.httprequest.url_root.rstrip('/')
        currency = self.currency_id or website.company_id.sudo().currency_id
        data = {
            '@context': 'https://schema.org',
            '@type': 'Vehicle',
            'name': f'{self.brand_id.name} {self.name}'.strip(),
            'brand': {'@type': 'Brand', 'name': self.brand_id.name or ''},
            'url': f'{base}/car/{self.id}',
            'vehicleConfiguration': self.body_type or '',
            'numberOfDoors': None,
            'seatingCapacity': self.seats or None,
        }
        if self.description:
            data['description'] = tools.html2plaintext(self.description).strip()[:500]
        if self.image:
            data['image'] = request.website.image_url(self, 'image')
        if self.base_price:
            data['offers'] = {
                '@type': 'Offer',
                'price': round(self.base_price, 2),
                'priceCurrency': currency.name or 'USD',
                'availability': 'https://schema.org/InStock',
                'url': f'{base}/car/{self.id}/book',
            }
        data = {k: v for k, v in data.items() if v not in (None, '', {})}
        return Markup(json.dumps(data))

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    brand_id = fields.Many2one('bs.car.brand', string='Brand', required=True, ondelete='cascade')
    
    # Model details
    body_type = fields.Selection([
        ('sedan', 'Sedan'),
        ('suv', 'SUV'),
        ('coupe', 'Coupe'),
        ('hatchback', 'Hatchback'),
        ('convertible', 'Convertible'),
        ('pickup', 'Pickup'),
        ('van', 'Van'),
    ], string='Body Type')
    
    description = fields.Html('Description', translate=True)
    highlight_features = fields.Text('Highlight Features', translate=True,
                                     help='Key features displayed on website, one per line')
    
    # Media
    image = fields.Image('Main Image', max_width=1920, max_height=1080)
    gallery_image_ids = fields.One2many('bs.car.model.image', 'model_id', string='Gallery')
    # Optional looping background video for the hero (mp4/webm). Stored as a
    # generic attachment (NOT an Image field), so video files are accepted.
    hero_video = fields.Binary('Hero Video', attachment=True,
                               help='Upload an .mp4/.webm to play as a looping hero background. '
                                    'Falls back to Main Image when empty.')
    hero_video_filename = fields.Char('Hero Video Filename')
    hero_video_url = fields.Char('Hero Video URL',
                                 help='Direct .mp4/.webm URL (e.g. a CDN) — alternative to uploading a file.')
    has_hero_video = fields.Boolean(compute='_compute_has_hero_video', store=True)
    hero_video_src = fields.Char('Hero Video Source', compute='_compute_hero_video_src',
                                 help='Resolved playable source: the uploaded file if any, else the URL.')

    @api.depends('hero_video')
    def _compute_has_hero_video(self):
        # Computed at write-time only; lets the website test presence without
        # loading the (potentially large) video binary on every page render.
        for rec in self:
            rec.has_hero_video = bool(rec.hero_video)

    hero_media_type = fields.Char(compute='_compute_hero_media',
                                  help="Resolved hero media: video / youtube / vimeo / image / none.")
    hero_embed_url = fields.Char(compute='_compute_hero_media',
                                 help="Embed URL for YouTube/Vimeo background players.")

    @api.depends('has_hero_video', 'hero_video_url')
    def _compute_hero_video_src(self):
        for rec in self:
            if rec.has_hero_video:
                rec.hero_video_src = '/web/content/bs.car.model/%s/hero_video' % rec.id
            else:
                rec.hero_video_src = rec.hero_video_url or False

    @api.depends('has_hero_video', 'hero_video_url', 'image')
    def _compute_hero_media(self):
        for rec in self:
            url = (rec.hero_video_url or '').strip()
            embed = False
            if rec.has_hero_video:
                mtype = 'video'
            elif url:
                yt = YOUTUBE_RE.search(url)
                vm = VIMEO_RE.search(url)
                if yt:
                    mtype, vid = 'youtube', yt.group(1)
                    embed = (f'https://www.youtube.com/embed/{vid}'
                             f'?autoplay=1&mute=1&loop=1&playlist={vid}'
                             '&controls=0&showinfo=0&modestbranding=1&rel=0'
                             '&playsinline=1&disablekb=1&fs=0&iv_load_policy=3')
                elif vm:
                    mtype, vid = 'vimeo', vm.group(1)
                    embed = f'https://player.vimeo.com/video/{vid}?background=1&autoplay=1&loop=1&muted=1'
                else:
                    mtype = 'video'  # treat as a direct .mp4/.webm URL
            else:
                mtype = 'image' if rec.image else 'none'
            rec.hero_media_type = mtype
            rec.hero_embed_url = embed
    
    # Pricing
    base_price = fields.Monetary('Base Price', currency_field='currency_id',
                                 help='Starting price displayed on website')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    deposit_amount = fields.Monetary('Deposit Amount', currency_field='currency_id',
                                     help='Required deposit for booking')
    
    # Specifications
    range_km = fields.Integer('Range (km)', help='Electric range or fuel range in km')
    acceleration = fields.Float('0-100 km/h (s)', digits=(3, 1))
    top_speed = fields.Integer('Top Speed (km/h)')
    seats = fields.Integer('Seats', default=5)
    
    # Variants
    variant_ids = fields.One2many('bs.car.variant', 'model_id', string='Variants')
    variant_count = fields.Integer(compute='_compute_variant_count')
    
    # Website
    website_published = fields.Boolean('Published on Website', default=True)
    website_featured = fields.Boolean('Featured on Home',
                                      help='Show this model in the home "Featured Model" section.')
    website_url = fields.Char('Website URL', compute='_compute_website_url')
    arrival_date = fields.Date('Arrival Date',
                               help='When this model arrived/launched. Drives the '
                                    '"Latest arrivals" section and the "New" badge.')
    is_new_arrival = fields.Boolean('New Arrival', compute='_compute_is_new_arrival',
                                    help='Arrived within the "new" window '
                                         '(System Parameter bs_car_booking.arrival_new_days, default 60).')

    @api.depends('arrival_date')
    def _compute_is_new_arrival(self):
        days = int(self.env['ir.config_parameter'].sudo().get_param(
            'bs_car_booking.arrival_new_days', 60))
        cutoff = fields.Date.context_today(self) - timedelta(days=days)
        for rec in self:
            rec.is_new_arrival = bool(rec.arrival_date and rec.arrival_date >= cutoff)

    @api.model
    def _get_latest_arrivals(self, limit=6):
        """Published models, newest first — by arrival date, then by creation.
        Models without an arrival date sort last (still shown)."""
        recs = self.sudo().search([('website_published', '=', True), ('active', '=', True)])
        recs = recs.sorted(
            key=lambda c: (c.arrival_date or date.min, c.create_date or datetime.min),
            reverse=True)
        return recs[:limit]

    @api.model
    def _get_website_featured(self):
        """Return the model to showcase on the home page: the flagged one,
        else the first published model."""
        base = [('website_published', '=', True), ('active', '=', True)]
        return (self.sudo().search([('website_featured', '=', True)] + base, limit=1)
                or self.sudo().search(base, order='sequence, id', limit=1))

    def _get_compare_rows(self):
        """Align the spec sheets of ``self`` for a side-by-side comparison.

        Spec labels are free-form per model, so we build the union of labels
        (in first-seen order) and look up each model's value for every label,
        filling gaps with an em-dash. ``values[i]`` corresponds to ``self[i]``.
        Returns a list of {'label', 'values'} dicts.
        """
        labels, seen, per_model = [], set(), []
        for car in self:
            by_label = {}
            for sp in car.spec_ids.sorted(lambda s: (s.sequence, s.id)):
                key = (sp.name or '').strip()
                if not key:
                    continue
                by_label.setdefault(key, sp)
                if key not in seen:
                    seen.add(key)
                    labels.append(key)
            per_model.append(by_label)
        rows = []
        for label in labels:
            values = [(m.get(label).display_value if m.get(label) else '—')
                      for m in per_model]
            rows.append({'label': label, 'values': values})
        return rows

    @api.model
    def _get_browse_facets(self):
        """Entry tiles for the home "Browse" section: body-type tiles (derived
        from published models) + price-band chips (thresholds from the system
        parameter ``bs_car_booking.browse_price_bands``, default 2M/4M).
        Empty bands are omitted. Each entry carries a representative model id
        for its image and a link into the filtered ``/cars`` listing."""
        models = self.sudo().search(
            [('website_published', '=', True), ('active', '=', True)], order='sequence, id')
        types = dict(self._fields['body_type'].selection)
        body = []
        for bt in dict.fromkeys(models.mapped('body_type')):
            if not bt:
                continue
            grp = models.filtered(lambda m: m.body_type == bt)
            rep = grp.filtered('image')[:1] or grp[:1]
            body.append({'label': types.get(bt, bt), 'key': bt,
                         'count': len(grp), 'model_id': rep.id})

        ICP = self.env['ir.config_parameter'].sudo()
        raw = ICP.get_param('bs_car_booking.browse_price_bands', '2000000,4000000')
        thresholds = sorted(float(x) for x in raw.split(',') if x.strip())
        sym = (models[:1].currency_id.symbol or '') if models else ''

        def fmt(n):
            return f'{sym}{n / 1_000_000:g}M' if n >= 1_000_000 else f'{sym}{n:g}'

        price = []
        edges = [0.0] + thresholds + [None]
        for i in range(len(edges) - 1):
            lo, hi = edges[i], edges[i + 1]
            grp = models.filtered(
                lambda m: (m.base_price or 0) >= lo and (hi is None or (m.base_price or 0) < hi))
            if not grp:
                continue
            if lo == 0 and hi:
                label, url = f'Under {fmt(hi)}', f'/cars?price_max={int(hi)}'
            elif hi is None:
                label, url = f'{fmt(lo)}+', f'/cars?price_min={int(lo)}'
            else:
                label, url = f'{fmt(lo)} – {fmt(hi)}', f'/cars?price_min={int(lo)}&price_max={int(hi)}'
            price.append({'label': label, 'url': url, 'count': len(grp)})
        return {'body': body, 'price': price}

    # === Commerce backbone (native product) ===
    product_tmpl_id = fields.Many2one('product.template', string='Configurable Product',
                                      copy=False, readonly=True,
                                      help='Generated product that powers pricing & ordering.')
    option_ids = fields.One2many('bs.car.model.option', 'model_id', string='Options',
                                 help='Selectable priced options (color, interior, wheels, add-ons).')
    spec_ids = fields.One2many('bs.car.model.spec', 'model_id', string='Specifications',
                               help='Technical spec sheet shown on the website (data-driven).')

    # --- Home "showcase" content, split per type so each maps to one
    #     home section. All point to bs.car.showcase.item via model_id; the
    #     domains are mutually exclusive (no record appears in two fields). ---
    showcase_item_ids = fields.One2many('bs.car.showcase.item', 'model_id', string='Showcase Items')
    stage_item_ids = fields.One2many(
        'bs.car.showcase.item', 'model_id', string='Model Stage Slides',
        domain=[('item_type', '=', 'stage')], context={'default_item_type': 'stage'})
    exterior_item_ids = fields.One2many(
        'bs.car.showcase.item', 'model_id', string='Exterior Colours',
        domain=[('item_type', '=', 'exterior')], context={'default_item_type': 'exterior'})
    interior_item_ids = fields.One2many(
        'bs.car.showcase.item', 'model_id', string='Interior Themes',
        domain=[('item_type', '=', 'interior')], context={'default_item_type': 'interior'})
    highlight_item_ids = fields.One2many(
        'bs.car.showcase.item', 'model_id', string='Highlight Cards',
        domain=[('item_type', '=', 'highlight')], context={'default_item_type': 'highlight'})
    cabin_item_ids = fields.One2many(
        'bs.car.showcase.item', 'model_id', string='Cabin Story',
        domain=[('item_type', '=', 'cabin')], context={'default_item_type': 'cabin'})
    story_ids = fields.One2many('bs.car.story', 'model_id', string='Stories')
    showcase_count = fields.Integer(compute='_compute_showcase_count')

    @api.depends('showcase_item_ids')
    def _compute_showcase_count(self):
        for rec in self:
            rec.showcase_count = len(rec.showcase_item_ids)

    def _compute_variant_count(self):
        for rec in self:
            rec.variant_count = len(rec.variant_ids)

    def _compute_website_url(self):
        for rec in self:
            rec.website_url = f'/car/{rec.id}'

    # === Product generation ===
    def _get_or_create_pav(self, attribute, name):
        """Get or create a product.attribute.value for a (per-model) trim name."""
        PAV = self.env['product.attribute.value']
        pav = PAV.search([('attribute_id', '=', attribute.id), ('name', '=', name)], limit=1)
        if not pav:
            pav = PAV.create({'attribute_id': attribute.id, 'name': name})
        return pav

    def _build_attribute_config(self):
        """Return {product.attribute: [(product.attribute.value, price_extra)]} for self."""
        self.ensure_one()
        trim_attr = self.env.ref('bs_car_booking.attr_trim')
        config = {}
        # Trim values come from the model's variants (name + price delta).
        for variant in self.variant_ids.filtered('active'):
            pav = self._get_or_create_pav(trim_attr, variant.name)
            extra = (variant.price or self.base_price or 0.0) - (self.base_price or 0.0)
            config.setdefault(trim_attr, []).append((pav, extra))
        # Other attributes come from option lines.
        for opt in self.option_ids:
            if opt.value_id and opt.attribute_id:
                config.setdefault(opt.attribute_id, []).append((opt.value_id, opt.price_extra))
        return config

    def _get_sale_tax(self):
        """Customer tax applied to the car product (so the deposit/down-payment
        invoice carries the right VAT). Driven by the system parameter
        ``bs_car_booking.sale_tax_id`` (e.g. Thailand VAT 7%), falling back to
        the company's default sale tax."""
        ICP = self.env['ir.config_parameter'].sudo()
        tax_id = ICP.get_param('bs_car_booking.sale_tax_id')
        if tax_id:
            tax = self.env['account.tax'].sudo().browse(int(tax_id)).exists()
            if tax:
                return tax
        return self.env.company.account_sale_tax_id

    def action_generate_product(self):
        """Create/refresh the product.template + attribute lines for each model."""
        Line = self.env['product.template.attribute.line']
        tax = self._get_sale_tax()
        for model in self:
            vals = {
                'name': f'{model.brand_id.name} {model.name}'.strip(),
                'type': 'consu',
                'list_price': model.base_price or 0.0,
                'bs_car_model_id': model.id,
            }
            # `is_published` only exists on product.template when website_sale is
            # installed. This module does NOT depend on website_sale (cars are
            # sold via the booking funnel, not the shop), so set it only if the
            # field is present — avoids "Invalid field is_published" on generate.
            if 'is_published' in self.env['product.template']._fields:
                vals['is_published'] = model.website_published
            if tax:
                vals['taxes_id'] = [(6, 0, tax.ids)]
            if model.image:
                vals['image_1920'] = model.image
            tmpl = model.product_tmpl_id
            if tmpl:
                tmpl.write(vals)
            else:
                tmpl = self.env['product.template'].create(vals)
                model.product_tmpl_id = tmpl

            config = model._build_attribute_config()
            for attr, pairs in config.items():
                value_ids = [p[0].id for p in pairs]
                line = tmpl.attribute_line_ids.filtered(lambda l: l.attribute_id == attr)
                if line:
                    line.value_ids = [(6, 0, value_ids)]
                else:
                    line = Line.create({
                        'product_tmpl_id': tmpl.id,
                        'attribute_id': attr.id,
                        'value_ids': [(6, 0, value_ids)],
                    })
                # Set per-model extra price on the generated template values.
                for pav, extra in pairs:
                    ptav = line.product_template_value_ids.filtered(
                        lambda v: v.product_attribute_value_id == pav)
                    if ptav and ptav.price_extra != extra:
                        ptav.price_extra = extra
        return True

    def action_open_product(self):
        self.ensure_one()
        if not self.product_tmpl_id:
            self.action_generate_product()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'res_id': self.product_tmpl_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # === Demo seeding (invoked from demo data) ===
    @api.model
    def _demo_seed(self):
        """Seed standard options on every model, generate products, and create
        one fully-paid sample booking for the portal demo. Best-effort."""
        Option = self.env['bs.car.model.option']
        for model in self.search([]):
            if not model.option_ids:
                for xmlid, price in DEMO_OPTION_PRICES:
                    val = self.env.ref('bs_car_booking.' + xmlid, raise_if_not_found=False)
                    if val:
                        Option.create({
                            'model_id': model.id, 'value_id': val.id, 'price_extra': price,
                        })
            try:
                model.action_generate_product()
            except Exception as e:  # noqa: BLE001
                _logger.warning('Demo: product generation failed for %s: %s', model.name, e)
        try:
            self._demo_sample_booking()
        except Exception as e:  # noqa: BLE001
            _logger.warning('Demo: sample booking skipped: %s', e)
        return True

    @api.model
    def _demo_sample_booking(self):
        model = self.env.ref('bs_car_booking.model_model3', raise_if_not_found=False)
        if not model or not model.product_tmpl_id:
            return
        Booking = self.env['bs.car.booking']
        if Booking.search_count([('model_id', '=', model.id),
                                 ('customer_email', '=', 'demo.buyer@example.com')]):
            return  # already seeded
        partner = self.env['res.partner'].search(
            [('email', '=', 'demo.buyer@example.com')], limit=1)
        if not partner:
            partner = self.env['res.partner'].create({
                'name': 'Demo Buyer', 'email': 'demo.buyer@example.com',
                'phone': '+95 9 123 456 789',
            })
        booking = Booking.create({
            'brand_id': model.brand_id.id, 'model_id': model.id,
            'customer_name': 'Demo Buyer', 'customer_phone': '+95 9 123 456 789',
            'customer_email': 'demo.buyer@example.com', 'phone_verified': True,
            'deposit_amount': model.deposit_amount, 'currency_id': model.currency_id.id,
            'partner_id': partner.id,
            'state': 'otp_verified',
        })
        tmpl = model.product_tmpl_id
        trim_attr = self.env.ref('bs_car_booking.attr_trim')
        color_attr = self.env.ref('bs_car_booking.attr_color')
        trim_ptav = tmpl.attribute_line_ids.filtered(
            lambda l: l.attribute_id == trim_attr).product_template_value_ids[:1]
        color_ptav = tmpl.attribute_line_ids.filtered(
            lambda l: l.attribute_id == color_attr).product_template_value_ids[:1]
        booking._apply_configuration((trim_ptav + color_ptav).ids)
        order = booking._ensure_sale_order()
        booking._transition_to('payment_pending')
        order.action_confirm()
        # Deposit invoice + payment so the portal demo shows real documents.
        wizard = self.env['sale.advance.payment.inv'].create({
            'advance_payment_method': 'fixed',
            'fixed_amount': booking.deposit_amount,
            'sale_order_ids': [(6, 0, order.ids)],
        })
        invoices = wizard._create_invoices(order)
        invoices.action_post()
        register = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoices.ids).create({})
        register._create_payments()
        booking.write({'deposit_paid': booking.deposit_amount})
        booking._transition_to('confirmed')


class BsCarModelImage(models.Model):
    _name = 'bs.car.model.image'
    _description = 'Car Model Image'
    _order = 'sequence, id'

    name = fields.Char('Title')
    sequence = fields.Integer(default=10)
    model_id = fields.Many2one('bs.car.model', string='Car Model', required=True, ondelete='cascade')
    image = fields.Image('Image', max_width=1920, max_height=1080, required=True)
