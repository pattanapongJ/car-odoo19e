# -*- coding: utf-8 -*-
from odoo import fields, models


class BsCarWebslideCta(models.Model):
    _name = 'bs.car.website.slide.cta'
    _description = 'Slide CTA Button'
    _rec_name = 'label'
    _order = 'sequence, id'

    slide_id = fields.Many2one(
        'bs.car.website.slide', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)

    label = fields.Char(required=True, translate=True)
    url_type = fields.Selection([
        ('custom',      'Custom URL'),
        ('menu',        'Website Menu'),
        ('book',        'Order Now (auto → /car/ID/book)'),
        ('view',        'View Car (auto → /car/ID)'),
        ('test_drive',  'Test Drive (auto → /test-drive)'),
        ('URL_Download',    'Download URL'),
    ], string='Link Type', default='custom', required=True)
    url = fields.Char('Link URL', help='ใช้เมื่อ Link Type = Custom URL')
    menu_id = fields.Many2one(
        'website.menu', string='Website Menu',
        help='ดึง URL จาก menu ที่เลือก')
    download_file = fields.Binary('Download File', attachment=True)
    download_filename = fields.Char('Download Filename')
    target_blank = fields.Boolean('Open in New Tab', default=False)
    style = fields.Selection([
        ('solid', 'Solid'),
        ('outline', 'Outline'),
        ('ghost', 'Ghost (Frosted)'),
        ('text_only', 'Text Only'),
    ], default='solid', required=True)
    bg_color = fields.Char('Background Color', help='Hex e.g. #C8102E')
    text_color = fields.Char('Text Color', help='Hex e.g. #FFFFFF')
    icon = fields.Char('Icon', help='FontAwesome class e.g. fa-arrow-right')
    icon_position = fields.Selection([
        ('left', 'Left'),
        ('right', 'Right'),
    ], string='Icon Position', default='right')
