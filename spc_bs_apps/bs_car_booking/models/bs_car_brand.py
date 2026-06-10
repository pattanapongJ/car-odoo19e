# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import api, fields, models


class BsCarBrand(models.Model):
    _name = 'bs.car.brand'
    _description = 'Car Brand'
    _inherit = ['website.published.multi.mixin', 'bs.car.website.scope.mixin']
    _order = 'sequence, name'
    _bs_clear_website_cache_on_write = True

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
        index=True, help='Leave empty to share this brand across companies.')
    logo = fields.Image('Brand Logo', max_width=200, max_height=200)
    website_description = fields.Html(
        'Website Description', translate=True,
        help='Brand description shown on website'
    )
    model_ids = fields.One2many('bs.car.model', 'brand_id', string='Models')
    model_count = fields.Integer(compute='_compute_model_count', string='# Models')

    # Heritage / brand-story (rendered by the home "Heritage" section)
    tagline = fields.Char('Tagline', translate=True,
                          help='Short brand line, e.g. "The flag bearer of Chinese luxury".')
    heritage_title = fields.Char('Heritage Title', translate=True)
    heritage_html = fields.Html('Heritage Story', translate=True, sanitize_attributes=True)
    heritage_image = fields.Image('Heritage Image', max_width=1920, max_height=1280)
    heritage_cta_label = fields.Char('Heritage Button', translate=True, default='Explore the range')
    heritage_cta_url = fields.Char('Heritage Button Link', default='/cars')
    website_featured = fields.Boolean('Featured Brand',
                                      help='Brand shown in the home "Heritage" section.')

    def _default_is_published(self):
        return True

    def _compute_model_count(self):
        for brand in self:
            brand.model_count = len(brand.model_ids)

    @api.model
    def _get_website_featured(self):
        """Brand to feature in the heritage section: the flagged one, else the
        first active brand."""
        domain = [('active', '=', True), ('website_published', '=', True)] + self._public_scope_domain()
        return (self.sudo().search([('website_featured', '=', True)] + domain, limit=1)
                or self.sudo().search(domain, order='sequence, name', limit=1))
