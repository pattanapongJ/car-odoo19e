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

class BsCarModel(models.Model):
    _name = 'bs.car.model'
    _description = 'Car Model'
    _inherit = ['website.seo.metadata', 'website.published.multi.mixin', 'bs.car.website.scope.mixin']
    _order = 'brand_id, sequence, name'
    _bs_clear_website_cache_on_write = True

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
            website = getattr(request, 'website', False) or self.env['website'].get_current_website()
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
            data['image'] = website.image_url(self, 'image')
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
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
        index=True, help='Leave empty to share this model across companies.')
    
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
    # Document-only (FC requirement): Thai sales paperwork — invoices,
    # registration, insurance/finance quotes — carries the รุ่นปี (model year).
    # It flows into the generated product's name, hence every SO/invoice line.
    # NOT shown on the website; marketing display is a "Model Year" spec line.
    model_year = fields.Char('Model Year', size=4,
                             help='Manufacturer model year (e.g. 2026). Appended to the '
                                  'generated product name so sales documents carry it.')

    description = fields.Html('Description', translate=True)
    highlight_features = fields.Text('Highlight Features', translate=True,
                                     help='Key features displayed on website, one per line')
    
    # Media
    image = fields.Image('Main Image', max_width=1920, max_height=1080)
    gallery_image_ids = fields.One2many('bs.car.model.image', 'model_id', string='Gallery', copy=True)
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
    variant_ids = fields.One2many('bs.car.variant', 'model_id', string='Variants', copy=True)
    variant_count = fields.Integer(compute='_compute_variant_count')
    
    # Website
    website_featured = fields.Boolean('Featured on Home',
                                      help='Show this model in the home "Featured Model" section.')
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
        recs = self.sudo().search(
            [('website_published', '=', True), ('active', '=', True)] + self._public_scope_domain())
        recs = recs.sorted(
            key=lambda c: (c.arrival_date or date.min, c.create_date or datetime.min),
            reverse=True)
        return recs[:limit]

    @api.model
    def _get_website_featured(self):
        """Return the model to showcase on the home page: the flagged one,
        else the first published model."""
        base = [('website_published', '=', True), ('active', '=', True)] + self._public_scope_domain()
        return (self.sudo().search([('website_featured', '=', True)] + base, limit=1)
                or self.sudo().search(base, order='sequence, id', limit=1))

    # === Commerce backbone (native product) ===
    product_tmpl_id = fields.Many2one('product.template', string='Configurable Product',
                                      copy=False, readonly=True,
                                      help='Generated product that powers pricing & ordering.')
    option_ids = fields.One2many('bs.car.model.option', 'model_id', string='Options', copy=True,
                                 help='Selectable priced options (color, interior, wheels, add-ons).')
    spec_ids = fields.One2many('bs.car.model.spec', 'model_id', string='Specifications', copy=True,
                               help='Technical spec sheet shown on the website (data-driven).')

    # --- Home "showcase" content, split per type so each maps to one
    #     home section. All point to bs.car.showcase.item via model_id; the
    #     domains are mutually exclusive (no record appears in two fields). ---
    showcase_item_ids = fields.One2many('bs.car.showcase.item', 'model_id', string='Showcase Items', copy=True)
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
    # copy=False (default) kept on purpose: news articles are time-bound
    # editorial — duplicating a model for a new year must not clone them.
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
        """Get or create a product.attribute.value for a per-model package."""
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
        # Standard package values come from the model's package records.
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

    def _product_display_name(self):
        """Name of the generated product, hence of every SO/invoice line:
        "Brand Model (Year)" — the year is a Thai sales-paperwork requirement."""
        self.ensure_one()
        name = f'{self.brand_id.name} {self.name}'.strip()
        if self.model_year:
            name = f'{name} ({self.model_year})'
        return name

    def write(self, vals):
        res = super().write(vals)
        # Keep the generated product's name (→ new sales documents) in sync.
        # Already-confirmed order lines keep their historical description.
        if {'name', 'brand_id', 'model_year'} & set(vals):
            for model in self.filtered('product_tmpl_id'):
                new_name = model._product_display_name()
                if model.product_tmpl_id.name != new_name:
                    model.product_tmpl_id.name = new_name
        return res

    def action_generate_product(self):
        """Create/refresh the product.template + attribute lines for each model."""
        Line = self.env['product.template.attribute.line']
        tax = self._get_sale_tax()
        # Attributes this routine owns: trim (from variants) + the option-sourced
        # ones. Used to drop stale attribute lines when a model's options for an
        # attribute are all removed (otherwise old values linger on the product).
        managed_attr_ids = set()
        trim_attr = self.env.ref('bs_car_booking.attr_trim', raise_if_not_found=False)
        if trim_attr:
            managed_attr_ids.add(trim_attr.id)
        for ref in OPTION_ATTRIBUTE_REFS:
            attr = self.env.ref(ref, raise_if_not_found=False)
            if attr:
                managed_attr_ids.add(attr.id)
        for model in self:
            vals = {
                'name': model._product_display_name(),
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
            # Drop owned attribute lines whose options were all removed from the
            # model, so the product no longer keeps stale attribute values.
            config_attr_ids = {attr.id for attr in config}
            stale_lines = tmpl.attribute_line_ids.filtered(
                lambda l: l.attribute_id.id in managed_attr_ids
                and l.attribute_id.id not in config_attr_ids)
            if stale_lines:
                stale_lines.unlink()
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

class BsCarModelImage(models.Model):
    _name = 'bs.car.model.image'
    _description = 'Car Model Image'
    _inherit = ['bs.car.website.scope.mixin']
    _order = 'sequence, id'
    _bs_clear_website_cache_on_write = True

    name = fields.Char('Title')
    sequence = fields.Integer(default=10)
    model_id = fields.Many2one('bs.car.model', string='Car Model', required=True, ondelete='cascade')
    image = fields.Image('Image', max_width=1920, max_height=1080, required=True)
    def _default_is_published(self):
        return True
