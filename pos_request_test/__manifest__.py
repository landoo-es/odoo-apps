# -*- coding: utf-8 -*-
# Part of BAKERY set of modules. See LICENSE file for full copyright and licensing details.
# Copyright 2017 Landoo SL, Aselcis SL.
# License OPL-1 or later. For more information, see LICENSE file.

{
    'name': "pos_request_test",

    'summary': """
        Añade la opción de hacer encargos al TPV. Versión de test.
    """,

    'author': "Landoo, Aselcis",
    'website': 'https://www.landoo.es',
    'category': 'Point of Sale',
    'version': '10.0.0.0.1',

    'depends': ['point_of_sale',],
    'data': [
        'views/products.xml',
        'views/pos.xml',
        'security/ir.model.access.csv',
        'security/pos_security.xml'
    ],
    'installable': True,
    'license': 'OPL-1',
}
