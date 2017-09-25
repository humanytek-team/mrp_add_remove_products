# -*- coding: utf-8 -*-
{
    'name' : 'Add products to bom in manufacturing orders',
    'summary': '',
    'author': 'Humanytek',
    'description': """
    """,
    'category' : 'Mrp',
    'images' : [],
    'depends' : ['mrp','stock','procurement'],
    'data': [
        'wizard/add_products_view.xml',
        'mrp_view.xml',
    ],
    'demo': [

    ],
    'qweb': [
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
