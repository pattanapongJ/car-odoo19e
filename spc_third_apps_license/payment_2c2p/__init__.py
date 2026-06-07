# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    See LICENSE file for full copyright and licensing details.
#################################################################################

from . import models
from . import controllers

from odoo.exceptions import UserError
from odoo.service import common
from odoo.addons.payment import setup_provider, reset_payment_provider


def pre_init_check(env):
    version_info = common.exp_version()
    server_serie = version_info.get('server_serie')
    if server_serie != '19.0':
        raise UserError(
            f'Module support Odoo series 19.0 found {server_serie}.')


def post_init_hook(env):
    setup_provider(env, 'to_c_to_p')


def uninstall_hook(env):
    reset_payment_provider(env, 'to_c_to_p')
