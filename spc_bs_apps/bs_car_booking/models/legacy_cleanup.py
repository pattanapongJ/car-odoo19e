# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

from odoo import models


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    def action_cleanup_bs_car_booking_legacy_home_blocks(self):
        Menu = self.env['ir.ui.menu'].sudo()
        Action = self.env['ir.actions.act_window'].sudo()
        View = self.env['ir.ui.view'].sudo()
        Access = self.env['ir.model.access'].sudo()
        ModelData = self.env['ir.model.data'].sudo()

        legacy_actions = Action.search([('res_model', '=', 'bs.car.home.block')])
        if legacy_actions:
            action_names = ['ir.actions.act_window,%s' % action.id for action in legacy_actions]
            Menu.search([('action', 'in', action_names)]).unlink()
            legacy_actions.unlink()

        View.search([('model', '=', 'bs.car.home.block')]).unlink()
        Access.search([('model_id.model', '=', 'bs.car.home.block')]).unlink()
        ModelData.search([('model', '=', 'bs.car.home.block')]).unlink()
