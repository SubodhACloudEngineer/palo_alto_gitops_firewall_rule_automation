# ============================================
# AZURE VM DEPLOYMENT
# GitOps-driven Infrastructure Provisioning
# ============================================

locals {
  # Common tags for all resources
  common_tags = merge(var.tags, {
    Environment  = var.environment
    ManagedBy    = "Terraform"
    DeploymentId = var.deployment_name
    RequestId    = var.request_id
    Requester    = var.requester
    CreatedAt    = timestamp()
  })

  # Determine if Windows or Linux
  is_windows = can(regex("windows", var.os_type))

  # OS image references
  os_images = {
    ubuntu_22_04 = {
      publisher = "Canonical"
      offer     = "0001-com-ubuntu-server-jammy"
      sku       = "22_04-lts-gen2"
      version   = "latest"
    }
    ubuntu_20_04 = {
      publisher = "Canonical"
      offer     = "0001-com-ubuntu-server-focal"
      sku       = "20_04-lts-gen2"
      version   = "latest"
    }
    windows_server_2022 = {
      publisher = "MicrosoftWindowsServer"
      offer     = "WindowsServer"
      sku       = "2022-datacenter-g2"
      version   = "latest"
    }
    windows_server_2019 = {
      publisher = "MicrosoftWindowsServer"
      offer     = "WindowsServer"
      sku       = "2019-datacenter-g2"
      version   = "latest"
    }
    rhel_9 = {
      publisher = "RedHat"
      offer     = "RHEL"
      sku       = "9-lvm-gen2"
      version   = "latest"
    }
    rhel_8 = {
      publisher = "RedHat"
      offer     = "RHEL"
      sku       = "8-lvm-gen2"
      version   = "latest"
    }
  }

  # Parse custom ports
  custom_port_list = var.custom_ports != "" ? [for p in split(",", var.custom_ports) : trimspace(p)] : []
}

# ============================================
# RESOURCE GROUP
# ============================================

resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.common_tags
}

# ============================================
# VIRTUAL NETWORK
# ============================================

resource "azurerm_virtual_network" "main" {
  name                = "${var.deployment_name}-vnet"
  address_space       = [var.vnet_address_space]
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.common_tags
}

resource "azurerm_subnet" "main" {
  name                 = "${var.deployment_name}-subnet"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [var.subnet_address_prefix]
}

# ============================================
# NETWORK SECURITY GROUP
# ============================================

resource "azurerm_network_security_group" "main" {
  name                = "${var.deployment_name}-nsg"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.common_tags
}

# SSH Rule
resource "azurerm_network_security_rule" "ssh" {
  count                       = contains(var.nsg_rules, "ssh") ? 1 : 0
  name                        = "Allow-SSH"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "22"
  source_address_prefixes     = var.allowed_source_ips
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.main.name
}

# RDP Rule
resource "azurerm_network_security_rule" "rdp" {
  count                       = contains(var.nsg_rules, "rdp") ? 1 : 0
  name                        = "Allow-RDP"
  priority                    = 110
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "3389"
  source_address_prefixes     = var.allowed_source_ips
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.main.name
}

# HTTP Rule
resource "azurerm_network_security_rule" "http" {
  count                       = contains(var.nsg_rules, "http") ? 1 : 0
  name                        = "Allow-HTTP"
  priority                    = 120
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "80"
  source_address_prefixes     = var.allowed_source_ips
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.main.name
}

# HTTPS Rule
resource "azurerm_network_security_rule" "https" {
  count                       = contains(var.nsg_rules, "https") ? 1 : 0
  name                        = "Allow-HTTPS"
  priority                    = 130
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "443"
  source_address_prefixes     = var.allowed_source_ips
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.main.name
}

# Custom Port Rules
resource "azurerm_network_security_rule" "custom" {
  count                       = length(local.custom_port_list)
  name                        = "Allow-Custom-${local.custom_port_list[count.index]}"
  priority                    = 200 + count.index
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = local.custom_port_list[count.index]
  source_address_prefixes     = var.allowed_source_ips
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.main.name
}

# Associate NSG with Subnet
resource "azurerm_subnet_network_security_group_association" "main" {
  subnet_id                 = azurerm_subnet.main.id
  network_security_group_id = azurerm_network_security_group.main.id
}

# ============================================
# SSH KEY (for Linux VMs)
# ============================================

resource "tls_private_key" "ssh" {
  count     = var.generate_ssh_key && !local.is_windows ? 1 : 0
  algorithm = "RSA"
  rsa_bits  = 4096
}

# ============================================
# PUBLIC IP ADDRESSES
# ============================================

resource "azurerm_public_ip" "main" {
  count               = var.create_public_ip ? var.vm_count : 0
  name                = "${var.vm_name_prefix}-${format("%02d", count.index + 1)}-pip"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = local.common_tags
}

# ============================================
# NETWORK INTERFACES
# ============================================

resource "azurerm_network_interface" "main" {
  count               = var.vm_count
  name                = "${var.vm_name_prefix}-${format("%02d", count.index + 1)}-nic"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.common_tags

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.main.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = var.create_public_ip ? azurerm_public_ip.main[count.index].id : null
  }
}

# ============================================
# LINUX VIRTUAL MACHINES
# ============================================

resource "azurerm_linux_virtual_machine" "main" {
  count               = !local.is_windows ? var.vm_count : 0
  name                = "${var.vm_name_prefix}-${format("%02d", count.index + 1)}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  size                = var.vm_size
  admin_username      = var.admin_username
  tags                = local.common_tags

  network_interface_ids = [azurerm_network_interface.main[count.index].id]

  admin_ssh_key {
    username   = var.admin_username
    public_key = var.generate_ssh_key ? tls_private_key.ssh[0].public_key_openssh : file("~/.ssh/id_rsa.pub")
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
    name                 = "${var.vm_name_prefix}-${format("%02d", count.index + 1)}-osdisk"
  }

  source_image_reference {
    publisher = local.os_images[var.os_type].publisher
    offer     = local.os_images[var.os_type].offer
    sku       = local.os_images[var.os_type].sku
    version   = local.os_images[var.os_type].version
  }

  identity {
    type = "SystemAssigned"
  }
}

# ============================================
# WINDOWS VIRTUAL MACHINES
# ============================================

resource "random_password" "windows" {
  count   = local.is_windows && var.admin_password == "" ? 1 : 0
  length  = 16
  special = true
}

resource "azurerm_windows_virtual_machine" "main" {
  count               = local.is_windows ? var.vm_count : 0
  name                = "${var.vm_name_prefix}-${format("%02d", count.index + 1)}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  size                = var.vm_size
  admin_username      = var.admin_username
  admin_password      = var.admin_password != "" ? var.admin_password : random_password.windows[0].result
  tags                = local.common_tags

  network_interface_ids = [azurerm_network_interface.main[count.index].id]

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
    name                 = "${var.vm_name_prefix}-${format("%02d", count.index + 1)}-osdisk"
  }

  source_image_reference {
    publisher = local.os_images[var.os_type].publisher
    offer     = local.os_images[var.os_type].offer
    sku       = local.os_images[var.os_type].sku
    version   = local.os_images[var.os_type].version
  }

  identity {
    type = "SystemAssigned"
  }
}
