# ============================================
# DEPLOYMENT OUTPUTS
# ============================================

output "deployment_name" {
  description = "Name of the deployment"
  value       = var.deployment_name
}

output "resource_group_name" {
  description = "Name of the Resource Group"
  value       = azurerm_resource_group.main.name
}

output "resource_group_id" {
  description = "ID of the Resource Group"
  value       = azurerm_resource_group.main.id
}

# ============================================
# NETWORK OUTPUTS
# ============================================

output "vnet_name" {
  description = "Name of the Virtual Network"
  value       = azurerm_virtual_network.main.name
}

output "vnet_id" {
  description = "ID of the Virtual Network"
  value       = azurerm_virtual_network.main.id
}

output "subnet_name" {
  description = "Name of the Subnet"
  value       = azurerm_subnet.main.name
}

output "subnet_id" {
  description = "ID of the Subnet"
  value       = azurerm_subnet.main.id
}

output "nsg_name" {
  description = "Name of the Network Security Group"
  value       = azurerm_network_security_group.main.name
}

output "nsg_id" {
  description = "ID of the Network Security Group"
  value       = azurerm_network_security_group.main.id
}

# ============================================
# VM OUTPUTS
# ============================================

output "vm_names" {
  description = "Names of the Virtual Machines"
  value       = local.is_windows ? azurerm_windows_virtual_machine.main[*].name : azurerm_linux_virtual_machine.main[*].name
}

output "vm_ids" {
  description = "IDs of the Virtual Machines"
  value       = local.is_windows ? azurerm_windows_virtual_machine.main[*].id : azurerm_linux_virtual_machine.main[*].id
}

output "private_ip_addresses" {
  description = "Private IP addresses of the VMs"
  value       = azurerm_network_interface.main[*].private_ip_address
}

output "public_ip_addresses" {
  description = "Public IP addresses of the VMs (if created)"
  value       = var.create_public_ip ? azurerm_public_ip.main[*].ip_address : []
}

# ============================================
# SSH KEY OUTPUT (Linux only)
# ============================================

output "ssh_private_key" {
  description = "SSH private key for Linux VMs (sensitive)"
  value       = var.generate_ssh_key && !local.is_windows ? tls_private_key.ssh[0].private_key_pem : null
  sensitive   = true
}

output "ssh_public_key" {
  description = "SSH public key for Linux VMs"
  value       = var.generate_ssh_key && !local.is_windows ? tls_private_key.ssh[0].public_key_openssh : null
}

# ============================================
# WINDOWS PASSWORD OUTPUT
# ============================================

output "windows_admin_password" {
  description = "Windows admin password (if auto-generated)"
  value       = local.is_windows && var.admin_password == "" ? random_password.windows[0].result : null
  sensitive   = true
}

# ============================================
# CONNECTION INFO
# ============================================

output "connection_info" {
  description = "Connection information for the VMs"
  value = {
    os_type        = var.os_type
    admin_username = var.admin_username
    vm_count       = var.vm_count
    public_ips     = var.create_public_ip ? azurerm_public_ip.main[*].ip_address : []
    private_ips    = azurerm_network_interface.main[*].private_ip_address
    ssh_command    = !local.is_windows && var.create_public_ip && length(azurerm_public_ip.main) > 0 ? "ssh ${var.admin_username}@${azurerm_public_ip.main[0].ip_address}" : null
    rdp_info       = local.is_windows && var.create_public_ip && length(azurerm_public_ip.main) > 0 ? "RDP to ${azurerm_public_ip.main[0].ip_address}" : null
  }
}

# ============================================
# SUMMARY OUTPUT
# ============================================

output "deployment_summary" {
  description = "Summary of the deployment"
  value = <<-EOT
    ============================================
    DEPLOYMENT SUMMARY
    ============================================
    Deployment Name:    ${var.deployment_name}
    Resource Group:     ${azurerm_resource_group.main.name}
    Location:           ${var.location}
    Environment:        ${var.environment}

    NETWORK:
    - VNet:             ${azurerm_virtual_network.main.name} (${var.vnet_address_space})
    - Subnet:           ${azurerm_subnet.main.name} (${var.subnet_address_prefix})
    - NSG:              ${azurerm_network_security_group.main.name}

    VMs:
    - Count:            ${var.vm_count}
    - Size:             ${var.vm_size}
    - OS:               ${var.os_type}
    - Admin User:       ${var.admin_username}

    Request ID:         ${var.request_id}
    Requester:          ${var.requester}
    ============================================
  EOT
}
