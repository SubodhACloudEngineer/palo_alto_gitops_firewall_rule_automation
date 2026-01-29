#!/usr/bin/env python3
"""
Azure to NetBox Sync Script
============================

Syncs Azure resources from a resource group to NetBox:
- Virtual Machines (VMs)
- Virtual Networks (VNets)
- Subnets
- Network Interfaces (NICs)
- Public IP addresses
- Private IP addresses
- Network Security Groups (NSGs)
- Bastion Hosts

Author: Network Automation Team
Version: 1.0
"""

import sys
import json
from datetime import datetime
from azure.identity import DefaultAzureCredential, AzureCliCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient
import requests
from urllib3.exceptions import InsecureRequestWarning

# Disable SSL warnings
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# ============================================
# CONFIGURATION
# ============================================

# Azure Configuration
AZURE_CONFIG = {
    'subscription_id': '8527d19f-1ff6-461c-a89e-da961a355bed',  # Your subscription
    'resource_group': 'rg-panorama-gitops-poc',
    'location': 'eastus'
}

# NetBox Configuration
NETBOX_CONFIG = {
    'url': 'http://localhost:8000',
    'token': 'YOUR_NETBOX_TOKEN_HERE',  # Same token as Palo Alto sync
    'verify_ssl': False
}

# Site configuration
SITE_NAME = 'Azure-EastUS'
SITE_SLUG = 'azure-eastus'

# ============================================
# NETBOX API CLIENT
# ============================================

class NetBoxAPI:
    """NetBox API client"""
    
    def __init__(self, url, token, verify_ssl=False):
        self.url = url.rstrip('/')
        self.token = token
        self.headers = {
            'Authorization': f'Token {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        self.verify_ssl = verify_ssl
    
    def _request(self, method, endpoint, data=None, params=None):
        """Make API request"""
        url = f"{self.url}/api{endpoint}"
        
        try:
            kwargs = {
                'headers': self.headers,
                'verify': self.verify_ssl,
                'timeout': 30
            }
            
            if params:
                kwargs['params'] = params
            if data:
                kwargs['json'] = data
            
            response = getattr(requests, method.lower())(url, **kwargs)
            response.raise_for_status()
            
            if response.status_code == 204:
                return None
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"❌ NetBox API error: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                print(f"   Response: {e.response.text[:200]}")
            return None
    
    def get_or_create_site(self, name, slug):
        """Get or create site"""
        result = self._request('GET', '/dcim/sites/', params={'slug': slug})
        if result and result.get('count', 0) > 0:
            return result['results'][0]
        
        data = {'name': name, 'slug': slug, 'status': 'active'}
        return self._request('POST', '/dcim/sites/', data)
    
    def get_or_create_manufacturer(self, name, slug):
        """Get or create manufacturer"""
        result = self._request('GET', '/dcim/manufacturers/', params={'slug': slug})
        if result and result.get('count', 0) > 0:
            return result['results'][0]
        
        data = {'name': name, 'slug': slug}
        return self._request('POST', '/dcim/manufacturers/', data)
    
    def get_or_create_device_type(self, model, manufacturer_id, slug):
        """Get or create device type"""
        result = self._request('GET', '/dcim/device-types/', params={'slug': slug})
        if result and result.get('count', 0) > 0:
            return result['results'][0]
        
        data = {
            'model': model,
            'slug': slug,
            'manufacturer': manufacturer_id
        }
        return self._request('POST', '/dcim/device-types/', data)
    
    def get_or_create_device_role(self, name, slug, color='2196f3'):
        """Get or create device role"""
        result = self._request('GET', '/dcim/device-roles/', params={'slug': slug})
        if result and result.get('count', 0) > 0:
            return result['results'][0]
        
        data = {'name': name, 'slug': slug, 'color': color}
        return self._request('POST', '/dcim/device-roles/', data)
    
    def get_or_create_device(self, name, device_type_id, site_id, role_id):
        """Get or create device"""
        result = self._request('GET', '/dcim/devices/', params={'name': name})
        if result and result.get('count', 0) > 0:
            return result['results'][0]
        
        data = {
            'name': name,
            'device_type': device_type_id,
            'site': site_id,
            'role': role_id,
            'status': 'active'
        }
        return self._request('POST', '/dcim/devices/', data)
    
    def update_device_config_context(self, device_id, context_data):
        """Update device config context"""
        data = {'local_context_data': context_data}
        return self._request('PATCH', f'/dcim/devices/{device_id}/', data)
    
    def create_or_update_interface(self, device_id, name, iface_type='virtual', enabled=True):
        """Create or update interface"""
        result = self._request('GET', '/dcim/interfaces/', params={
            'device_id': device_id,
            'name': name
        })
        
        data = {
            'device': device_id,
            'name': name,
            'type': iface_type,
            'enabled': enabled
        }
        
        if result and result.get('count', 0) > 0:
            iface_id = result['results'][0]['id']
            return self._request('PATCH', f'/dcim/interfaces/{iface_id}/', data)
        
        return self._request('POST', '/dcim/interfaces/', data)
    
    def get_or_create_prefix(self, prefix, site_id=None, description=''):
        """Get or create IP prefix"""
        result = self._request('GET', '/ipam/prefixes/', params={'prefix': prefix})
        if result and result.get('count', 0) > 0:
            return result['results'][0]
        
        data = {
            'prefix': prefix,
            'status': 'active',
            'description': description
        }
        if site_id:
            data['site'] = site_id
        
        return self._request('POST', '/ipam/prefixes/', data)
    
    def create_or_update_ip_address(self, address, interface_id=None, description=''):
        """Create or update IP address"""
        result = self._request('GET', '/ipam/ip-addresses/', params={'address': address})
        
        data = {
            'address': address,
            'status': 'active',
            'description': description
        }
        
        if interface_id:
            data['assigned_object_type'] = 'dcim.interface'
            data['assigned_object_id'] = interface_id
        
        if result and result.get('count', 0) > 0:
            ip_id = result['results'][0]['id']
            return self._request('PATCH', f'/ipam/ip-addresses/{ip_id}/', data)
        
        return self._request('POST', '/ipam/ip-addresses/', data)


# ============================================
# AZURE RESOURCE SYNC
# ============================================

def sync_azure_to_netbox():
    """Main sync function"""
    
    print("=" * 60)
    print("  Azure → NetBox Sync")
    print("=" * 60)
    print()
    
    # Initialize Azure clients
    print("🔌 Connecting to Azure...")
    try:
        # Try CLI credentials first (easiest)
        credential = AzureCliCredential()
        print("   Using Azure CLI credentials")
    except Exception:
        # Fall back to DefaultAzureCredential (Managed Identity, Environment Variables, etc.)
        credential = DefaultAzureCredential()
        print("   Using Default Azure credentials")
    
    subscription_id = AZURE_CONFIG['subscription_id']
    resource_group = AZURE_CONFIG['resource_group']
    
    compute_client = ComputeManagementClient(credential, subscription_id)
    network_client = NetworkManagementClient(credential, subscription_id)
    resource_client = ResourceManagementClient(credential, subscription_id)
    
    # Verify resource group exists
    try:
        rg = resource_client.resource_groups.get(resource_group)
        print(f"   ✅ Found resource group: {rg.name} ({rg.location})")
    except Exception as e:
        print(f"   ❌ Resource group not found: {e}")
        return False
    
    # Initialize NetBox
    print("\n🔌 Connecting to NetBox...")
    nb = NetBoxAPI(NETBOX_CONFIG['url'], NETBOX_CONFIG['token'], NETBOX_CONFIG['verify_ssl'])
    
    # Setup NetBox objects
    print("\n📦 Setting up NetBox objects...")
    
    site = nb.get_or_create_site(SITE_NAME, SITE_SLUG)
    if not site:
        print("❌ Failed to create/get site")
        return False
    print(f"  ✅ Site: {site['name']}")
    
    # Create manufacturers for different resource types
    ms_manufacturer = nb.get_or_create_manufacturer('Microsoft', 'microsoft')
    print(f"  ✅ Manufacturer: {ms_manufacturer['name']}")
    
    # Create device role for VMs
    vm_role = nb.get_or_create_device_role('Server', 'server', color='2196f3')
    print(f"  ✅ Role: {vm_role['name']}")
    
    # ============================================
    # SYNC VIRTUAL NETWORKS
    # ============================================
    print("\n🌐 Syncing Virtual Networks...")
    
    vnets = list(network_client.virtual_networks.list(resource_group))
    print(f"  Found {len(vnets)} VNets")
    
    for vnet in vnets:
        print(f"\n  • VNet: {vnet.name}")
        
        # Create prefix for VNet
        for address_prefix in vnet.address_space.address_prefixes:
            print(f"    Address Space: {address_prefix}")
            nb.get_or_create_prefix(
                address_prefix,
                site['id'],
                f"Azure VNet: {vnet.name}"
            )
        
        # Sync subnets
        if vnet.subnets:
            print(f"    Subnets: {len(vnet.subnets)}")
            for subnet in vnet.subnets:
                print(f"      - {subnet.name}: {subnet.address_prefix}")
                nb.get_or_create_prefix(
                    subnet.address_prefix,
                    site['id'],
                    f"Azure Subnet: {subnet.name} (VNet: {vnet.name})"
                )
    
    # ============================================
    # SYNC VIRTUAL MACHINES
    # ============================================
    print("\n💻 Syncing Virtual Machines...")
    
    vms = list(compute_client.virtual_machines.list(resource_group))
    print(f"  Found {len(vms)} VMs")
    
    for vm in vms:
        print(f"\n  • VM: {vm.name}")
        
        # Get VM size and OS info
        vm_size = vm.hardware_profile.vm_size
        os_type = "Unknown"
        
        if vm.storage_profile.image_reference:
            os_type = f"{vm.storage_profile.image_reference.publisher or 'Unknown'}"
            if vm.storage_profile.image_reference.offer:
                os_type += f" {vm.storage_profile.image_reference.offer}"
        elif vm.storage_profile.os_disk:
            os_type = vm.storage_profile.os_disk.os_type or "Unknown"
        
        print(f"    Size: {vm_size}")
        print(f"    OS: {os_type}")
        
        # Create device type for this VM size
        device_type_name = f"Azure-{vm_size}"
        device_type_slug = f"azure-{vm_size.lower()}"
        device_type = nb.get_or_create_device_type(
            device_type_name,
            ms_manufacturer['id'],
            device_type_slug
        )
        
        # Create device in NetBox
        device = nb.get_or_create_device(
            vm.name,
            device_type['id'],
            site['id'],
            vm_role['id']
        )
        
        if not device:
            print(f"    ❌ Failed to create device")
            continue
        
        print(f"    ✅ Device created/updated in NetBox")
        
        # Store VM metadata in config context
        vm_metadata = {
            'azure': {
                'resource_id': vm.id,
                'vm_size': vm_size,
                'os_type': os_type,
                'location': vm.location,
                'provisioning_state': vm.provisioning_state,
                'last_synced': datetime.now().isoformat()
            }
        }
        nb.update_device_config_context(device['id'], vm_metadata)
        
        # Sync network interfaces
        if vm.network_profile and vm.network_profile.network_interfaces:
            print(f"    NICs: {len(vm.network_profile.network_interfaces)}")
            
            for nic_ref in vm.network_profile.network_interfaces:
                nic_id = nic_ref.id
                nic_name = nic_id.split('/')[-1]
                
                # Get full NIC details
                try:
                    nic = network_client.network_interfaces.get(
                        resource_group,
                        nic_name
                    )
                    
                    print(f"      - NIC: {nic.name}")
                    
                    # Create interface in NetBox
                    nb_interface = nb.create_or_update_interface(
                        device['id'],
                        nic.name,
                        'virtual',
                        nic.enable_ip_forwarding or True
                    )
                    
                    # Sync IP configurations
                    if nic.ip_configurations:
                        for ip_config in nic.ip_configurations:
                            # Private IP
                            if ip_config.private_ip_address:
                                private_ip = ip_config.private_ip_address
                                # Determine subnet mask from subnet
                                subnet_id = ip_config.subnet.id if ip_config.subnet else None
                                if subnet_id:
                                    subnet_name = subnet_id.split('/')[-1]
                                    # Try to get subnet CIDR
                                    for vnet in vnets:
                                        for subnet in vnet.subnets:
                                            if subnet.name == subnet_name:
                                                # Extract prefix length
                                                prefix_len = subnet.address_prefix.split('/')[-1]
                                                private_ip_with_mask = f"{private_ip}/{prefix_len}"
                                                break
                                else:
                                    private_ip_with_mask = f"{private_ip}/32"
                                
                                print(f"        Private IP: {private_ip_with_mask}")
                                nb.create_or_update_ip_address(
                                    private_ip_with_mask,
                                    nb_interface['id'] if nb_interface else None,
                                    f"Azure VM: {vm.name}"
                                )
                            
                            # Public IP
                            if ip_config.public_ip_address:
                                try:
                                    public_ip_id = ip_config.public_ip_address.id
                                    public_ip_name = public_ip_id.split('/')[-1]
                                    public_ip_obj = network_client.public_ip_addresses.get(
                                        resource_group,
                                        public_ip_name
                                    )
                                    
                                    if public_ip_obj.ip_address:
                                        print(f"        Public IP: {public_ip_obj.ip_address}")
                                        nb.create_or_update_ip_address(
                                            f"{public_ip_obj.ip_address}/32",
                                            nb_interface['id'] if nb_interface else None,
                                            f"Azure Public IP: {public_ip_name}"
                                        )
                                except Exception as e:
                                    print(f"        ⚠️  Could not get public IP details: {e}")
                
                except Exception as e:
                    print(f"      ⚠️  Could not get NIC details: {e}")
    
    # ============================================
    # SYNC PUBLIC IPs (standalone)
    # ============================================
    print("\n🌍 Syncing Public IP Addresses...")
    
    public_ips = list(network_client.public_ip_addresses.list(resource_group))
    print(f"  Found {len(public_ips)} Public IPs")
    
    for public_ip in public_ips:
        if public_ip.ip_address:
            print(f"  • {public_ip.name}: {public_ip.ip_address}")
            nb.create_or_update_ip_address(
                f"{public_ip.ip_address}/32",
                description=f"Azure Public IP: {public_ip.name}"
            )
    
    # ============================================
    # SUMMARY
    # ============================================
    print("\n" + "=" * 60)
    print("  ✅ Azure Sync Complete!")
    print("=" * 60)
    print()
    print(f"📊 Summary:")
    print(f"  • Virtual Networks: {len(vnets)}")
    print(f"  • Virtual Machines: {len(vms)}")
    print(f"  • Public IPs: {len(public_ips)}")
    print()
    print(f"🌐 View in NetBox: {NETBOX_CONFIG['url']}/dcim/sites/{site['id']}/")
    print()
    
    return True


# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    # Check configuration
    if NETBOX_CONFIG['token'] == 'YOUR_NETBOX_TOKEN_HERE':
        print("❌ Error: Please update NETBOX_CONFIG['token']")
        print("\nUse the same token from the Palo Alto sync script")
        sys.exit(1)
    
    print("Azure to NetBox Sync")
    print(f"Subscription: {AZURE_CONFIG['subscription_id']}")
    print(f"Resource Group: {AZURE_CONFIG['resource_group']}")
    print(f"NetBox: {NETBOX_CONFIG['url']}")
    print()
    
    # Check Azure authentication
    print("Checking Azure authentication...")
    try:
        from azure.identity import AzureCliCredential
        credential = AzureCliCredential()
        # Test the credential
        from azure.mgmt.resource import ResourceManagementClient
        client = ResourceManagementClient(credential, AZURE_CONFIG['subscription_id'])
        list(client.resource_groups.list())
        print("✅ Azure authentication successful\n")
    except Exception as e:
        print(f"❌ Azure authentication failed: {e}")
        print("\nPlease run: az login")
        sys.exit(1)
    
    # Run sync
    try:
        success = sync_azure_to_netbox()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Sync interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
