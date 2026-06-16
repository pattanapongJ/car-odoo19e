# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from urllib.parse import quote

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Types whose physical presence is bounded by a date window. Permanent types
# (showroom / service centre) ignore date_start / date_end entirely.
TEMPORARY_TYPES = ('event', 'roadshow', 'popup', 'test_drive')


class BsCarLocation(models.Model):
    """A physical touchpoint operated by a dealer.

    A dealer (the permanent business / showroom entity, ``bs.car.dealer``) can
    run several locations: its own showroom, service centres, plus time-boxed
    presences like events, roadshows, pop-up stores and test-drive sites.

    This is intentionally a *separate* model from the dealer the booking funnel
    points at (``booking.dealer_id`` is untouched). It exists for website
    display today; it is shaped so a future ``booking.location_id`` link is a
    one-field addition, not a migration.
    """
    _name = 'bs.car.location'
    _description = 'Car Dealer Location / Touchpoint'
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
    location_type = fields.Selection(
        selection=[
            ('showroom', 'Showroom'),
            ('service_center', 'Service Center'),
            ('event', 'Event'),
            ('roadshow', 'Roadshow'),
            ('popup', 'Pop-up Store'),
            ('test_drive', 'Test Drive Site'),
        ],
        string='Type', required=True, default='showroom', tracking=True)
    is_temporary = fields.Boolean(
        compute='_compute_is_temporary',
        help='Whether this location type is bounded by a start/end date.')

    dealer_id = fields.Many2one(
        'bs.car.dealer', string='Dealer', required=True,
        ondelete='cascade', tracking=True,
        help='Permanent dealer this location belongs to.')
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
        index=True, help='Leave empty to share this location across companies.')

    # Contact
    phone = fields.Char('Phone', tracking=True)
    email = fields.Char('Email', tracking=True)

    # Address
    # Standard Odoo address fields (same names/types as res.partner) so the
    # location address behaves like a contact address — incl. state filtered by
    # country. The location keeps its OWN address (events happen at venues, not
    # the dealer's registered office), rather than borrowing the dealer partner.
    street = fields.Char('Street')
    street2 = fields.Char('Street2')
    city = fields.Char('City')
    state_id = fields.Many2one(
        'res.country.state', string='State', ondelete='restrict',
        domain="[('country_id', '=?', country_id)]")
    country_id = fields.Many2one('res.country', string='Country', ondelete='restrict')
    zip = fields.Char('ZIP')
    latitude = fields.Float('Latitude', digits=(10, 7))
    longitude = fields.Float('Longitude', digits=(10, 7))

    # Validity window (temporary types only)
    date_start = fields.Date('Start Date', tracking=True)
    date_end = fields.Date('End Date', tracking=True)
    is_live = fields.Boolean(
        string='Live', compute='_compute_is_live', search='_search_is_live',
        help='Active and, for temporary types, today falls within the date '
             'window. The website shows live locations only.')

    # Operations / presentation
    opening_hours = fields.Text('Opening Hours')
    image = fields.Image('Image', max_width=1920, max_height=1080)
    website_description = fields.Html('Website Description', translate=True)

    # Maps (mirrors bs.car.dealer so events get pins + directions for free)
    maps_query = fields.Char(compute='_compute_maps_query',
                             help='Query for the "Get directions" link (lat,long or address).')
    map_embed_url = fields.Char(compute='_compute_maps_query',
                                help='Keyless Google Maps embed URL for the location map iframe.')
    directions_url = fields.Char(compute='_compute_maps_query',
                                 help='Google Maps directions link (opens in a new tab).')

    def _default_is_published(self):
        return True

    @api.depends('location_type')
    def _compute_is_temporary(self):
        for loc in self:
            loc.is_temporary = loc.location_type in TEMPORARY_TYPES

    @api.depends('active', 'location_type', 'date_start', 'date_end')
    def _compute_is_live(self):
        today = fields.Date.context_today(self)
        for loc in self:
            if not loc.active:
                loc.is_live = False
            elif loc.location_type not in TEMPORARY_TYPES:
                loc.is_live = True
            else:
                after_start = not loc.date_start or loc.date_start <= today
                before_end = not loc.date_end or loc.date_end >= today
                loc.is_live = after_start and before_end

    def _search_is_live(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise ValidationError(_('Unsupported search on "Live".'))
        live = value if operator == '=' else not value
        today = fields.Date.context_today(self)
        live_domain = [
            ('active', '=', True),
            '|',
                ('location_type', 'not in', list(TEMPORARY_TYPES)),
                '&',
                    '|', ('date_start', '=', False), ('date_start', '<=', today),
                    '|', ('date_end', '=', False), ('date_end', '>=', today),
        ]
        if live:
            return live_domain
        # Not live: anything the positive domain excludes. Cheapest correct
        # expression is the id-complement of the live set.
        live_ids = self.sudo().search(live_domain).ids
        return [('id', 'not in', live_ids)]

    @api.constrains('date_start', 'date_end')
    def _check_date_window(self):
        for loc in self:
            if loc.date_start and loc.date_end and loc.date_end < loc.date_start:
                raise ValidationError(_('End Date cannot be earlier than Start Date.'))

    @api.depends('latitude', 'longitude', 'street', 'city', 'country_id')
    def _compute_maps_query(self):
        for loc in self:
            if loc.latitude and loc.longitude:
                loc.maps_query = f'{loc.latitude},{loc.longitude}'
            else:
                loc.maps_query = ', '.join(
                    p for p in [loc.street, loc.city, loc.country_id.name] if p)
            q = quote(loc.maps_query) if loc.maps_query else ''
            loc.map_embed_url = (
                'https://maps.google.com/maps?q=%s&t=m&z=14&ie=UTF8&iwloc=&output=embed' % q
            ) if q else False
            loc.directions_url = (
                'https://www.google.com/maps/dir/?api=1&destination=%s' % q
            ) if q else False

    @api.model
    def _get_website_locations(self, limit=None):
        """Live, published, website/company-scoped locations for the locator.

        ``is_live`` drops date-expired temporary touchpoints (events, roadshows,
        pop-ups, test-drive sites) via its search method.
        """
        domain = [
            ('is_live', '=', True),
            ('website_published', '=', True),
        ] + self._public_scope_domain()
        return self.sudo().search(domain, order='sequence, name', limit=limit)

    @api.model
    def _cron_archive_expired_locations(self):
        """Auto-archive temporary locations once their End Date has passed, so
        staff never have to remember to take last month's roadshow off the map.
        """
        today = fields.Date.context_today(self)
        expired = self.search([
            ('active', '=', True),
            ('location_type', 'in', list(TEMPORARY_TYPES)),
            ('date_end', '!=', False),
            ('date_end', '<', today),
        ])
        if expired:
            expired.active = False
