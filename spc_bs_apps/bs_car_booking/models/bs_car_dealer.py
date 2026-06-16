# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

import json
from urllib.parse import quote

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.http import request


class BsCarDealer(models.Model):
    _name = 'bs.car.dealer'
    _description = 'Car Dealer / Showroom'
    _order = 'sequence, name'
    _inherit = [
        'mail.thread',
        'mail.activity.mixin',
        'website.published.multi.mixin',
        'bs.car.website.scope.mixin',
    ]
    _bs_clear_website_cache_on_write = True

    name = fields.Char(required=True, translate=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
        index=True, help='Leave empty to share this dealer across companies.')
    
    # Contact
    partner_id = fields.Many2one('res.partner', string='Contact Partner',
                                 help='Linked partner record for this dealer')
    phone = fields.Char('Phone', tracking=True)
    email = fields.Char('Email', tracking=True)
    
    # Address
    street = fields.Char('Street')
    street2 = fields.Char('Street2')
    city = fields.Char('City')
    state_id = fields.Many2one('res.country.state', string='State')
    country_id = fields.Many2one('res.country', string='Country')
    zip = fields.Char('ZIP')
    
    # Location
    latitude = fields.Float('Latitude', digits=(10, 7))
    longitude = fields.Float('Longitude', digits=(10, 7))
    
    # Operations
    opening_hours = fields.Text('Opening Hours')
    image = fields.Image('Showroom Image', max_width=1920, max_height=1080)
    website_description = fields.Html('Website Description', translate=True)
    
    # Brands handled
    brand_ids = fields.Many2many('bs.car.brand', string='Brands Available')

    # Locations / touchpoints operated by this dealer (showrooms, service
    # centres, plus time-boxed events / roadshows / pop-ups / test-drive sites)
    location_ids = fields.One2many('bs.car.location', 'dealer_id', string='Locations')
    location_count = fields.Integer(compute='_compute_location_count')

    # Website
    maps_query = fields.Char(compute='_compute_maps_query',
                             help='Query for the "Get directions" link (lat,long or address).')
    map_embed_url = fields.Char(compute='_compute_maps_query',
                                help='Keyless Google Maps embed URL for the showroom map iframe.')
    directions_url = fields.Char(compute='_compute_maps_query',
                                 help='Google Maps directions link (opens in a new tab).')

    def _default_is_published(self):
        return True

    @api.depends('location_ids')
    def _compute_location_count(self):
        for dealer in self:
            dealer.location_count = len(dealer.location_ids)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_referenced(self):
        # booking.dealer_id is ondelete='set null', so without this guard a
        # delete would silently wipe the dealer from existing bookings.
        used = self.env['bs.car.booking'].sudo().search_count([('dealer_id', 'in', self.ids)])
        if used:
            raise ValidationError(_(
                'You cannot delete a dealer referenced by bookings. '
                'Archive it instead.'))

    @api.depends('latitude', 'longitude', 'street', 'city', 'country_id')
    def _compute_maps_query(self):
        for d in self:
            if d.latitude and d.longitude:
                d.maps_query = f'{d.latitude},{d.longitude}'
            else:
                d.maps_query = ', '.join(
                    p for p in [d.street, d.city, d.country_id.name] if p)
            q = quote(d.maps_query) if d.maps_query else ''
            d.map_embed_url = (
                'https://maps.google.com/maps?q=%s&t=m&z=14&ie=UTF8&iwloc=&output=embed' % q
            ) if q else False
            d.directions_url = (
                'https://www.google.com/maps/dir/?api=1&destination=%s' % q
            ) if q else False

    @api.model
    def _website_autodealer_jsonld(self):
        """Schema.org AutoDealer structured data with showroom locations.
        Returns empty when rendered outside a website request (e.g. the
        builder's snippet preview via render_public_asset)."""
        try:
            website = getattr(request, 'website', False) or self.env['website'].get_current_website()
        except (AttributeError, RuntimeError):
            website = False
        if not website:
            return Markup('')
        base = website.domain or request.httprequest.url_root.rstrip('/')
        data = {
            '@context': 'https://schema.org',
            '@type': 'AutoDealer',
            'name': website.name,
            'url': base,
        }
        departments = []
        for d in self.sudo().search(
                [('active', '=', True), ('website_published', '=', True)] + self._public_scope_domain()):
            loc = {'@type': 'AutoDealer', 'name': d.name}
            addr = {k: v for k, v in {
                'streetAddress': d.street, 'addressLocality': d.city,
                'addressCountry': d.country_id.name,
            }.items() if v}
            if addr:
                loc['address'] = {'@type': 'PostalAddress', **addr}
            if d.phone:
                loc['telephone'] = d.phone
            if d.latitude and d.longitude:
                loc['geo'] = {'@type': 'GeoCoordinates',
                              'latitude': d.latitude, 'longitude': d.longitude}
            departments.append(loc)
        if departments:
            data['department'] = departments
        return Markup(json.dumps(data))
