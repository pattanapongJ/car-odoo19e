# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

import json

from markupsafe import Markup

from odoo import api, fields, models
from odoo.http import request


class BsCarDealer(models.Model):
    _name = 'bs.car.dealer'
    _description = 'Car Dealer / Showroom'
    _order = 'sequence, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    
    # Contact
    partner_id = fields.Many2one('res.partner', string='Contact Partner',
                                 help='Linked partner record for this dealer')
    phone = fields.Char('Phone')
    email = fields.Char('Email')
    
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
    
    # Website
    website_published = fields.Boolean('Published on Website', default=True)
    maps_query = fields.Char(compute='_compute_maps_query',
                             help='Query for the "Get directions" link (lat,long or address).')

    @api.depends('latitude', 'longitude', 'street', 'city', 'country_id')
    def _compute_maps_query(self):
        for d in self:
            if d.latitude and d.longitude:
                d.maps_query = f'{d.latitude},{d.longitude}'
            else:
                d.maps_query = ', '.join(
                    p for p in [d.street, d.city, d.country_id.name] if p)

    @api.model
    def _website_autodealer_jsonld(self):
        """Schema.org AutoDealer structured data with showroom locations.
        Returns empty when rendered outside a website request (e.g. the
        builder's snippet preview via render_public_asset)."""
        try:
            website = request.website
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
        for d in self.sudo().search([('active', '=', True), ('website_published', '=', True)]):
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
