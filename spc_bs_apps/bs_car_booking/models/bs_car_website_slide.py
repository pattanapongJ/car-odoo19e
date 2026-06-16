# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from urllib.parse import parse_qs, urlencode, urlparse

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

DIRECT_VIDEO_EXTENSIONS = ('.mp4', '.mov', '.m4v')


class BsCarWebsiteSlide(models.Model):
    _name = 'bs.car.website.slide'
    _description = 'Car Website Slide'
    _order = 'sequence, id'

    section_id = fields.Many2one(
        'bs.car.website.section', string='Section',
        required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    name = fields.Char(required=True, translate=True)
    eyebrow = fields.Char(translate=True)
    title = fields.Char(required=True, translate=True)
    subtitle = fields.Text(translate=True)
    body_html = fields.Html(translate=True, sanitize_attributes=True)

    model_id = fields.Many2one(
        'bs.car.model', string='Car Model', ondelete='set null', index=True,
        help='Link to car model — used to display base price on slide.')
    show_price = fields.Boolean('Show Base Price', default=False)
    price_display = fields.Char(compute='_compute_price_display')

    image = fields.Image('Slide Image', max_width=2400, max_height=1400)
    image_alt = fields.Char(translate=True)
    title_image = fields.Image(
        'Title Image', max_width=2400, max_height=800,
        help='Optional graphic title/logo rendered instead of the text title.')
    title_image_alt = fields.Char('Title Image Alt', translate=True)

    video_file = fields.Binary('Desktop Video Upload', attachment=True)
    video_filename = fields.Char('Video Filename')
    mobile_video_file = fields.Binary('Mobile Video Upload', attachment=True)
    mobile_video_filename = fields.Char('Mobile Video Filename')
    has_video_file = fields.Boolean(compute='_compute_has_video_file', store=True)
    has_mobile_video_file = fields.Boolean(compute='_compute_has_video_file', store=True)

    video_url = fields.Char('External Video URL')
    video_src = fields.Char(compute='_compute_video_media')
    mobile_video_src = fields.Char(compute='_compute_video_media')
    video_embed_url = fields.Char(compute='_compute_video_embed_url')
    video_media_type = fields.Selection([
        ('upload', 'Uploaded Video'),
        ('direct', 'Direct Video URL'),
        ('youtube', 'YouTube'),
        ('vimeo', 'Vimeo'),
        ('none', 'No Video'),
    ], compute='_compute_video_media')

    # ── Content Position ──────────────────────────────────────────────
    content_align_x = fields.Selection([
        ('left', 'Left'),
        ('center', 'Center'),
        ('right', 'Right'),
    ], string='Horizontal Align', default='center')
    content_align_y = fields.Selection([
        ('top', 'Top'),
        ('middle', 'Middle'),
        ('bottom', 'Bottom'),
    ], string='Vertical Align', default='bottom')

    # ── Text Color Scheme ─────────────────────────────────────────────
    text_color_scheme = fields.Selection([
        ('light', 'Light (White)'),
        ('dark', 'Dark (Black)'),
        ('custom', 'Custom'),
    ], string='Text Color', default='light')
    custom_title_color = fields.Char('Title Color', help='Hex e.g. #FFFFFF')
    custom_subtitle_color = fields.Char('Subtitle Color', help='Hex e.g. #CCCCCC')

    # ── CTA Buttons (One2many — unlimited) ───────────────────────────
    cta_ids = fields.One2many(
        'bs.car.website.slide.cta', 'slide_id', string='Buttons')

    @api.depends('show_price', 'model_id.base_price', 'model_id.currency_id')
    def _compute_price_display(self):
        _UNIT = {'th_TH': 'บาท', 'th': 'บาท'}
        for slide in self:
            if slide.show_price and slide.model_id and slide.model_id.base_price:
                amount_str = '{:,.0f}'.format(slide.model_id.base_price)
                lang = (slide.env.lang or 'en_US')
                unit = _UNIT.get(lang) or _UNIT.get(lang.split('_')[0]) or 'Baht'
                slide.price_display = '%s %s' % (amount_str, unit)
            else:
                slide.price_display = False

    @api.depends('video_file', 'mobile_video_file')
    def _compute_has_video_file(self):
        for slide in self:
            slide.has_video_file = bool(slide.video_file)
            slide.has_mobile_video_file = bool(slide.mobile_video_file)

    @api.depends('has_video_file', 'has_mobile_video_file', 'video_url')
    def _compute_video_media(self):
        for slide in self:
            video_url = (slide.video_url or '').strip()
            embed_url = slide._normalize_video_embed_url(video_url)
            slide.mobile_video_src = (
                '/web/content/bs.car.website.slide/%s/mobile_video_file' % slide.id
                if slide.has_mobile_video_file else False
            )
            if slide.has_video_file:
                slide.video_media_type = 'upload'
                slide.video_src = '/web/content/bs.car.website.slide/%s/video_file' % slide.id
            elif slide.has_mobile_video_file:
                slide.video_media_type = 'upload'
                slide.video_src = slide.mobile_video_src
            elif video_url and not embed_url:
                slide.video_media_type = 'direct'
                slide.video_src = video_url
            elif embed_url and 'youtube' in embed_url:
                slide.video_media_type = 'youtube'
                slide.video_src = False
            elif embed_url and 'vimeo' in embed_url:
                slide.video_media_type = 'vimeo'
                slide.video_src = False
            else:
                slide.video_media_type = 'none'
                slide.video_src = False

    @api.depends('video_url')
    def _compute_video_embed_url(self):
        for slide in self:
            slide.video_embed_url = slide._normalize_video_embed_url(slide.video_url)

    @api.model
    def _normalize_video_embed_url(self, video_url):
        if not video_url:
            return False
        parsed = urlparse(video_url.strip())
        host = (parsed.netloc or '').lower().removeprefix('www.')
        path = parsed.path.strip('/')
        video_id = False

        if host in ('youtu.be', 'youtube.com', 'm.youtube.com', 'youtube-nocookie.com'):
            if host == 'youtu.be':
                video_id = path.split('/')[0]
            elif path == 'watch':
                video_id = parse_qs(parsed.query).get('v', [False])[0]
            elif path.startswith(('embed/', 'shorts/', 'live/')):
                video_id = path.split('/')[1]
            if video_id:
                params = {'autoplay': 1, 'mute': 1, 'controls': 0,
                          'playsinline': 1, 'rel': 0, 'loop': 1, 'playlist': video_id}
                return 'https://www.youtube-nocookie.com/embed/%s?%s' % (
                    video_id, urlencode(params))

        if host in ('vimeo.com', 'player.vimeo.com'):
            video_id = path.split('/')[-1]
            if video_id:
                params = {'autoplay': 1, 'muted': 1, 'background': 1, 'loop': 1}
                return 'https://player.vimeo.com/video/%s?%s' % (
                    video_id, urlencode(params))

        path_lower = (parsed.path or '').lower()
        if path_lower.endswith(DIRECT_VIDEO_EXTENSIONS):
            return False
        return False

    @api.constrains('video_filename', 'mobile_video_filename')
    def _check_video_format(self):
        for slide in self:
            for fname in [slide.video_filename or '', slide.mobile_video_filename or '']:
                if fname and not fname.lower().endswith(DIRECT_VIDEO_EXTENSIONS):
                    raise ValidationError(_(
                        'Video Upload only supports MP4/MOV/M4V files.'))
