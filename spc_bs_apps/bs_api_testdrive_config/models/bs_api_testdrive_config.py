from __future__ import annotations

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class BsApiTestdriveConfig(models.Model):
    _name = 'bs.api.testdrive.config'
    _description = 'Test Drive API Configuration'

    name: str = fields.Char(string='Name', required=True, default='ReadyPlanet R-CRM')
    api_url: str = fields.Char(
        string='API URL',
        required=True,
        default='https://api-rcrm.readyplanet.com/v2/lead/add',
        help='ReadyPlanet R-CRM v2 lead endpoint',
    )
    api_key: str = fields.Char(
        string='API Key',
        required=True,
        help='Authorization header value for R-CRM API',
    )
    business_id: str = fields.Char(
        string='Business ID',
        help='ReadyPlanet business_id sent in every lead payload',
    )
    gate_id: str = fields.Char(
        string='Gate ID',
        help='ReadyPlanet gate_id for lead routing',
    )
    active: bool = fields.Boolean(default=True)

    @api.model
    def create(self, vals: dict) -> BsApiTestdriveConfig:
        if self.search_count([]) >= 1:
            raise UserError(_(
                'Only one API configuration record is allowed. '
                'Please edit the existing one.'
            ))
        return super().create(vals)

    @api.constrains('api_url')
    def _check_api_url(self) -> None:
        for rec in self:
            if rec.api_url and not rec.api_url.startswith(('http://', 'https://')):
                raise ValidationError(_('API URL must start with http:// or https://'))
