# -*- coding: utf-8 -*-
{
    'name': 'Add products to bom in manufacturing orders',
    'summary': '',
    'author': 'Humanytek',
    'version': '1.1.0',
    'description': """
    """,
    'category': 'Mrp',
    'depends': [
        'mrp',
        'procurement',
        'stock',
    ],
    'data': [
        'wizard/add_products_view.xml',
        'mrp_view.xml',
    ],
}
