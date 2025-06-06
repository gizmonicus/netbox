import json
import logging

from django.test import tag
from django.urls import reverse
from netaddr import IPNetwork
from rest_framework import status

from dcim.models import Device, DeviceRole, DeviceType, Interface, Manufacturer, Site
from ipam.choices import *
from ipam.models import *
from tenancy.models import Tenant
from utilities.data import string_to_ranges
from utilities.testing import APITestCase, APIViewTestCases, create_test_device, disable_logging


class AppTest(APITestCase):

    def test_root(self):

        url = reverse('ipam-api:api-root')
        response = self.client.get('{}?format=api'.format(url), **self.header)

        self.assertEqual(response.status_code, 200)


class ASNRangeTest(APIViewTestCases.APIViewTestCase):
    model = ASNRange
    brief_fields = ['description', 'display', 'id', 'name', 'url']
    bulk_update_data = {
        'description': 'New description',
    }

    @classmethod
    def setUpTestData(cls):
        rirs = (
            RIR(name='RIR 1', slug='rir-1', is_private=True),
            RIR(name='RIR 2', slug='rir-2', is_private=True),
        )
        RIR.objects.bulk_create(rirs)

        tenants = (
            Tenant(name='Tenant 1', slug='tenant-1'),
            Tenant(name='Tenant 2', slug='tenant-2'),
        )
        Tenant.objects.bulk_create(tenants)

        asn_ranges = (
            ASNRange(name='ASN Range 1', slug='asn-range-1', rir=rirs[0], tenant=tenants[0], start=100, end=199),
            ASNRange(name='ASN Range 2', slug='asn-range-2', rir=rirs[0], tenant=tenants[0], start=200, end=299),
            ASNRange(name='ASN Range 3', slug='asn-range-3', rir=rirs[0], tenant=tenants[0], start=300, end=399),
        )
        ASNRange.objects.bulk_create(asn_ranges)

        cls.create_data = [
            {
                'name': 'ASN Range 4',
                'slug': 'asn-range-4',
                'rir': rirs[1].pk,
                'start': 400,
                'end': 499,
                'tenant': tenants[1].pk,
            },
            {
                'name': 'ASN Range 5',
                'slug': 'asn-range-5',
                'rir': rirs[1].pk,
                'start': 500,
                'end': 599,
                'tenant': tenants[1].pk,
            },
            {
                'name': 'ASN Range 6',
                'slug': 'asn-range-6',
                'rir': rirs[1].pk,
                'start': 600,
                'end': 699,
                'tenant': tenants[1].pk,
            },
        ]

    def test_list_available_asns(self):
        """
        Test retrieval of all available ASNs within a parent range.
        """
        rir = RIR.objects.first()
        asnrange = ASNRange.objects.create(name='Range 1', slug='range-1', rir=rir, start=101, end=110)
        url = reverse('ipam-api:asnrange-available-asns', kwargs={'pk': asnrange.pk})
        self.add_permissions('ipam.view_asnrange', 'ipam.view_asn')

        response = self.client.get(url, **self.header)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 10)

    def test_create_single_available_asn(self):
        """
        Test creation of the first available ASN within a range.
        """
        rir = RIR.objects.first()
        asnrange = ASNRange.objects.create(name='Range 1', slug='range-1', rir=rir, start=101, end=110)
        url = reverse('ipam-api:asnrange-available-asns', kwargs={'pk': asnrange.pk})
        self.add_permissions('ipam.view_asnrange', 'ipam.add_asn')

        data = {
            'description': 'New ASN'
        }
        response = self.client.post(url, data, format='json', **self.header)
        self.assertHttpStatus(response, status.HTTP_201_CREATED)
        self.assertEqual(response.data['rir']['id'], asnrange.rir.pk)
        self.assertEqual(response.data['description'], data['description'])

    def test_create_multiple_available_asns(self):
        """
        Test the creation of several available ASNs within a parent range.
        """
        rir = RIR.objects.first()
        asnrange = ASNRange.objects.create(name='Range 1', slug='range-1', rir=rir, start=101, end=110)
        url = reverse('ipam-api:asnrange-available-asns', kwargs={'pk': asnrange.pk})
        self.add_permissions('ipam.view_asnrange', 'ipam.add_asn')

        # Try to create eleven ASNs (only ten are available)
        data = [
            {'description': f'New ASN {i}'}
            for i in range(1, 12)
        ]
        assert len(data) == 11
        response = self.client.post(url, data, format='json', **self.header)
        self.assertHttpStatus(response, status.HTTP_409_CONFLICT)
        self.assertIn('detail', response.data)

        # Create all ten available ASNs in a single request
        data.pop()
        assert len(data) == 10
        response = self.client.post(url, data, format='json', **self.header)
        self.assertHttpStatus(response, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data), 10)


class ASNTest(APIViewTestCases.APIViewTestCase):
    model = ASN
    brief_fields = ['asn', 'description', 'display', 'id', 'url']
    bulk_update_data = {
        'description': 'New description',
    }

    @classmethod
    def setUpTestData(cls):
        rirs = (
            RIR(name='RIR 1', slug='rir-1', is_private=True),
            RIR(name='RIR 2', slug='rir-2', is_private=True),
        )
        RIR.objects.bulk_create(rirs)

        sites = (
            Site(name='Site 1', slug='site-1'),
            Site(name='Site 2', slug='site-2')
        )
        Site.objects.bulk_create(sites)

        tenants = (
            Tenant(name='Tenant 1', slug='tenant-1'),
            Tenant(name='Tenant 2', slug='tenant-2'),
        )
        Tenant.objects.bulk_create(tenants)

        asns = (
            ASN(asn=65000, rir=rirs[0], tenant=tenants[0]),
            ASN(asn=65001, rir=rirs[0], tenant=tenants[1]),
            ASN(asn=4200000000, rir=rirs[1], tenant=tenants[0]),
            ASN(asn=4200000001, rir=rirs[1], tenant=tenants[1]),
        )
        ASN.objects.bulk_create(asns)

        asns[0].sites.set([sites[0]])
        asns[1].sites.set([sites[1]])
        asns[2].sites.set([sites[0]])
        asns[3].sites.set([sites[1]])

        cls.create_data = [
            {
                'asn': 64512,
                'rir': rirs[0].pk,
            },
            {
                'asn': 65002,
                'rir': rirs[0].pk,
            },
            {
                'asn': 4200000002,
                'rir': rirs[1].pk,
            },
        ]


class VRFTest(APIViewTestCases.APIViewTestCase):
    model = VRF
    brief_fields = ['description', 'display', 'id', 'name', 'prefix_count', 'rd', 'url']
    create_data = [
        {
            'name': 'VRF 4',
            'rd': '65000:4',
        },
        {
            'name': 'VRF 5',
            'rd': '65000:5',
        },
        {
            'name': 'VRF 6',
            'rd': '65000:6',
        },
    ]
    bulk_update_data = {
        'description': 'New description',
    }

    @classmethod
    def setUpTestData(cls):

        vrfs = (
            VRF(name='VRF 1', rd='65000:1'),
            VRF(name='VRF 2', rd='65000:2'),
            VRF(name='VRF 3'),  # No RD
        )
        VRF.objects.bulk_create(vrfs)


class RouteTargetTest(APIViewTestCases.APIViewTestCase):
    model = RouteTarget
    brief_fields = ['description', 'display', 'id', 'name', 'url']
    create_data = [
        {
            'name': '65000:1004',
        },
        {
            'name': '65000:1005',
        },
        {
            'name': '65000:1006',
        },
    ]
    bulk_update_data = {
        'description': 'New description',
    }

    @classmethod
    def setUpTestData(cls):

        route_targets = (
            RouteTarget(name='65000:1001'),
            RouteTarget(name='65000:1002'),
            RouteTarget(name='65000:1003'),
        )
        RouteTarget.objects.bulk_create(route_targets)


class RIRTest(APIViewTestCases.APIViewTestCase):
    model = RIR
    brief_fields = ['aggregate_count', 'description', 'display', 'id', 'name', 'slug', 'url']
    create_data = [
        {
            'name': 'RIR 4',
            'slug': 'rir-4',
        },
        {
            'name': 'RIR 5',
            'slug': 'rir-5',
        },
        {
            'name': 'RIR 6',
            'slug': 'rir-6',
        },
    ]
    bulk_update_data = {
        'description': 'New description',
    }

    @classmethod
    def setUpTestData(cls):

        rirs = (
            RIR(name='RIR 1', slug='rir-1'),
            RIR(name='RIR 2', slug='rir-2'),
            RIR(name='RIR 3', slug='rir-3'),
        )
        RIR.objects.bulk_create(rirs)


class AggregateTest(APIViewTestCases.APIViewTestCase):
    model = Aggregate
    brief_fields = ['description', 'display', 'family', 'id', 'prefix', 'url']
    bulk_update_data = {
        'description': 'New description',
    }

    @classmethod
    def setUpTestData(cls):

        rirs = (
            RIR(name='RIR 1', slug='rir-1'),
            RIR(name='RIR 2', slug='rir-2'),
        )
        RIR.objects.bulk_create(rirs)

        aggregates = (
            Aggregate(prefix=IPNetwork('10.0.0.0/8'), rir=rirs[0]),
            Aggregate(prefix=IPNetwork('172.16.0.0/12'), rir=rirs[0]),
            Aggregate(prefix=IPNetwork('192.168.0.0/16'), rir=rirs[0]),
        )
        Aggregate.objects.bulk_create(aggregates)

        cls.create_data = [
            {
                'prefix': '100.0.0.0/8',
                'rir': rirs[1].pk,
            },
            {
                'prefix': '101.0.0.0/8',
                'rir': rirs[1].pk,
            },
            {
                'prefix': '102.0.0.0/8',
                'rir': rirs[1].pk,
            },
        ]


class RoleTest(APIViewTestCases.APIViewTestCase):
    model = Role
    brief_fields = ['description', 'display', 'id', 'name', 'prefix_count', 'slug', 'url', 'vlan_count']
    create_data = [
        {
            'name': 'Role 4',
            'slug': 'role-4',
        },
        {
            'name': 'Role 5',
            'slug': 'role-5',
        },
        {
            'name': 'Role 6',
            'slug': 'role-6',
        },
    ]
    bulk_update_data = {
        'description': 'New description',
    }

    @classmethod
    def setUpTestData(cls):

        roles = (
            Role(name='Role 1', slug='role-1'),
            Role(name='Role 2', slug='role-2'),
            Role(name='Role 3', slug='role-3'),
        )
        Role.objects.bulk_create(roles)


class PrefixTest(APIViewTestCases.APIViewTestCase):
    model = Prefix
    brief_fields = ['_depth', 'description', 'display', 'family', 'id', 'prefix', 'url']
    create_data = [
        {
            'prefix': '192.168.4.0/24',
        },
        {
            'prefix': '192.168.5.0/24',
        },
        {
            'prefix': '192.168.6.0/24',
        },
    ]
    bulk_update_data = {
        'description': 'New description',
    }

    @classmethod
    def setUpTestData(cls):

        prefixes = (
            Prefix(prefix=IPNetwork('192.168.1.0/24')),
            Prefix(prefix=IPNetwork('192.168.2.0/24')),
            Prefix(prefix=IPNetwork('192.168.3.0/24')),
        )
        Prefix.objects.bulk_create(prefixes)

    @tag('regression')
    def test_clean_validates_scope(self):
        prefix = Prefix.objects.first()
        site = Site.objects.create(name='Test Site', slug='test-site')

        data = {'scope_type': 'dcim.site', 'scope_id': site.id}
        url = reverse('ipam-api:prefix-detail', kwargs={'pk': prefix.pk})
        self.add_permissions('ipam.change_prefix')

        response = self.client.patch(url, data, format='json', **self.header)
        self.assertHttpStatus(response, status.HTTP_200_OK)

    def test_list_available_prefixes(self):
        """
        Test retrieval of all available prefixes within a parent prefix.
        """
        vrf = VRF.objects.create(name='VRF 1')
        prefix = Prefix.objects.create(prefix=IPNetwork('192.0.2.0/24'), vrf=vrf)
        Prefix.objects.create(prefix=IPNetwork('192.0.2.64/26'), vrf=vrf)
        Prefix.objects.create(prefix=IPNetwork('192.0.2.192/27'), vrf=vrf)
        url = reverse('ipam-api:prefix-available-prefixes', kwargs={'pk': prefix.pk})
        self.add_permissions('ipam.view_prefix')

        # Retrieve all available IPs
        response = self.client.get(url, **self.header)
        available_prefixes = ['192.0.2.0/26', '192.0.2.128/26', '192.0.2.224/27']
        for i, p in enumerate(response.data):
            self.assertEqual(p['prefix'], available_prefixes[i])

    def test_create_single_available_prefix(self):
        """
        Test retrieval of the first available prefix within a parent prefix.
        """
        vrf = VRF.objects.create(name='VRF 1')
        prefix = Prefix.objects.create(prefix=IPNetwork('192.0.2.0/28'), vrf=vrf, is_pool=True)
        url = reverse('ipam-api:prefix-available-prefixes', kwargs={'pk': prefix.pk})
        self.add_permissions('ipam.view_prefix', 'ipam.add_prefix')

        # Create four available prefixes with individual requests
        prefixes_to_be_created = [
            '192.0.2.0/30',
            '192.0.2.4/30',
            '192.0.2.8/30',
            '192.0.2.12/30',
        ]
        for i in range(4):
            data = {
                'prefix_length': 30,
                'description': 'Test Prefix {}'.format(i + 1)
            }
            response = self.client.post(url, data, format='json', **self.header)
            self.assertHttpStatus(response, status.HTTP_201_CREATED)
            self.assertEqual(response.data['prefix'], prefixes_to_be_created[i])
            self.assertEqual(response.data['vrf']['id'], vrf.pk)
            self.assertEqual(response.data['description'], data['description'])

        # Try to create one more prefix
        response = self.client.post(url, {'prefix_length': 30}, format='json', **self.header)
        self.assertHttpStatus(response, status.HTTP_409_CONFLICT)
        self.assertIn('detail', response.data)

        # Try to create invalid prefix type
        response = self.client.post(url, {'prefix_length': '30'}, format='json', **self.header)
        self.assertHttpStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertIn('prefix_length', response.data[0])

    def test_create_multiple_available_prefixes(self):
        """
        Test the creation of available prefixes within a parent prefix.
        """
        vrf = VRF.objects.create(name='VRF 1')
        prefix = Prefix.objects.create(prefix=IPNetwork('192.0.2.0/28'), vrf=vrf, is_pool=True)
        url = reverse('ipam-api:prefix-available-prefixes', kwargs={'pk': prefix.pk})
        self.add_permissions('ipam.view_prefix', 'ipam.add_prefix')

        # Try to create five /30s (only four are available)
        data = [
            {'prefix_length': 30, 'description': 'Prefix 1'},
            {'prefix_length': 30, 'description': 'Prefix 2'},
            {'prefix_length': 30, 'description': 'Prefix 3'},
            {'prefix_length': 30, 'description': 'Prefix 4'},
            {'prefix_length': 30, 'description': 'Prefix 5'},
        ]
        response = self.client.post(url, data, format='json', **self.header)
        self.assertHttpStatus(response, status.HTTP_409_CONFLICT)
        self.assertIn('detail', response.data)

        # Verify that no prefixes were created (the entire /28 is still available)
        response = self.client.get(url, **self.header)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['prefix'], '192.0.2.0/28')

        # Create four /30s in a single request
        response = self.client.post(url, data[:4], format='json', **self.header)
        self.assertHttpStatus(response, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data), 4)

    def test_list_available_ips(self):
        """
        Test retrieval of all available IP addresses within a parent prefix.
        """
        vrf = VRF.objects.create(name='VRF 1')
        prefix = Prefix.objects.create(prefix=IPNetwork('192.0.2.0/29'), vrf=vrf, is_pool=True)
        url = reverse('ipam-api:prefix-available-ips', kwargs={'pk': prefix.pk})
        self.add_permissions('ipam.view_prefix', 'ipam.view_ipaddress')

        # Retrieve all available IPs
        response = self.client.get(url, **self.header)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 8)  # 8 because prefix.is_pool = True

        # Change the prefix to not be a pool and try again
        prefix.is_pool = False
        prefix.save()
        response = self.client.get(url, **self.header)
        self.assertEqual(len(response.data), 6)  # 8 - 2 because prefix.is_pool = False

    def test_create_single_available_ip(self):
        """
        Test retrieval of the first available IP address within a parent prefix.
        """
        vrf = VRF.objects.create(name='VRF 1')
        prefix = Prefix.objects.create(prefix=IPNetwork('192.0.2.0/30'), vrf=vrf, is_pool=True)
        url = reverse('ipam-api:prefix-available-ips', kwargs={'pk': prefix.pk})
        self.add_permissions('ipam.view_prefix', 'ipam.add_ipaddress')

        # Create all four available IPs with individual requests
        for i in range(1, 5):
            data = {
                'description': 'Test IP {}'.format(i)
            }
            response = self.client.post(url, data, format='json', **self.header)
            self.assertHttpStatus(response, status.HTTP_201_CREATED)
            self.assertEqual(response.data['vrf']['id'], vrf.pk)
            self.assertEqual(response.data['description'], data['description'])

        # Try to create one more IP
        response = self.client.post(url, {}, format='json', **self.header)
        self.assertHttpStatus(response, status.HTTP_409_CONFLICT)
        self.assertIn('detail', response.data)

    def test_create_multiple_available_ips(self):
        """
        Test the creation of available IP addresses within a parent prefix.
        """
        vrf = VRF.objects.create(name='VRF 1')
        prefix = Prefix.objects.create(prefix=IPNetwork('192.0.2.0/29'), vrf=vrf, is_pool=True)
        url = reverse('ipam-api:prefix-available-ips', kwargs={'pk': prefix.pk})
        self.add_permissions('ipam.view_prefix', 'ipam.add_ipaddress')

        # Try to create nine IPs (only eight are available)
        data = [{'description': f'Test IP {i}'} for i in range(1, 10)]  # 9 IPs
        response = self.client.post(url, data, format='json', **self.header)
        self.assertHttpStatus(response, status.HTTP_409_CONFLICT)
        self.assertIn('detail', response.data)

        # Create all eight available IPs in a single request
        data = [{'description': 'Test IP {}'.format(i)} for i in range(1, 9)]  # 8 IPs
        response = self.client.post(url, data, format='json', **self.header)
        self.assertHttpStatus(response, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data), 8)


class IPRangeTest(APIViewTestCases.APIViewTestCase):
    model = IPRange
    brief_fields = ['description', 'display', 'end_address', 'family', 'id', 'start_address', 'url']
    create_data = [
        {
            'start_address': '192.168.4.10/24',
            'end_address': '192.168.4.50/24',
        },
        {
            'start_address': '192.168.5.10/24',
            'end_address': '192.168.5.50/24',
        },
        {
            'start_address': '192.168.6.10/24',
            'end_address': '192.168.6.50/24',
        },
    ]
    bulk_update_data = {
        'description': 'New description',
    }

    @classmethod
    def setUpTestData(cls):

        ip_ranges = (
            IPRange(start_address=IPNetwork('192.168.1.10/24'), end_address=IPNetwork('192.168.1.50/24'), size=51),
            IPRange(start_address=IPNetwork('192.168.2.10/24'), end_address=IPNetwork('192.168.2.50/24'), size=51),
            IPRange(start_address=IPNetwork('192.168.3.10/24'), end_address=IPNetwork('192.168.3.50/24'), size=51),
        )
        IPRange.objects.bulk_create(ip_ranges)

    def test_list_available_ips(self):
        """
        Test retrieval of all available IP addresses within a parent IP range.
        """
        iprange = IPRange.objects.create(
            start_address=IPNetwork('192.0.2.10/24'),
            end_address=IPNetwork('192.0.2.19/24')
        )
        url = reverse('ipam-api:iprange-available-ips', kwargs={'pk': iprange.pk})
        self.add_permissions('ipam.view_iprange', 'ipam.view_ipaddress')

        # Retrieve all available IPs
        response = self.client.get(url, **self.header)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 10)

    def test_create_single_available_ip(self):
        """
        Test retrieval of the first available IP address within a parent IP range.
        """
        vrf = VRF.objects.create(name='Test VRF 1', rd='1234')
        iprange = IPRange.objects.create(
            start_address=IPNetwork('192.0.2.1/24'),
            end_address=IPNetwork('192.0.2.3/24'),
            vrf=vrf
        )
        url = reverse('ipam-api:iprange-available-ips', kwargs={'pk': iprange.pk})
        self.add_permissions('ipam.view_iprange', 'ipam.add_ipaddress')

        # Create all three available IPs with individual requests
        for i in range(1, 4):
            data = {
                'description': f'Test IP #{i}'
            }
            response = self.client.post(url, data, format='json', **self.header)
            self.assertHttpStatus(response, status.HTTP_201_CREATED)
            self.assertEqual(response.data['vrf']['id'], vrf.pk)
            self.assertEqual(response.data['description'], data['description'])

        # Try to create one more IP
        response = self.client.post(url, {}, format='json', **self.header)
        self.assertHttpStatus(response, status.HTTP_409_CONFLICT)
        self.assertIn('detail', response.data)

    def test_create_multiple_available_ips(self):
        """
        Test the creation of available IP addresses within a parent IP range.
        """
        iprange = IPRange.objects.create(
            start_address=IPNetwork('192.0.2.1/24'),
            end_address=IPNetwork('192.0.2.8/24')
        )
        url = reverse('ipam-api:iprange-available-ips', kwargs={'pk': iprange.pk})
        self.add_permissions('ipam.view_iprange', 'ipam.add_ipaddress')

        # Try to create nine IPs (only eight are available)
        data = [{'description': f'Test IP #{i}'} for i in range(1, 10)]  # 9 IPs
        response = self.client.post(url, data, format='json', **self.header)
        self.assertHttpStatus(response, status.HTTP_409_CONFLICT)
        self.assertIn('detail', response.data)

        # Create all eight available IPs in a single request
        data = [{'description': f'Test IP #{i}'} for i in range(1, 9)]  # 8 IPs
        response = self.client.post(url, data, format='json', **self.header)
        self.assertHttpStatus(response, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data), 8)


class IPAddressTest(APIViewTestCases.APIViewTestCase):
    model = IPAddress
    brief_fields = ['address', 'description', 'display', 'family', 'id', 'url']
    create_data = [
        {
            'address': '192.168.0.4/24',
        },
        {
            'address': '192.168.0.5/24',
        },
        {
            'address': '192.168.0.6/24',
        },
    ]
    bulk_update_data = {
        'description': 'New description',
    }
    graphql_filter = {
        'address': {'lookup': 'i_exact', 'value': '192.168.0.1/24'},
    }

    @classmethod
    def setUpTestData(cls):

        ip_addresses = (
            IPAddress(address=IPNetwork('192.168.0.1/24')),
            IPAddress(address=IPNetwork('192.168.0.2/24')),
            IPAddress(address=IPNetwork('192.168.0.3/24')),
        )
        IPAddress.objects.bulk_create(ip_addresses)

    def test_assign_object(self):
        """
        Test the creation of available IP addresses within a parent IP range.
        """
        site = Site.objects.create(name='Site 1')
        manufacturer = Manufacturer.objects.create(name='Manufacturer 1')
        device_type = DeviceType.objects.create(model='Device Type 1', manufacturer=manufacturer)
        role = DeviceRole.objects.create(name='Switch')
        device1 = Device.objects.create(
            name='Device 1',
            site=site,
            device_type=device_type,
            role=role,
            status='active'
        )
        interface1 = Interface.objects.create(name='Interface 1', device=device1, type='1000baset')
        interface2 = Interface.objects.create(name='Interface 2', device=device1, type='1000baset')
        device2 = Device.objects.create(
            name='Device 2',
            site=site,
            device_type=device_type,
            role=role,
            status='active'
        )
        interface3 = Interface.objects.create(name='Interface 3', device=device2, type='1000baset')

        ip_addresses = (
            IPAddress(address=IPNetwork('192.168.0.4/24'), assigned_object=interface1),
            IPAddress(address=IPNetwork('192.168.1.4/24')),
        )
        IPAddress.objects.bulk_create(ip_addresses)

        ip1 = ip_addresses[0]
        ip1.assigned_object = interface1
        device1.primary_ip4 = ip_addresses[0]
        device1.save()

        url = reverse('ipam-api:ipaddress-detail', kwargs={'pk': ip1.pk})
        self.add_permissions('ipam.change_ipaddress')

        # assign to same parent
        data = {
            'assigned_object_id': interface2.pk
        }
        response = self.client.patch(url, data, format='json', **self.header)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        # assign to same different parent - should error
        data = {
            'assigned_object_id': interface3.pk
        }
        response = self.client.patch(url, data, format='json', **self.header)
        self.assertHttpStatus(response, status.HTTP_400_BAD_REQUEST)


class FHRPGroupTest(APIViewTestCases.APIViewTestCase):
    model = FHRPGroup
    brief_fields = ['description', 'display', 'group_id', 'id', 'protocol', 'url']
    bulk_update_data = {
        'protocol': FHRPGroupProtocolChoices.PROTOCOL_GLBP,
        'group_id': 200,
        'auth_type': FHRPGroupAuthTypeChoices.AUTHENTICATION_MD5,
        'auth_key': 'foobarbaz999',
        'name': 'foobar-999',
        'description': 'New description',
    }

    @classmethod
    def setUpTestData(cls):
        fhrp_groups = (
            FHRPGroup(
                protocol=FHRPGroupProtocolChoices.PROTOCOL_VRRP2,
                group_id=10,
                auth_type=FHRPGroupAuthTypeChoices.AUTHENTICATION_PLAINTEXT,
                auth_key='foobar123',
            ),
            FHRPGroup(
                protocol=FHRPGroupProtocolChoices.PROTOCOL_VRRP3,
                group_id=20,
                auth_type=FHRPGroupAuthTypeChoices.AUTHENTICATION_MD5,
                auth_key='foobar123',
            ),
            FHRPGroup(protocol=FHRPGroupProtocolChoices.PROTOCOL_HSRP, group_id=30),
        )
        FHRPGroup.objects.bulk_create(fhrp_groups)

        cls.create_data = [
            {
                'protocol': FHRPGroupProtocolChoices.PROTOCOL_VRRP2,
                'group_id': 110,
                'auth_type': FHRPGroupAuthTypeChoices.AUTHENTICATION_PLAINTEXT,
                'auth_key': 'foobar123',
            },
            {
                'protocol': FHRPGroupProtocolChoices.PROTOCOL_VRRP3,
                'group_id': 120,
                'auth_type': FHRPGroupAuthTypeChoices.AUTHENTICATION_MD5,
                'auth_key': 'barfoo456',
            },
            {
                'protocol': FHRPGroupProtocolChoices.PROTOCOL_GLBP,
                'group_id': 130,
            },
        ]


class FHRPGroupAssignmentTest(APIViewTestCases.APIViewTestCase):
    model = FHRPGroupAssignment
    brief_fields = ['display', 'group', 'id', 'interface_id', 'interface_type', 'priority', 'url']
    bulk_update_data = {
        'priority': 100,
    }
    user_permissions = ('ipam.view_fhrpgroup', )

    @classmethod
    def setUpTestData(cls):

        device1 = create_test_device('device1')
        device2 = create_test_device('device2')
        device3 = create_test_device('device3')

        interfaces = (
            Interface(device=device1, name='eth0', type='other'),
            Interface(device=device1, name='eth1', type='other'),
            Interface(device=device1, name='eth2', type='other'),
            Interface(device=device2, name='eth0', type='other'),
            Interface(device=device2, name='eth1', type='other'),
            Interface(device=device2, name='eth2', type='other'),
            Interface(device=device3, name='eth0', type='other'),
            Interface(device=device3, name='eth1', type='other'),
            Interface(device=device3, name='eth2', type='other'),
        )
        Interface.objects.bulk_create(interfaces)

        ip_addresses = (
            IPAddress(address=IPNetwork('192.168.0.2/24'), assigned_object=interfaces[0]),
            IPAddress(address=IPNetwork('192.168.1.2/24'), assigned_object=interfaces[1]),
            IPAddress(address=IPNetwork('192.168.2.2/24'), assigned_object=interfaces[2]),
            IPAddress(address=IPNetwork('192.168.0.3/24'), assigned_object=interfaces[3]),
            IPAddress(address=IPNetwork('192.168.1.3/24'), assigned_object=interfaces[4]),
            IPAddress(address=IPNetwork('192.168.2.3/24'), assigned_object=interfaces[5]),
            IPAddress(address=IPNetwork('192.168.0.4/24'), assigned_object=interfaces[6]),
            IPAddress(address=IPNetwork('192.168.1.4/24'), assigned_object=interfaces[7]),
            IPAddress(address=IPNetwork('192.168.2.4/24'), assigned_object=interfaces[8]),
        )
        IPAddress.objects.bulk_create(ip_addresses)

        fhrp_groups = (
            FHRPGroup(protocol=FHRPGroupProtocolChoices.PROTOCOL_VRRP2, group_id=10),
            FHRPGroup(protocol=FHRPGroupProtocolChoices.PROTOCOL_VRRP2, group_id=20),
            FHRPGroup(protocol=FHRPGroupProtocolChoices.PROTOCOL_VRRP2, group_id=30),
        )
        FHRPGroup.objects.bulk_create(fhrp_groups)

        fhrp_group_assignments = (
            FHRPGroupAssignment(group=fhrp_groups[0], interface=interfaces[0], priority=10),
            FHRPGroupAssignment(group=fhrp_groups[1], interface=interfaces[1], priority=10),
            FHRPGroupAssignment(group=fhrp_groups[2], interface=interfaces[2], priority=10),
            FHRPGroupAssignment(group=fhrp_groups[0], interface=interfaces[3], priority=20),
            FHRPGroupAssignment(group=fhrp_groups[1], interface=interfaces[4], priority=20),
            FHRPGroupAssignment(group=fhrp_groups[2], interface=interfaces[5], priority=20),
        )
        FHRPGroupAssignment.objects.bulk_create(fhrp_group_assignments)

        cls.create_data = [
            {
                'group': fhrp_groups[0].pk,
                'interface_type': 'dcim.interface',
                'interface_id': interfaces[6].pk,
                'priority': 30,
            },
            {
                'group': fhrp_groups[1].pk,
                'interface_type': 'dcim.interface',
                'interface_id': interfaces[7].pk,
                'priority': 30,
            },
            {
                'group': fhrp_groups[2].pk,
                'interface_type': 'dcim.interface',
                'interface_id': interfaces[8].pk,
                'priority': 30,
            },
        ]


class VLANGroupTest(APIViewTestCases.APIViewTestCase):
    model = VLANGroup
    brief_fields = ['description', 'display', 'id', 'name', 'slug', 'url', 'vlan_count']
    create_data = [
        {
            'name': 'VLAN Group 4',
            'slug': 'vlan-group-4',
        },
        {
            'name': 'VLAN Group 5',
            'slug': 'vlan-group-5',
        },
        {
            'name': 'VLAN Group 6',
            'slug': 'vlan-group-6',
        },
    ]
    bulk_update_data = {
        'description': 'New description',
    }

    @classmethod
    def setUpTestData(cls):

        vlan_groups = (
            VLANGroup(name='VLAN Group 1', slug='vlan-group-1'),
            VLANGroup(name='VLAN Group 2', slug='vlan-group-2'),
            VLANGroup(name='VLAN Group 3', slug='vlan-group-3'),
        )
        VLANGroup.objects.bulk_create(vlan_groups)

    def test_list_available_vlans(self):
        """
        Test retrieval of all available VLANs within a group.
        """
        MIN_VID = 100
        MAX_VID = 199

        self.add_permissions('ipam.view_vlangroup', 'ipam.view_vlan')
        vlangroup = VLANGroup.objects.create(
            name='VLAN Group X',
            slug='vlan-group-x',
            vid_ranges=string_to_ranges(f"{MIN_VID}-{MAX_VID}")
        )

        # Create a set of VLANs within the group
        vlans = (
            VLAN(vid=10, name='VLAN 10', group=vlangroup),
            VLAN(vid=20, name='VLAN 20', group=vlangroup),
            VLAN(vid=30, name='VLAN 30', group=vlangroup),
        )
        VLAN.objects.bulk_create(vlans)

        # Retrieve all available VLANs
        url = reverse('ipam-api:vlangroup-available-vlans', kwargs={'pk': vlangroup.pk})
        response = self.client.get(f'{url}?limit=0', **self.header)
        self.assertEqual(len(response.data), MAX_VID - MIN_VID + 1)
        available_vlans = {vlan['vid'] for vlan in response.data}
        for vlan in vlans:
            self.assertNotIn(vlan.vid, available_vlans)

        # Retrieve a maximum number of available VLANs
        url = reverse('ipam-api:vlangroup-available-vlans', kwargs={'pk': vlangroup.pk})
        response = self.client.get(f'{url}?limit=10', **self.header)
        self.assertEqual(len(response.data), 10)

    def test_create_single_available_vlan(self):
        """
        Test the creation of a single available VLAN.
        """
        self.add_permissions('ipam.view_vlangroup', 'ipam.view_vlan', 'ipam.add_vlan')
        vlangroup = VLANGroup.objects.first()
        VLAN.objects.create(vid=1, name='VLAN 1', group=vlangroup)

        data = {
            "name": "First VLAN",
        }
        url = reverse('ipam-api:vlangroup-available-vlans', kwargs={'pk': vlangroup.pk})
        response = self.client.post(url, data, format='json', **self.header)

        self.assertHttpStatus(response, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], data['name'])
        self.assertEqual(response.data['group']['id'], vlangroup.pk)
        self.assertEqual(response.data['vid'], 2)

    def test_create_multiple_available_vlans(self):
        """
        Test the creation of multiple available VLANs.
        """
        self.add_permissions('ipam.view_vlangroup', 'ipam.view_vlan', 'ipam.add_vlan')
        vlangroup = VLANGroup.objects.first()

        vlans = (
            VLAN(vid=1, name='VLAN 1', group=vlangroup),
            VLAN(vid=3, name='VLAN 3', group=vlangroup),
            VLAN(vid=5, name='VLAN 5', group=vlangroup),
        )
        VLAN.objects.bulk_create(vlans)

        data = (
            {"name": "First VLAN"},
            {"name": "Second VLAN"},
            {"name": "Third VLAN"},
        )
        url = reverse('ipam-api:vlangroup-available-vlans', kwargs={'pk': vlangroup.pk})
        response = self.client.post(url, data, format='json', **self.header)

        self.assertHttpStatus(response, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data), 3)
        self.assertEqual(response.data[0]['name'], data[0]['name'])
        self.assertEqual(response.data[0]['group']['id'], vlangroup.pk)
        self.assertEqual(response.data[0]['vid'], 2)
        self.assertEqual(response.data[1]['name'], data[1]['name'])
        self.assertEqual(response.data[1]['group']['id'], vlangroup.pk)
        self.assertEqual(response.data[1]['vid'], 4)
        self.assertEqual(response.data[2]['name'], data[2]['name'])
        self.assertEqual(response.data[2]['group']['id'], vlangroup.pk)
        self.assertEqual(response.data[2]['vid'], 6)


class VLANTest(APIViewTestCases.APIViewTestCase):
    model = VLAN
    brief_fields = ['description', 'display', 'id', 'name', 'url', 'vid']
    bulk_update_data = {
        'description': 'New description',
    }

    @classmethod
    def setUpTestData(cls):

        vlan_groups = (
            VLANGroup(name='VLAN Group 1', slug='vlan-group-1'),
            VLANGroup(name='VLAN Group 2', slug='vlan-group-2'),
        )
        VLANGroup.objects.bulk_create(vlan_groups)

        vlans = (
            VLAN(name='VLAN 1', vid=1, group=vlan_groups[0]),
            VLAN(name='VLAN 2', vid=2, group=vlan_groups[0]),
            VLAN(name='VLAN 3', vid=3, group=vlan_groups[0]),
            VLAN(name='SVLAN 1', vid=1001, qinq_role=VLANQinQRoleChoices.ROLE_SERVICE),
        )
        VLAN.objects.bulk_create(vlans)

        cls.create_data = [
            {
                'vid': 4,
                'name': 'VLAN 4',
                'group': vlan_groups[1].pk,
            },
            {
                'vid': 5,
                'name': 'VLAN 5',
                'group': vlan_groups[1].pk,
            },
            {
                'vid': 6,
                'name': 'VLAN 6',
                'group': vlan_groups[1].pk,
            },
            {
                'vid': 2001,
                'name': 'CVLAN 1',
                'qinq_role': VLANQinQRoleChoices.ROLE_CUSTOMER,
                'qinq_svlan': vlans[3].pk,
            },
        ]

    def test_delete_vlan_with_prefix(self):
        """
        Attempt and fail to delete a VLAN with a Prefix assigned to it.
        """
        vlan = VLAN.objects.first()
        Prefix.objects.create(prefix=IPNetwork('192.0.2.0/24'), vlan=vlan)

        self.add_permissions('ipam.delete_vlan')
        url = reverse('ipam-api:vlan-detail', kwargs={'pk': vlan.pk})
        with disable_logging(level=logging.WARNING):
            response = self.client.delete(url, **self.header)

        self.assertHttpStatus(response, status.HTTP_409_CONFLICT)

        content = json.loads(response.content.decode('utf-8'))
        self.assertIn('detail', content)
        self.assertTrue(content['detail'].startswith('Unable to delete object.'))


class VLANTranslationPolicyTest(APIViewTestCases.APIViewTestCase):
    model = VLANTranslationPolicy
    brief_fields = ['description', 'display', 'id', 'name', 'url',]
    bulk_update_data = {
        'description': 'New description',
    }

    @classmethod
    def setUpTestData(cls):

        vlan_translation_policies = (
            VLANTranslationPolicy(
                name='Policy 1',
                description='foobar1',
            ),
            VLANTranslationPolicy(
                name='Policy 2',
                description='foobar2',
            ),
            VLANTranslationPolicy(
                name='Policy 3',
                description='foobar3',
            ),
        )
        VLANTranslationPolicy.objects.bulk_create(vlan_translation_policies)

        cls.create_data = [
            {
                'name': 'Policy 4',
                'description': 'foobar4',
            },
            {
                'name': 'Policy 5',
                'description': 'foobar5',
            },
            {
                'name': 'Policy 6',
                'description': 'foobar6',
            },
        ]


class VLANTranslationRuleTest(APIViewTestCases.APIViewTestCase):
    model = VLANTranslationRule
    brief_fields = ['description', 'display', 'id', 'local_vid', 'policy', 'remote_vid', 'url']

    @classmethod
    def setUpTestData(cls):

        vlan_translation_policies = (
            VLANTranslationPolicy(
                name='Policy 1',
                description='foobar1',
            ),
            VLANTranslationPolicy(
                name='Policy 2',
                description='foobar2',
            ),
        )
        VLANTranslationPolicy.objects.bulk_create(vlan_translation_policies)

        vlan_translation_rules = (
            VLANTranslationRule(
                policy=vlan_translation_policies[0],
                local_vid=100,
                remote_vid=200,
                description='foo',
            ),
            VLANTranslationRule(
                policy=vlan_translation_policies[0],
                local_vid=101,
                remote_vid=201,
                description='bar',
            ),
            VLANTranslationRule(
                policy=vlan_translation_policies[1],
                local_vid=102,
                remote_vid=202,
                description='baz',
            ),
        )
        VLANTranslationRule.objects.bulk_create(vlan_translation_rules)

        cls.create_data = [
            {
                'policy': vlan_translation_policies[0].pk,
                'local_vid': 300,
                'remote_vid': 400,
            },
            {
                'policy': vlan_translation_policies[0].pk,
                'local_vid': 301,
                'remote_vid': 401,
            },
            {
                'policy': vlan_translation_policies[1].pk,
                'local_vid': 302,
                'remote_vid': 402,
            },
        ]

        cls.bulk_update_data = {
            'policy': vlan_translation_policies[1].pk,
        }


class ServiceTemplateTest(APIViewTestCases.APIViewTestCase):
    model = ServiceTemplate
    brief_fields = ['description', 'display', 'id', 'name', 'ports', 'protocol', 'url']
    bulk_update_data = {
        'description': 'New description',
    }

    @classmethod
    def setUpTestData(cls):
        service_templates = (
            ServiceTemplate(name='Service Template 1', protocol=ServiceProtocolChoices.PROTOCOL_TCP, ports=[1, 2]),
            ServiceTemplate(name='Service Template 2', protocol=ServiceProtocolChoices.PROTOCOL_TCP, ports=[3, 4]),
            ServiceTemplate(name='Service Template 3', protocol=ServiceProtocolChoices.PROTOCOL_TCP, ports=[5, 6]),
        )
        ServiceTemplate.objects.bulk_create(service_templates)

        cls.create_data = [
            {
                'name': 'Service Template 4',
                'protocol': ServiceProtocolChoices.PROTOCOL_TCP,
                'ports': [7, 8],
            },
            {
                'name': 'Service Template 5',
                'protocol': ServiceProtocolChoices.PROTOCOL_TCP,
                'ports': [9, 10],
            },
            {
                'name': 'Service Template 6',
                'protocol': ServiceProtocolChoices.PROTOCOL_TCP,
                'ports': [11, 12],
            },
        ]


class ServiceTest(APIViewTestCases.APIViewTestCase):
    model = Service
    brief_fields = ['description', 'display', 'id', 'name', 'ports', 'protocol', 'url']
    bulk_update_data = {
        'description': 'New description',
    }

    @classmethod
    def setUpTestData(cls):
        site = Site.objects.create(name='Site 1', slug='site-1')
        manufacturer = Manufacturer.objects.create(name='Manufacturer 1', slug='manufacturer-1')
        devicetype = DeviceType.objects.create(manufacturer=manufacturer, model='Device Type 1')
        role = DeviceRole.objects.create(name='Device Role 1', slug='device-role-1')

        devices = (
            Device(name='Device 1', site=site, device_type=devicetype, role=role),
            Device(name='Device 2', site=site, device_type=devicetype, role=role),
        )
        Device.objects.bulk_create(devices)

        services = (
            Service(parent=devices[0], name='Service 1', protocol=ServiceProtocolChoices.PROTOCOL_TCP, ports=[1]),
            Service(parent=devices[0], name='Service 2', protocol=ServiceProtocolChoices.PROTOCOL_TCP, ports=[2]),
            Service(parent=devices[0], name='Service 3', protocol=ServiceProtocolChoices.PROTOCOL_TCP, ports=[3]),
        )
        Service.objects.bulk_create(services)

        cls.create_data = [
            {
                'parent_object_id': devices[1].pk,
                'parent_object_type': 'dcim.device',
                'name': 'Service 4',
                'protocol': ServiceProtocolChoices.PROTOCOL_TCP,
                'ports': [4],
            },
            {
                'parent_object_id': devices[1].pk,
                'parent_object_type': 'dcim.device',
                'name': 'Service 5',
                'protocol': ServiceProtocolChoices.PROTOCOL_TCP,
                'ports': [5],
            },
            {
                'parent_object_id': devices[1].pk,
                'parent_object_type': 'dcim.device',
                'name': 'Service 6',
                'protocol': ServiceProtocolChoices.PROTOCOL_TCP,
                'ports': [6],
            },
        ]
