# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import models


class ThemeUtils(models.AbstractModel):
    _inherit = 'theme.utils'

    def _theme_bs_hongqi_car_post_copy(self, mod):
        website = self.env['website'].browse(self.env.context.get('website_id'))
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

        websites = self.env['website'].sudo().search([('theme_id', '=', theme.id)])
        for website in websites:
            self._theme_bs_hongqi_car_cleanup_website(website)

    def _theme_bs_hongqi_car_sync_theme_templates(self):
        """Keep noupdate theme menu templates aligned across upgrades."""
        home_view = self.env.ref('theme_bs_hongqi_car.hongqi_home_view', raise_if_not_found=False)
        if home_view:
            home_view.sudo().write({
                'arch': self._theme_bs_hongqi_car_home_arch(),
            })

        menu_updates = {
            'theme_bs_hongqi_car.menu_website_home': ('Home', '/showroom', 5),
            'theme_bs_hongqi_car.menu_website_cars': ('Models', '/cars', 10),
            'theme_bs_hongqi_car.menu_website_stories': ('News', '/stories', 30),
            # TEMPORARILY HIDDEN (2026-06-12, business request) — restore by
            # uncommenting here AND in expected_menus below, then re-run the
            # theme cleanup (the cleanup recreates missing expected menus).
            # 'theme_bs_hongqi_car.menu_website_track': ('My Booking', '/track', 40),
            # 'theme_bs_hongqi_car.menu_website_about': ('About Us', '/about-us', 50),
            'theme_bs_hongqi_car.menu_website_contact': ('Contact Us', '/contactus', 60),
        }
        for xmlid, (name, url, sequence) in menu_updates.items():
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if menu:
                menu.sudo().write({
                    'name': name,
                    'url': url,
                    'sequence': sequence,
                })

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
            <!-- Data-driven sections (managed via backend Section records, NOT the
                 builder). They use t-call, so they must NOT sit inside an oe_structure
                 or the editor turns the whole region read-only. -->
            <t t-call="bs_car_booking.home_sections_content"/>
            <!-- Builder drop zone: free-form Odoo snippets can be dropped/saved here
                 (per website), while the cinematic sections above stay data-driven. -->
            <div class="oe_structure" id="oe_structure_hongqi_home"/>
        </div>
    </t>
</t>
""".strip()

    def _theme_bs_hongqi_car_sync_home_page(self, website):
        template = self.env.ref('theme_bs_hongqi_car.hongqi_home_view', raise_if_not_found=False)
        if not template:
            return

        View = self.env['ir.ui.view'].sudo().with_context(active_test=False)
        Page = self.env['website.page'].sudo().with_context(active_test=False)
        home_view = (template.copy_ids.filtered(lambda view: view.website_id == website)[:1]
                     or View.search([
                         ('key', '=', 'theme_bs_hongqi_car.hongqi_home'),
                         ('website_id', '=', website.id),
                     ], limit=1))
        if home_view:
            home_view.write({
                'arch_db': template.arch,
                'active': True,
            })

        pages = Page.search([
            ('website_id', '=', website.id),
            ('url', '=', '/showroom'),
        ], order='theme_template_id desc, id desc')
        keeper = pages.filtered(lambda page: page.view_id == home_view)[:1] or pages[:1]
        if keeper:
            keeper.write({
                'name': 'Hongqi Car Home',
                'url': '/showroom',
                'is_published': True,
                'view_id': home_view.id if home_view else keeper.view_id.id,
            })
            (pages - keeper).unlink()

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

        expected_menus = {
            '/showroom': ('Home', 5),
            '/cars': ('Models', 10),
            '/stories': ('News', 30),
            # TEMPORARILY HIDDEN (2026-06-12) — see note in menu_updates above.
            # '/track': ('My Booking', 40),
            # '/about-us': ('About Us', 50),
            '/contactus': ('Contact Us', 60),
        }
        for url, (name, sequence) in expected_menus.items():
            menus = Menu.search([
                ('website_id', '=', website.id),
                ('parent_id', '=', top_menu.id),
                ('url', '=', url),
            ], order='theme_template_id desc, sequence, id')
            keeper = menus.filtered('theme_template_id')[:1] or menus[:1]
            if keeper:
                keeper.write({
                    'name': name,
                    'url': url,
                    'sequence': sequence,
                })
                (menus - keeper).unlink()
            else:
                Menu.create({
                    'name': name,
                    'url': url,
                    'sequence': sequence,
                    'parent_id': top_menu.id,
                    'website_id': website.id,
                })

        Menu.search([
            ('website_id', '=', website.id),
            ('parent_id', '=', top_menu.id),
            ('url', '=', '/'),
            ('theme_template_id', '=', False),
        ]).unlink()

        # Remove legacy root/home duplicates from earlier theme iterations.
        Menu.search([
            ('website_id', '=', website.id),
            ('parent_id', '=', top_menu.id),
            ('url', '=', '/'),
        ]).unlink()

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
