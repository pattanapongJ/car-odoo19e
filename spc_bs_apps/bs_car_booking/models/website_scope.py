# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import api, models
from odoo.http import request


class BsCarWebsiteScopeMixin(models.AbstractModel):
    _name = 'bs.car.website.scope.mixin'
    _description = 'BS Car Website/Company Scope Helpers'

    _bs_clear_website_cache_on_write = False

    @api.model
    def _current_website(self):
        website_id = self.env.context.get('website_id')
        if website_id:
            return self.env['website'].browse(website_id)
        try:
            return getattr(request, 'website', False) or self.env['website'].get_current_website()
        except (AttributeError, RuntimeError):
            return self.env['website'].get_current_website()

    @api.model
    def _current_website_company(self):
        website = self._current_website()
        if website:
            return website.company_id
        return self.env.company

    @api.model
    def _website_scope_domain(self):
        website = self._current_website()
        if website and 'website_id' in self._fields:
            return [('website_id', 'in', [False, website.id])]
        return []

    @api.model
    def _company_scope_domain(self):
        company = self._current_website_company()
        if company and 'company_id' in self._fields:
            return [('company_id', 'in', [False, company.id])]
        return []

    @api.model
    def _public_scope_domain(self):
        return self._website_scope_domain() + self._company_scope_domain()

    def _bs_clear_website_render_cache(self):
        """Invalidate Odoo website page/template caches after data changes.

        Odoo website pages cache rendered HTML in the templates cache family;
        that family also clears the `templates.cached_values` page-response
        cache used by website.page.
        """
        self.env.registry.clear_cache('templates')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if records and records._bs_clear_website_cache_on_write:
            records._bs_clear_website_render_cache()
        return records

    def write(self, vals):
        result = super().write(vals)
        if self and self._bs_clear_website_cache_on_write:
            self._bs_clear_website_render_cache()
        return result

    def unlink(self):
        clear_cache = bool(self and self._bs_clear_website_cache_on_write)
        result = super().unlink()
        if clear_cache:
            self._bs_clear_website_render_cache()
        return result
