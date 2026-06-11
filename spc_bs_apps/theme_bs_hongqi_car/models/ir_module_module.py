# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import models


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    def _theme_load(self, website):
        result = super()._theme_load(website)
        if any(module.name == 'theme_bs_hongqi_car' for module in self):
            self.env['theme.utils'].with_context(
                website_id=website.id,
            )._theme_bs_hongqi_car_cleanup_website(website)
        return result

    def action_cleanup_theme_bs_hongqi_car(self):
        self.env['theme.utils']._theme_bs_hongqi_car_cleanup_installed_websites()

    def action_reset_theme_bs_hongqi_car_templates(self):
        self.env['theme.utils']._theme_bs_hongqi_car_reset_theme_templates()
