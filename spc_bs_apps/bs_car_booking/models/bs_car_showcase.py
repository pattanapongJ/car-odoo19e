# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

import json

from odoo import api, fields, models


class BsCarShowcaseItem(models.Model):
    """Editorial home-page content tied to a car model.

    This keeps campaign sections data-driven: model stage slides,
    exterior/interior colour studio images, highlight cards and the cabin story
    band can all be curated from the back office.
    """
    _name = 'bs.car.showcase.item'
    _description = 'Car Showcase Item'
    _inherit = ['website.published.multi.mixin', 'bs.car.website.scope.mixin']
    _order = 'model_id, item_type, sequence, id'
    _bs_clear_website_cache_on_write = True

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
        index=True, help='Leave empty to share this showcase item across companies.')
    model_id = fields.Many2one('bs.car.model', required=True, ondelete='cascade', index=True)
    item_type = fields.Selection([
        ('stage', 'Model Stage Slide'),
        ('exterior', 'Exterior Colour'),
        ('interior', 'Interior Theme'),
        ('highlight', 'Highlight Card'),
        ('cabin', 'Cabin Story'),
    ], required=True, default='highlight', index=True)

    subtitle = fields.Char(translate=True)
    description = fields.Html(translate=True, sanitize_attributes=True)
    image = fields.Image(max_width=1920, max_height=1080)
    image_alt = fields.Char(translate=True)
    highlight_image_ids = fields.One2many(
        'bs.car.showcase.item.image', 'item_id', string='Highlight Gallery',
        help='Additional images shown in the highlight lightbox.')
    swatch_color = fields.Char(
        'Swatch Colour',
        help='CSS colour used by exterior/interior option buttons, e.g. #111111.')
    cta_label = fields.Char('Button Label', translate=True)
    cta_url = fields.Char('Button Link')

    def _default_is_published(self):
        return True

    def _studio_swatch(self):
        """Resolved swatch colour for the colour-studio button."""
        self.ensure_one()
        return self.swatch_color or '#111111'

    def _studio_swatch_style(self):
        """CSS ``background`` for the colour-studio swatch. Mirrors the method
        on bs.car.model.option so the shared color_studio template can call it
        on showcase items too (the template uses both)."""
        self.ensure_one()
        return f'background:{self._studio_swatch()}'

    def _highlight_gallery_json(self):
        """Lightbox gallery payload: main card image followed by detail images."""
        self.ensure_one()
        images = []
        if self.image:
            images.append({
                'src': '/web/image/bs.car.showcase.item/%s/image/1600x1067' % self.id,
                'thumb': '/web/image/bs.car.showcase.item/%s/image/220x146' % self.id,
                'alt': self.image_alt or self.name or '',
                'title': self.name or '',
            })
        for img in self.highlight_image_ids.sorted('sequence'):
            if not img.image:
                continue
            images.append({
                'src': '/web/image/bs.car.showcase.item.image/%s/image/1600x1067' % img.id,
                'thumb': '/web/image/bs.car.showcase.item.image/%s/image/220x146' % img.id,
                'alt': img.image_alt or img.name or self.name or '',
                'title': img.name or self.name or '',
            })
        return json.dumps(images)

    @api.model
    def _get_website_items(self, model, item_type, limit=None):
        model_id = model.id if hasattr(model, 'id') else int(model or 0)
        domain = [
            ('model_id', '=', model_id),
            ('item_type', '=', item_type),
            ('active', '=', True),
            ('website_published', '=', True),
        ]
        return self.sudo().search(domain + self._public_scope_domain(), order='sequence, id', limit=limit)


class BsCarShowcaseItemImage(models.Model):
    """Additional images for a showcase item lightbox."""
    _name = 'bs.car.showcase.item.image'
    _description = 'Car Showcase Item Image'
    _inherit = ['bs.car.website.scope.mixin']
    _order = 'sequence, id'
    _bs_clear_website_cache_on_write = True

    name = fields.Char('Caption', translate=True)
    sequence = fields.Integer(default=10)
    item_id = fields.Many2one(
        'bs.car.showcase.item', string='Showcase Item',
        required=True, ondelete='cascade', index=True)
    image = fields.Image('Image', max_width=1920, max_height=1080, required=True)
    image_alt = fields.Char('Image Alt', translate=True)


class BsCarStory(models.Model):
    """Brand/editorial stories surfaced on the showroom home page."""
    _name = 'bs.car.story'
    _description = 'Car Brand Story'
    _inherit = ['website.published.multi.mixin', 'bs.car.website.scope.mixin']
    _order = 'sequence, publish_date desc, id desc'
    _bs_clear_website_cache_on_write = True

    name = fields.Char('Headline', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
        index=True, help='Leave empty to share this story across companies.')
    publish_date = fields.Date()
    location = fields.Char(translate=True,
                           help='Dateline location shown with the date, e.g. "Changchun, China".')
    subtitle = fields.Char(translate=True)
    excerpt = fields.Text(translate=True)
    body = fields.Html(translate=True, sanitize_attributes=True)
    image = fields.Image(max_width=1920, max_height=1080)
    model_id = fields.Many2one('bs.car.model', ondelete='set null')
    cta_label = fields.Char('Button Label', translate=True, default='Read story')
    cta_url = fields.Char('Button Link')

    def _default_is_published(self):
        return True

    def _get_website_url(self):
        self.ensure_one()
        return '/story/%s' % self.id

    def _resolve_cta_url(self):
        self.ensure_one()
        if self.cta_url:
            return self.cta_url
        if self.model_id:
            return '/car/%s' % self.model_id.id
        return False

    @api.model
    def _get_website_stories(self, model_id=None, limit=3):
        domain = [('active', '=', True), ('website_published', '=', True)] + self._public_scope_domain()
        if model_id:
            domain += ['|', ('model_id', '=', int(model_id)), ('model_id', '=', False)]
        return self.sudo().search(domain, order='sequence, publish_date desc, id desc', limit=limit)
