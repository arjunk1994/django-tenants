from unittest import mock

from django.test import RequestFactory, SimpleTestCase

from django_tenants import utils
from django_tenants.middleware import TenantMainMiddleware
from django_tenants.test.cases import TenantTestCase
from django.core.management.commands.migrate import Command as MigrateCommand
from django.test.utils import override_settings

from django_tenants.utils import get_tenant


class CustomMigrateCommand(MigrateCommand):
    pass


class ConfigStringParsingTestCase(TenantTestCase):
    def test_static_string(self):
        self.assertEqual(
            utils.parse_tenant_config_path("foo"),
            "foo/{}".format(self.tenant.schema_name),
        )

    def test_format_string(self):
        self.assertEqual(
            utils.parse_tenant_config_path("foo/%s/bar"),
            "foo/{}/bar".format(self.tenant.schema_name),
        )

        # Preserve trailing slash
        self.assertEqual(
            utils.parse_tenant_config_path("foo/%s/bar/"),
            "foo/{}/bar/".format(self.tenant.schema_name),
        )

    def test_get_tenant_base_migrate_command_class_default(self):
        self.assertEqual(
            utils.get_tenant_base_migrate_command_class(),
            MigrateCommand,
        )

    def test_get_tenant_base_migrate_command_class_custom(self):
        command_path = 'django_tenants.tests.test_utils.CustomMigrateCommand'
        with override_settings(TENANT_BASE_MIGRATE_COMMAND=command_path):
            self.assertEqual(
                utils.get_tenant_base_migrate_command_class(),
                CustomMigrateCommand,
            )

    def test_get_tenant(self):
        tenant_domain = 'tenant.test.com'
        factory = RequestFactory()
        tm = TenantMainMiddleware(lambda r: r)
        request = factory.get('/any/request/', HTTP_HOST=tenant_domain)
        tm.process_request(request)
        self.assertEqual(get_tenant(request).schema_name, 'test')


class MultiDbContextTestCase(SimpleTestCase):
    def test_schema_context_updates_and_restores_other_connections(self):
        primary = mock.Mock()
        primary.tenant = object()

        replica = mock.Mock()
        replica.tenant = None
        replica.set_schema = mock.Mock()
        replica.set_schema_to_public = mock.Mock()

        mocked_connections = {
            'default': primary,
            'replica1': replica,
        }

        with override_settings(MULTI_DB_ENABLED=True):
            with mock.patch.object(utils, 'connections', mocked_connections):
                with utils.schema_context('tenant1'):
                    pass

        primary.set_schema.assert_called_once_with('tenant1')
        replica.set_schema.assert_called_once_with('tenant1')
        replica.set_schema_to_public.assert_called_once_with()
        primary.set_tenant.assert_called_once_with(primary.tenant)

    def test_tenant_context_updates_and_restores_other_connections(self):
        previous_primary_tenant = object()
        previous_replica_tenant = object()

        primary = mock.Mock()
        primary.tenant = previous_primary_tenant

        replica = mock.Mock()
        replica.tenant = previous_replica_tenant
        replica.set_tenant = mock.Mock()

        tenant = object()
        mocked_connections = {
            'default': primary,
            'replica1': replica,
        }

        with override_settings(MULTI_DB_ENABLED=True):
            with mock.patch.object(utils, 'connections', mocked_connections):
                with utils.tenant_context(tenant):
                    pass

        primary.set_tenant.assert_has_calls(
            [mock.call(tenant), mock.call(previous_primary_tenant)]
        )
        replica.set_tenant.assert_has_calls(
            [mock.call(tenant), mock.call(previous_replica_tenant)]
        )

    def test_contexts_only_touch_selected_database_when_multidb_disabled(self):
        primary = mock.Mock()
        primary.tenant = None

        replica = mock.Mock()
        replica.tenant = None
        replica.set_schema = mock.Mock()
        replica.set_tenant = mock.Mock()

        mocked_connections = {
            'default': primary,
            'replica1': replica,
        }

        with override_settings(MULTI_DB_ENABLED=False):
            with mock.patch.object(utils, 'connections', mocked_connections):
                with utils.schema_context('tenant1'):
                    pass

                with utils.tenant_context(object()):
                    pass

        replica.set_schema.assert_not_called()
        replica.set_tenant.assert_not_called()
