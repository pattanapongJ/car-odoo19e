# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from urllib.parse import parse_qs, urlencode, urlparse

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

DIRECT_VIDEO_EXTENSIONS = ('.mp4', '.mov', '.m4v')


class BsCarWebsiteSection(models.Model):
    """Website/company scoped marketing sections for dealer websites.

    This is the generic content layer used by brand themes. The theme decides
    the visual treatment; this model only stores the dealer-managed content.
    """
    _name = 'bs.car.website.section'
    _description = 'Car Website Section'
    _inherit = ['website.published.multi.mixin', 'bs.car.website.scope.mixin']
    _order = 'sequence, id'
    _bs_clear_website_cache_on_write = True

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
        index=True, help='Leave empty to share this section across companies.')
    section_type = fields.Selection([
        ('brand_cover', 'Brand Cover'),
        ('featured_model', 'Featured Model'),
        ('model_stage', 'Model Stage'),
        ('color_studio', 'Colour Studio'),
        ('heritage', 'Brand Heritage'),
        ('model_specs', 'Model Specifications'),
        ('highlights', 'Highlights'),
        ('cabin_story', 'Cabin Story'),
        ('latest_arrivals', 'Latest Arrivals'),
        ('offers', 'Offers'),
        ('stories', 'News'),
        ('dealer_locator', 'Dealer Locator'),
        ('hero_slider', 'Hero Slider'),
    ], required=True, default='brand_cover', index=True)
    theme_variant = fields.Selection([
        ('standard', 'Standard'),
        ('fullscreen', 'Full Screen Cover'),
        ('editorial', 'Editorial'),
        ('compact', 'Compact'),
    ], string='Cover Layout', default='fullscreen',
        help='Choose the visual layout. Brand themes can add their own layouts.')

    brand_id = fields.Many2one('bs.car.brand', string='Brand', ondelete='set null')
    model_id = fields.Many2one('bs.car.model', string='Featured Model', ondelete='set null')

    eyebrow = fields.Char(translate=True)
    title = fields.Char(required=True, translate=True)
    subtitle = fields.Text(translate=True)
    body_html = fields.Html(translate=True, sanitize_attributes=True)
    title_image = fields.Image(
        'Title Image', max_width=2400, max_height=800,
        help='Optional graphic title/logo rendered instead of the text title.')
    title_image_alt = fields.Char('Title Image Alt', translate=True)
    image = fields.Image('Cover Image', max_width=2400, max_height=1400)
    image_alt = fields.Char(translate=True)
    video_file = fields.Binary(
        'Desktop Video Upload',
        attachment=True,
        help='Upload an .mp4/.mov/.m4v file to use as a looping background video. '
             'This works better than YouTube on mobile. WebM is not supported on iOS Safari.')
    video_filename = fields.Char('Video Filename')
    mobile_video_file = fields.Binary(
        'Mobile Video Upload',
        attachment=True,
        help='Optional portrait video for mobile hero playback.')
    mobile_video_filename = fields.Char('Mobile Video Filename')
    has_video_file = fields.Boolean(compute='_compute_has_video_file', store=True)
    has_mobile_video_file = fields.Boolean(compute='_compute_has_video_file', store=True)
    video_src = fields.Char(compute='_compute_video_media')
    mobile_video_src = fields.Char(compute='_compute_video_media')
    video_url = fields.Char(
        'External Video URL',
        help='Optional YouTube/Vimeo URL or direct .mp4/.mov/.m4v URL. Uploaded video takes priority. WebM is not supported on iOS Safari.')
    video_embed_url = fields.Char(compute='_compute_video_embed_url')
    video_media_type = fields.Selection([
        ('upload', 'Uploaded Video'),
        ('direct', 'Direct Video URL'),
        ('youtube', 'YouTube'),
        ('vimeo', 'Vimeo'),
        ('none', 'No Video'),
    ], compute='_compute_video_media')

    slide_ids = fields.One2many(
        'bs.car.website.slide', 'section_id', string='Slides',
        help='Available when section_type is Hero Slider.')
    slide_interval = fields.Integer(
        'Auto-advance Interval (seconds)', default=5,
        help='Seconds between automatic slide changes. Set 0 to disable auto-advance.')
    slide_ken_burns = fields.Boolean(
        'Ken Burns Effect', default=True,
        help='เปิด/ปิด slow zoom-pan animation บนรูปพื้นหลังแต่ละ slide')

    primary_cta_label = fields.Char('Primary Button', translate=True)
    primary_cta_url = fields.Char('Primary Link')
    secondary_cta_label = fields.Char('Secondary Button', translate=True)
    secondary_cta_url = fields.Char('Secondary Link')

    def _default_is_published(self):
        return True

    @api.model
    def _get_home_sections(self, section_type=None, limit=None):
        domain = [
            ('active', '=', True),
            ('website_published', '=', True),
        ] + self._public_scope_domain()
        if section_type:
            domain.append(('section_type', '=', section_type))
        return self.sudo().search(domain, order='sequence, id', limit=limit)

    @api.model
    def _get_brand_cover(self):
        return self._get_home_sections('brand_cover', limit=1)

    def _section_model(self):
        self.ensure_one()
        return self.model_id or self.env['bs.car.model'].sudo().with_context(
            website_id=self._current_website().id if self._current_website() else False,
        )._get_website_featured()

    @api.depends('video_file', 'mobile_video_file')
    def _compute_has_video_file(self):
        for section in self:
            section.has_video_file = bool(section.video_file)
            section.has_mobile_video_file = bool(section.mobile_video_file)

    @api.depends('has_video_file', 'has_mobile_video_file', 'video_url')
    def _compute_video_media(self):
        for section in self:
            video_url = (section.video_url or '').strip()
            embed_url = section._normalize_video_embed_url(video_url)
            section.mobile_video_src = (
                '/web/content/bs.car.website.section/%s/mobile_video_file' % section.id
                if section.has_mobile_video_file else False
            )
            if section.has_video_file:
                section.video_media_type = 'upload'
                section.video_src = '/web/content/bs.car.website.section/%s/video_file' % section.id
            elif section.has_mobile_video_file:
                section.video_media_type = 'upload'
                section.video_src = section.mobile_video_src
            elif video_url and not embed_url:
                section.video_media_type = 'direct'
                section.video_src = video_url
            elif embed_url and 'youtube' in embed_url:
                section.video_media_type = 'youtube'
                section.video_src = False
            elif embed_url and 'vimeo' in embed_url:
                section.video_media_type = 'vimeo'
                section.video_src = False
            else:
                section.video_media_type = 'none'
                section.video_src = False

    @api.depends('video_url')
    def _compute_video_embed_url(self):
        for section in self:
            section.video_embed_url = section._normalize_video_embed_url(section.video_url)

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
                params = {
                    'autoplay': 1,
                    'mute': 1,
                    'controls': 0,
                    'playsinline': 1,
                    'rel': 0,
                    'loop': 1,
                    'playlist': video_id,
                }
                return 'https://www.youtube-nocookie.com/embed/%s?%s' % (
                    video_id,
                    urlencode(params),
                )

        if host in ('vimeo.com', 'player.vimeo.com'):
            video_id = path.split('/')[-1]
            if video_id:
                params = {
                    'autoplay': 1,
                    'muted': 1,
                    'background': 1,
                    'loop': 1,
                }
                return 'https://player.vimeo.com/video/%s?%s' % (
                    video_id,
                    urlencode(params),
                )

        path_lower = (parsed.path or '').lower()
        if path_lower.endswith(DIRECT_VIDEO_EXTENSIONS):
            return False

        return False

    @api.constrains('video_filename', 'mobile_video_filename', 'video_url')
    def _check_video_media_format(self):
        for section in self:
            filenames = [
                (section.video_filename or '').lower(),
                (section.mobile_video_filename or '').lower(),
            ]
            if any(filename and not filename.endswith(DIRECT_VIDEO_EXTENSIONS) for filename in filenames):
                raise ValidationError(_(
                    'Video Upload only supports MP4/MOV/M4V files. WebM is not supported on iOS Safari.'))

            video_url = (section.video_url or '').strip().lower()
            if video_url and not section._normalize_video_embed_url(video_url):
                parsed = urlparse(video_url)
                if not (parsed.scheme in ('http', 'https') and parsed.path.lower().endswith(DIRECT_VIDEO_EXTENSIONS)):
                    raise ValidationError(_(
                        'External Video URL must be YouTube, Vimeo, or a direct MP4/MOV/M4V URL.'))
