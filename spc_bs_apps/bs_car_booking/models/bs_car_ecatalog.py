# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import fields, models


class BsCarEcatalog(models.Model):
    _name = 'bs.car.ecatalog'
    _description = 'Car e-Catalog'
    _order = 'sequence, id'

    name = fields.Char('Catalog Name', required=True, translate=True)
    model_id = fields.Many2one('bs.car.model', string='Car Model', required=True, ondelete='cascade', index=True)
    catalog_file = fields.Binary('Catalog File', attachment=True, required=True)
    catalog_filename = fields.Char('Filename')
    button_label = fields.Char('Button Label', default='Download e-Catalog', translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
        index=True)
