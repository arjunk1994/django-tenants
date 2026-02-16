import logging

from django.db import connections
from django_tenants.utils import get_tenant_database_alias


class TenantContextFilter(logging.Filter):
    """
    Add the current ``schema_name`` and ``domain_url`` to log records.
    Thanks to @regolith for the snippet on https://github.com/bernardopires/django-tenant-schemas/issues/248
    """
    def filter(self, record):
        try:
            conn = connections[get_tenant_database_alias()]
            record.schema_name = conn.tenant.schema_name
            record.domain_url = getattr(conn.tenant, 'domain_url', None)
        except Exception:
            record.schema_name = 'public'
            record.domain_url = None
        return True
