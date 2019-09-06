# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import datetime

from prestapyt import PrestaShopWebServiceError

from openerp.addons.connector.unit.mapper import (mapping,
                                                  ImportMapper, only_create)
from ...unit.importer import TranslatableRecordImporter, DelayedBatchImporter
from ...unit.mapper import backend_to_m2o
from ...backend import prestashop


@prestashop
class ProductCategoryMapper(ImportMapper):
    _model_name = 'prestashop.product.category'

    direct = [
        ('position', 'sequence'),
        ('description', 'description'),
        ('link_rewrite', 'link_rewrite'),
        ('meta_description', 'meta_description'),
        ('meta_keywords', 'meta_keywords'),
        ('meta_title', 'meta_title'),
        (backend_to_m2o('id_shop_default'), 'default_shop_id'),
        ('active', 'active'),
        ('position', 'position')
    ]

    @only_create
    @mapping
    def name(self, record):
        if record['name'] is None:
            return {'name': ''}
        return {'name': record['name']}

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    @mapping
    def parent_id(self, record):
        if record['id_parent'] == '0':
            return {}
        parent = self.binder_for().to_openerp(record['id_parent'], unwrap=True)
        categ_binder = self.binder_for(
                        'prestashop.product.category')
        parent_categ_id  = categ_binder.to_openerp(
                        record['id_parent'], unwrap=True)
        return {'parent_id': parent.id,
                'prestashop_parent_category_id': parent_categ_id.id}

    @mapping
    def data_add(self, record):
        if record['date_add'] == '0000-00-00 00:00:00':
            return {'date_add': datetime.datetime.now()}
        return {'date_add': record['date_add']}

    @mapping
    def data_upd(self, record):
        if record['date_upd'] == '0000-00-00 00:00:00':
            return {'date_upd': datetime.datetime.now()}
        return {'date_upd': record['date_upd']}
    
    @only_create
    @mapping
    def openerp_id(self, record):
        """ Will bind the product category to an existing one with the same name """

        if self.backend_record.matching_product_template:
            categ_binder = self.binder_for(
                        'prestashop.product.category')
            categ_id  = categ_binder.to_openerp(
                        record['id'], unwrap=True)
            parent_categ_id  = categ_binder.to_openerp(
                        record['id_parent'], unwrap=True)
            
            if categ_id:
                #If already bound with this id, force the binding
                return {'openerp_id': categ_id.id}
            
            #If not, implement a way to map on categ name.
            name = self.name(record)['name']
            domain = [('name', '=', name),]
            
            categ_bound = self.env['prestashop.product.category'].search(
                [('backend_id', '=', self.backend_record.id),]
                )
            
            domain.append(('id', 'not in', [c.openerp_id.id for c in categ_bound ]))
            categ = self.env['product.category'].search(domain, order='id')
            if len(categ) >= 1 :
                return {'openerp_id': categ[0].id}                    
        else:
            return {}


@prestashop
class ProductCategoryImporter(TranslatableRecordImporter):
    _model_name = [
        'prestashop.product.category',
    ]

    _translatable_fields = {
        'prestashop.product.category': [
            'name',
            'description',
            'link_rewrite',
            'meta_description',
            'meta_keywords',
            'meta_title'
        ],
    }

    def _import_dependencies(self):
        record = self.prestashop_record
        if record['id_parent'] != '0':
            try:
                self._import_dependency(record['id_parent'],
                                        'prestashop.product.category')
            except PrestaShopWebServiceError:
                # TODO check this silent error
                pass


@prestashop
class ProductCategoryBatchImporter(DelayedBatchImporter):
    _model_name = 'prestashop.product.category'
