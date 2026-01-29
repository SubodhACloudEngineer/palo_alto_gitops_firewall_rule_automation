#!/usr/bin/env python3
"""
Palo Alto to NetBox Sync Script
================================

Syncs firewall configuration from Palo Alto NGFW to NetBox:
- Network interfaces
- IP addresses
- Address objects
- Security zones
- Security rules

Author: Network Automation Team
Version: 1.0
"""

import requests
import xml.etree.ElementTree as ET
import json
import sys
from datetime import datetime
from urllib3.exceptions import InsecureRequestWarning

# Disable SSL warnings for self-signed certificates
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# ============================================
# CONFIGURATION
# ============================================

# Palo Alto Configuration
PA_CONFIG = {
    'host': '40.76.129.220',
    'api_key': 'LUFRPT03ZVlPQ1o5UmQ5NFdvOFNqNGdZMXlTQk11WkU9UU5HYzJRWkNVUzBIVndaRVpDNjhSQzBTR0NaVCtCdDlySDNoMlVGV2dGVWFnQ24xanN0ZjJOeXZyUmtGQjlKag==',  # Update this!
    'verify_ssl': False
}

# NetBox Configuration
NETBOX_CONFIG = {
    'url': 'http://localhost:8000',  # Your NetBox URL
    'token': 'cb8da4ed137116561635c752a5c685753c246cae',  # Create in NetBox: Admin → API Tokens
    'verify_ssl': False
}

# Resource mappings
DEVICE_NAME = 'fw1toyota123'  # Palo Alto device name in NetBox
SITE_NAME = 'Azure-EastUS'     # Site name in NetBox
MANUFACTURER = 'Palo Alto Networks'
DEVICE_TYPE = 'PA-VM-Series'

# ============================================
# PALO ALTO API FUNCTIONS
# ============================================

class PaloAltoAPI:
    """Interface to Palo Alto NGFW API"""
    
    def __init__(self, host, api_key, verify_ssl=False):
        self.host = host
        self.api_key = api_key
        self.base_url = f"https://{host}/api/"
        self.verify_ssl = verify_ssl
    
    def _make_request(self, params):
        """Make API request to Palo Alto"""
        params['key'] = self.api_key
        
        try:
            response = requests.get(
                self.base_url,
                params=params,
                verify=self.verify_ssl,
                timeout=30
            )
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"❌ API request failed: {e}")
            return None
    
    def get_interfaces(self):
        """Get all network interfaces"""
        params = {
            'type': 'config',
            'action': 'get',
            'xpath': "/config/devices/entry[@name='localhost.localdomain']/network/interface"
        }
        
        response = self._make_request(params)
        if not response:
            return []
        
        try:
            root = ET.fromstring(response)
            interfaces = []
            
            # Parse ethernet interfaces
            for iface in root.findall('.//ethernet/entry'):
                name = iface.get('name')
                
                # Get IP address
                ip_elem = iface.find('.//layer3/ip/entry')
                ip_address = ip_elem.get('name') if ip_elem is not None else None
                
                # Get zone
                zone_elem = iface.find('.//layer3/zone')
                zone = zone_elem.text if zone_elem is not None else None
                
                if name:
                    interfaces.append({
                        'name': name,
                        'ip_address': ip_address,
                        'zone': zone,
                        'type': 'virtual'
                    })
            
            return interfaces
            
        except ET.ParseError as e:
            print(f"❌ Failed to parse interfaces: {e}")
            return []
    
    def get_address_objects(self):
        """Get all address objects"""
        params = {
            'type': 'config',
            'action': 'get',
            'xpath': "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/address"
        }
        
        response = self._make_request(params)
        if not response:
            return []
        
        try:
            root = ET.fromstring(response)
            addresses = []
            
            for addr in root.findall('.//entry'):
                name = addr.get('name')
                
                # Get IP/network
                ip_elem = addr.find('ip-netmask')
                ip_netmask = ip_elem.text if ip_elem is not None else None
                
                # Get description
                desc_elem = addr.find('description')
                description = desc_elem.text if desc_elem is not None else ''
                
                if name and ip_netmask:
                    addresses.append({
                        'name': name,
                        'ip_netmask': ip_netmask,
                        'description': description
                    })
            
            return addresses
            
        except ET.ParseError as e:
            print(f"❌ Failed to parse address objects: {e}")
            return []
    
    def get_security_rules(self):
        """Get all security rules"""
        params = {
            'type': 'config',
            'action': 'get',
            'xpath': "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/rulebase/security/rules"
        }
        
        response = self._make_request(params)
        if not response:
            return []
        
        try:
            root = ET.fromstring(response)
            rules = []
            
            for rule in root.findall('.//entry'):
                name = rule.get('name')
                
                # Extract rule details
                from_zone = [m.text for m in rule.findall('.//from/member')]
                to_zone = [m.text for m in rule.findall('.//to/member')]
                source = [m.text for m in rule.findall('.//source/member')]
                destination = [m.text for m in rule.findall('.//destination/member')]
                application = [m.text for m in rule.findall('.//application/member')]
                service = [m.text for m in rule.findall('.//service/member')]
                action_elem = rule.find('.//action')
                action = action_elem.text if action_elem is not None else 'allow'
                
                desc_elem = rule.find('.//description')
                description = desc_elem.text if desc_elem is not None else ''
                
                if name:
                    rules.append({
                        'name': name,
                        'from_zone': from_zone,
                        'to_zone': to_zone,
                        'source': source,
                        'destination': destination,
                        'application': application,
                        'service': service,
                        'action': action,
                        'description': description
                    })
            
            return rules
            
        except ET.ParseError as e:
            print(f"❌ Failed to parse security rules: {e}")
            return []
    
    def get_zones(self):
        """Get all security zones"""
        params = {
            'type': 'config',
            'action': 'get',
            'xpath': "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/zone"
        }
        
        response = self._make_request(params)
        if not response:
            return []
        
        try:
            root = ET.fromstring(response)
            zones = []
            
            for zone in root.findall('.//entry'):
                name = zone.get('name')
                interfaces = [m.text for m in zone.findall('.//network/layer3/member')]
                
                if name:
                    zones.append({
                        'name': name,
                        'interfaces': interfaces
                    })
            
            return zones
            
        except ET.ParseError as e:
            print(f"❌ Failed to parse zones: {e}")
            return []


# ============================================
# NETBOX API FUNCTIONS
# ============================================

class NetBoxAPI:
    """Interface to NetBox API"""
    
    def __init__(self, url, token, verify_ssl=False):
        self.url = url.rstrip('/')
        self.token = token
        self.headers = {
            'Authorization': f'Token {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        self.verify_ssl = verify_ssl
    
    def _make_request(self, method, endpoint, data=None):
        """Make API request to NetBox"""
        url = f"{self.url}/api{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=self.headers, verify=self.verify_ssl)
            elif method == 'POST':
                response = requests.post(url, headers=self.headers, json=data, verify=self.verify_ssl)
            elif method == 'PATCH':
                response = requests.patch(url, headers=self.headers, json=data, verify=self.verify_ssl)
            elif method == 'PUT':
                response = requests.put(url, headers=self.headers, json=data, verify=self.verify_ssl)
            elif method == 'DELETE':
                response = requests.delete(url, headers=self.headers, verify=self.verify_ssl)
            
            response.raise_for_status()
            
            if response.status_code == 204:  # No content
                return None
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"❌ NetBox API error ({method} {endpoint}): {e}")
            if hasattr(e.response, 'text'):
                print(f"   Response: {e.response.text}")
            return None
    
    def get_or_create_site(self, name, slug=None):
        """Get or create a site"""
        if not slug:
            slug = name.lower().replace(' ', '-').replace('_', '-')
        
        # Check if exists
        result = self._make_request('GET', f'/dcim/sites/?slug={slug}')
        if result and result.get('count', 0) > 0:
            return result['results'][0]
        
        # Create
        data = {'name': name, 'slug': slug}
        return self._make_request('POST', '/dcim/sites/', data)
    
    def get_or_create_manufacturer(self, name, slug=None):
        """Get or create a manufacturer"""
        if not slug:
            slug = name.lower().replace(' ', '-')
        
        result = self._make_request('GET', f'/dcim/manufacturers/?slug={slug}')
        if result and result.get('count', 0) > 0:
            return result['results'][0]
        
        data = {'name': name, 'slug': slug}
        return self._make_request('POST', '/dcim/manufacturers/', data)
    
    def get_or_create_device_type(self, model, manufacturer_id, slug=None):
        """Get or create a device type"""
        if not slug:
            slug = model.lower().replace(' ', '-')
        
        result = self._make_request('GET', f'/dcim/device-types/?slug={slug}')
        if result and result.get('count', 0) > 0:
            return result['results'][0]
        
        data = {
            'model': model,
            'slug': slug,
            'manufacturer': manufacturer_id
        }
        return self._make_request('POST', '/dcim/device-types/', data)
    
    def get_or_create_device_role(self, name, slug=None, color='ff5722'):
        """Get or create a device role"""
        if not slug:
            slug = name.lower().replace(' ', '-')
        
        result = self._make_request('GET', f'/dcim/device-roles/?slug={slug}')
        if result and result.get('count', 0) > 0:
            return result['results'][0]
        
        data = {'name': name, 'slug': slug, 'color': color}
        return self._make_request('POST', '/dcim/device-roles/', data)
    
    def get_or_create_device(self, name, device_type_id, site_id, role_id):
        """Get or create a device"""
        result = self._make_request('GET', f'/dcim/devices/?name={name}')
        if result and result.get('count', 0) > 0:
            return result['results'][0]
        
        data = {
            'name': name,
            'device_type': device_type_id,
            'site': site_id,
            'role': role_id,
            'status': 'active'
        }
        return self._make_request('POST', '/dcim/devices/', data)
    
    def create_or_update_interface(self, device_id, name, iface_type='virtual'):
        """Create or update an interface"""
        # Check if exists
        result = self._make_request('GET', f'/dcim/interfaces/?device_id={device_id}&name={name}')
        
        data = {
            'device': device_id,
            'name': name,
            'type': iface_type,
            'enabled': True
        }
        
        if result and result.get('count', 0) > 0:
            # Update
            iface_id = result['results'][0]['id']
            return self._make_request('PATCH', f'/dcim/interfaces/{iface_id}/', data)
        else:
            # Create
            return self._make_request('POST', '/dcim/interfaces/', data)
    
    def create_or_update_ip_address(self, address, interface_id=None, description=''):
        """Create or update an IP address"""
        # Check if exists
        result = self._make_request('GET', f'/ipam/ip-addresses/?address={address}')
        
        data = {
            'address': address,
            'status': 'active',
            'description': description
        }
        
        if interface_id:
            data['assigned_object_type'] = 'dcim.interface'
            data['assigned_object_id'] = interface_id
        
        if result and result.get('count', 0) > 0:
            # Update
            ip_id = result['results'][0]['id']
            return self._make_request('PATCH', f'/ipam/ip-addresses/{ip_id}/', data)
        else:
            # Create
            return self._make_request('POST', '/ipam/ip-addresses/', data)
    
    def store_firewall_rules(self, device_id, rules):
        """Store firewall rules in device config context"""
        data = {
            'local_context_data': {
                'firewall_rules': rules,
                'last_sync': datetime.now().isoformat()
            }
        }
        
        return self._make_request('PATCH', f'/dcim/devices/{device_id}/', data)


# ============================================
# SYNC FUNCTIONS
# ============================================

def sync_palo_alto_to_netbox():
    """Main sync function"""
    
    print("=" * 60)
    print("  Palo Alto → NetBox Sync")
    print("=" * 60)
    print()
    
    # Initialize APIs
    print("🔌 Connecting to Palo Alto NGFW...")
    pa = PaloAltoAPI(PA_CONFIG['host'], PA_CONFIG['api_key'], PA_CONFIG['verify_ssl'])
    
    print("🔌 Connecting to NetBox...")
    nb = NetBoxAPI(NETBOX_CONFIG['url'], NETBOX_CONFIG['token'], NETBOX_CONFIG['verify_ssl'])
    
    # Create/get NetBox objects
    print("\n📦 Setting up NetBox objects...")
    
    site = nb.get_or_create_site(SITE_NAME)
    if not site:
        print("❌ Failed to create/get site")
        return False
    print(f"  ✅ Site: {site['name']}")
    
    manufacturer = nb.get_or_create_manufacturer(MANUFACTURER)
    if not manufacturer:
        print("❌ Failed to create/get manufacturer")
        return False
    print(f"  ✅ Manufacturer: {manufacturer['name']}")
    
    device_type = nb.get_or_create_device_type(DEVICE_TYPE, manufacturer['id'])
    if not device_type:
        print("❌ Failed to create/get device type")
        return False
    print(f"  ✅ Device Type: {device_type['model']}")
    
    role = nb.get_or_create_device_role('Firewall', color='ff5722')
    if not role:
        print("❌ Failed to create/get role")
        return False
    print(f"  ✅ Role: {role['name']}")
    
    device = nb.get_or_create_device(DEVICE_NAME, device_type['id'], site['id'], role['id'])
    if not device:
        print("❌ Failed to create/get device")
        return False
    print(f"  ✅ Device: {device['name']}")
    
    # Sync interfaces
    print("\n🔌 Syncing interfaces...")
    interfaces = pa.get_interfaces()
    print(f"  Found {len(interfaces)} interfaces")
    
    for iface in interfaces:
        print(f"  • {iface['name']}: {iface.get('ip_address', 'no IP')} (zone: {iface.get('zone', 'none')})")
        
        # Create interface in NetBox
        nb_iface = nb.create_or_update_interface(device['id'], iface['name'], 'virtual')
        
        # Create IP address if exists
        if iface.get('ip_address'):
            nb.create_or_update_ip_address(
                iface['ip_address'],
                nb_iface['id'] if nb_iface else None,
                f"Zone: {iface.get('zone', 'unknown')}"
            )
    
    # Sync address objects
    print("\n📍 Syncing address objects...")
    addresses = pa.get_address_objects()
    print(f"  Found {len(addresses)} address objects")
    
    for addr in addresses:
        print(f"  • {addr['name']}: {addr['ip_netmask']}")
        nb.create_or_update_ip_address(
            addr['ip_netmask'],
            description=f"{addr['name']}: {addr.get('description', '')}"
        )
    
    # Sync security rules
    print("\n🔐 Syncing security rules...")
    rules = pa.get_security_rules()
    print(f"  Found {len(rules)} security rules")
    
    for rule in rules:
        print(f"  • {rule['name']}: {rule['from_zone']} → {rule['to_zone']} ({rule['action']})")
    
    # Store rules in device config context
    nb.store_firewall_rules(device['id'], rules)
    
    # Sync zones
    print("\n🏷️  Syncing zones...")
    zones = pa.get_zones()
    print(f"  Found {len(zones)} zones")
    
    for zone in zones:
        print(f"  • {zone['name']}: {', '.join(zone['interfaces'])}")
    
    print("\n" + "=" * 60)
    print("  ✅ Sync Complete!")
    print("=" * 60)
    print()
    print(f"📊 Summary:")
    print(f"  • Interfaces: {len(interfaces)}")
    print(f"  • Address Objects: {len(addresses)}")
    print(f"  • Security Rules: {len(rules)}")
    print(f"  • Zones: {len(zones)}")
    print()
    print(f"🌐 View in NetBox: {NETBOX_CONFIG['url']}/dcim/devices/{device['id']}/")
    print()
    
    return True


# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    # Check configuration
    if PA_CONFIG['api_key'] == 'YOUR_API_KEY_HERE':
        print("❌ Error: Please update PA_CONFIG['api_key'] with your Palo Alto API key")
        sys.exit(1)
    
    if NETBOX_CONFIG['token'] == 'YOUR_NETBOX_TOKEN_HERE':
        print("❌ Error: Please update NETBOX_CONFIG['token'] with your NetBox API token")
        print("\nTo create a NetBox token:")
        print("1. Login to NetBox")
        print("2. Click your username → API Tokens")
        print("3. Click 'Add a token'")
        print("4. Copy the token and paste it in this script")
        sys.exit(1)
    
    # Run sync
    try:
        success = sync_palo_alto_to_netbox()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Sync interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
