# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import models


class ThemeUtils(models.AbstractModel):
    _inherit = 'theme.utils'

    def _theme_bs_hongqi_car_post_copy(self, mod):
        website = self.env['website'].browse(
            self.env.context.get('website_id')
        )
        if not website:
            website = self.env['website'].get_current_website()

        self._theme_bs_hongqi_car_cleanup_website(website)

    def _theme_bs_hongqi_car_cleanup_installed_websites(self):
        self._theme_bs_hongqi_car_sync_theme_templates()

        theme = self.env['ir.module.module'].sudo().search(
            [('name', '=', 'theme_bs_hongqi_car')],
            limit=1,
        )
        if not theme:
            return

        websites = self.env['website'].sudo().search(
            [('theme_id', '=', theme.id)]
        )
        for website in websites:
            self._theme_bs_hongqi_car_cleanup_website(website)

    def _theme_bs_hongqi_car_sync_theme_templates(self):
        """Keep noupdate theme templates aligned across upgrades."""
        home_view = self.env.ref(
            'theme_bs_hongqi_car.hongqi_home_view',
            raise_if_not_found=False,
        )
        if home_view:
            home_view.sudo().write({
                'arch': self._theme_bs_hongqi_car_home_arch(),
            })
        # website.menu records are owned entirely by _cleanup_website() which
        # runs on every _theme_load; no xmlid-based sync needed here.

    def _theme_bs_hongqi_car_reset_theme_templates(self):
        for xmlid in (
            'theme_bs_hongqi_car.contact_us_page',
            'theme_bs_hongqi_car.contact_us_view',
        ):
            record = self.env.ref(xmlid, raise_if_not_found=False)
            if record:
                record.sudo().unlink()

        self._theme_bs_hongqi_car_sync_theme_templates()

    def _theme_bs_hongqi_car_home_arch(self):
        return """
<t t-name="theme_bs_hongqi_car.hongqi_home">
    <t t-call="website.layout">
        <t t-set="title">Hongqi Thailand</t>
        <t t-set="bs_hero_overlay" t-value="True"/>
        <div id="wrap">
            <!-- Data-driven sections (via backend Section records).
                 Uses t-call — must NOT be inside oe_structure or the
                 editor locks the whole region read-only. -->
            <t t-call="bs_car_booking.home_sections_content"/>
            <!-- Builder drop zone: free-form Odoo snippets per website,
                 while the cinematic sections above stay data-driven. -->
            <div class="oe_structure" id="oe_structure_hongqi_home"/>
        </div>
    </t>
</t>
""".strip()

    def _theme_bs_hongqi_car_sync_home_page(self, website):
        template = self.env.ref(
            'theme_bs_hongqi_car.hongqi_home_view',
            raise_if_not_found=False,
        )
        if not template:
            return

        View = self.env['ir.ui.view'].sudo().with_context(active_test=False)
        Page = self.env['website.page'].sudo().with_context(active_test=False)
        home_view = (
            template.copy_ids.filtered(
                lambda view: view.website_id == website
            )[:1]
            or View.search([
                ('key', '=', 'theme_bs_hongqi_car.hongqi_home'),
                ('website_id', '=', website.id),
            ], limit=1)
        )
        if home_view:
            home_view.write({
                'arch_db': template.arch,
                'active': True,
            })

        pages = Page.search([
            ('website_id', '=', website.id),
            ('url', '=', '/showroom'),
        ], order='theme_template_id desc, id desc')
        keeper = (
            pages.filtered(lambda page: page.view_id == home_view)[:1]
            or pages[:1]
        )
        if keeper:
            keeper.write({
                'name': 'Hongqi Car Home',
                'url': '/showroom',
                'is_published': True,
                'view_id': home_view.id if home_view else keeper.view_id.id,
            })
            (pages - keeper).unlink()

    def _bs_set_menu_translation(self, menu, name_th, th_active):
        """Seed the Thai (th_TH) label on a freshly created menu. Only used on
        creation so any later website-editor change to the label is preserved."""
        if th_active and name_th:
            menu.with_context(lang='th_TH').write({'name': name_th})

    def _theme_bs_hongqi_car_cleanup_website(self, website):
        website = website.sudo().exists()
        if not website:
            return

        website.write({'homepage_url': '/showroom'})
        self._theme_bs_hongqi_car_sync_home_page(website)

        Menu = self.env['website.menu'].sudo()
        top_menu = website.menu_id
        if not top_menu:
            return

        # Thai labels are applied in code (en_US + th_TH) so every nav item is
        # translated consistently and survives this cleanup, which rewrites the
        # name on each run. Value tuple = (English, Thai, sequence).
        th_active = bool(self.env['res.lang'].sudo().search_count(
            [('code', '=', 'th_TH'), ('active', '=', True)]))

        expected_menus = {
            # Home points at "/" (clean URL); homepage_url reroutes "/" to the
            # /showroom page internally, so content shows with the address bar
            # staying "/". The /showroom page itself is kept (homepage source).
            '/': ('Home', 'หน้าแรก', 5),
            '/cars': ('Models', 'รุ่น', 10),
            '/test-drive': ('Test Drive', 'ทดลองขับ', 55),
            # TEMPORARILY HIDDEN (2026-06-12, business request):
            # '/track': ('My Booking', 'การจองของฉัน', 40),
            '/#': ('About Us', 'เกี่ยวกับเรา', 70),
        }

        # Remove orphan menus for this website (parent_id=False).
        # These are created by website_menus.xml records that include
        # website_id but omit parent_id — Odoo skips the auto-parent logic
        # when website_id is already in vals, leaving them unreachable from
        # the navbar and invisible to the parent_id=top_menu search below.
        # IMPORTANT: exclude top_menu itself — it also has parent_id=False
        # and deleting it would cascade-remove every menu on the site.
        Menu.search([
            ('website_id', '=', website.id),
            ('parent_id', '=', False),
            ('id', '!=', top_menu.id),
        ]).unlink()

        # Remove any top-level menus whose URL is not in the expected set
        # (stale entries from old module versions: /compare, /track, /, …).
        Menu.search([
            ('website_id', '=', website.id),
            ('parent_id', '=', top_menu.id),
            ('url', 'not in', list(expected_menus.keys())),
        ]).unlink()

        for url, (name, name_th, sequence) in expected_menus.items():
            menus = Menu.search([
                ('website_id', '=', website.id),
                ('parent_id', '=', top_menu.id),
                ('url', '=', url),
            ], order='theme_template_id desc, sequence, id')
            keeper = menus.filtered('theme_template_id')[:1] or menus[:1]
            if keeper:
                # Enforce structure only — preserve any UI-edited label.
                keeper.write({'url': url, 'sequence': sequence})
            else:
                keeper = Menu.create({
                    'name': name,
                    'url': url,
                    'sequence': sequence,
                    'parent_id': top_menu.id,
                    'website_id': website.id,
                })
                self._bs_set_menu_translation(keeper, name_th, th_active)
            (menus - keeper).unlink()

        # Ensure About Us sub-menus exist
        about_menu = Menu.search([
            ('website_id', '=', website.id),
            ('parent_id', '=', top_menu.id),
            ('url', '=', '/#'),
        ], limit=1)
        if about_menu:
            expected_sub = {
                '/stories': ('News', 'ข่าวสาร', 10),
                '/contactus': ('Contact Us', 'ติดต่อเรา', 20),
            }
            for url, (name, name_th, sequence) in expected_sub.items():
                sub_menus = Menu.search([
                    ('website_id', '=', website.id),
                    ('parent_id', '=', about_menu.id),
                    ('url', '=', url),
                ], order='theme_template_id desc, sequence, id')
                keeper = (
                    sub_menus.filtered('theme_template_id')[:1]
                    or sub_menus[:1]
                )
                if keeper:
                    # Enforce structure only — preserve any UI-edited label.
                    keeper.write({'url': url, 'sequence': sequence})
                else:
                    keeper = Menu.create({
                        'name': name,
                        'url': url,
                        'sequence': sequence,
                        'parent_id': about_menu.id,
                        'website_id': website.id,
                    })
                    self._bs_set_menu_translation(keeper, name_th, th_active)
                (sub_menus - keeper).unlink()

        contact_pages = self.env['website.page'].sudo().search([
            ('website_id', '=', website.id),
            ('url', '=', '/contactus'),
        ], order='theme_template_id desc, id desc')
        contact_keeper = contact_pages.filtered(
            lambda page: page.view_id.key == 'theme_bs_hongqi_car.contact_us'
        )[:1] or contact_pages[:1]
        if contact_keeper:
            contact_keeper.write({
                'is_published': True,
                'url': '/contactus',
            })
            (contact_pages - contact_keeper).unlink()
