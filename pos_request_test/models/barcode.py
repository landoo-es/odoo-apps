# -*- encoding: utf-8 -*-


from odoo import models, fields, api
from odoo.tools.translate import _


class BarcodeRule(models.Model):
    _inherit = 'barcode.rule'

    type = fields.Selection(selection_add=[
        ('pos_request', _('POS Request'))
    ])
