# ============================================
# DEPLOYMENT VARIABLES
# ============================================

variable "deployment_name" {
  description = "Unique name for this deployment"
  type        = string
}

variable "resource_group_name" {
  description = "Name of the Azure Resource Group"
  type        = string
}

variable "location" {
  description = "Azure region for resources"
  type        = string
  default     = "eastus"
}

variable "environment" {
  description = "Environment tag (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# ============================================
# VM VARIABLES
# ============================================

variable "vm_count" {
  description = "Number of VMs to create"
  type        = number
  default     = 1
}

variable "vm_name_prefix" {
  description = "Prefix for VM names"
  type        = string
}

variable "vm_size" {
  description = "Azure VM size"
  type        = string
  default     = "Standard_B2s"
}

variable "os_type" {
  description = "Operating system type"
  type        = string
  default     = "ubuntu_22_04"

  validation {
    condition = contains([
      "ubuntu_22_04", "ubuntu_20_04",
      "windows_server_2022", "windows_server_2019",
      "rhel_9", "rhel_8"
    ], var.os_type)
    error_message = "Invalid OS type specified."
  }
}

variable "admin_username" {
  description = "Administrator username"
  type        = string
  default     = "azureadmin"
}

variable "admin_password" {
  description = "Administrator password (for Windows VMs)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "generate_ssh_key" {
  description = "Generate SSH key for Linux VMs"
  type        = bool
  default     = true
}

# ============================================
# NETWORK VARIABLES
# ============================================

variable "vnet_address_space" {
  description = "Address space for the Virtual Network"
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_address_prefix" {
  description = "Address prefix for the Subnet"
  type        = string
  default     = "10.0.1.0/24"
}

variable "create_public_ip" {
  description = "Create public IP addresses for VMs"
  type        = bool
  default     = true
}

# ============================================
# NSG VARIABLES
# ============================================

variable "nsg_rules" {
  description = "List of NSG rules to create (ssh, rdp, http, https)"
  type        = list(string)
  default     = []
}

variable "custom_ports" {
  description = "Comma-separated list of custom ports to open"
  type        = string
  default     = ""
}

variable "allowed_source_ips" {
  description = "Source IP addresses allowed to access VMs"
  type        = list(string)
  default     = ["*"]
}

# ============================================
# METADATA VARIABLES
# ============================================

variable "request_id" {
  description = "Service request ID"
  type        = string
  default     = ""
}

variable "requester" {
  description = "Person who requested the deployment"
  type        = string
  default     = ""
}

variable "description" {
  description = "Business justification for the deployment"
  type        = string
  default     = ""
}
