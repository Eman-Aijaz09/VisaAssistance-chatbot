# ---------------- Key Vault (secrets) ----------------
resource "azurerm_key_vault" "kv" {
  name                       = "kv-visa-${random_string.suffix.result}"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  soft_delete_retention_days = 7
  purge_protection_enabled   = false
}

resource "azurerm_key_vault_access_policy" "deployer" {
  key_vault_id       = azurerm_key_vault.kv.id
  tenant_id          = data.azurerm_client_config.current.tenant_id
  object_id          = data.azurerm_client_config.current.object_id
  secret_permissions = ["Get", "List", "Set", "Delete", "Purge", "Recover"]
}

resource "azurerm_key_vault_secret" "db" {
  name         = "supabase-db-url"
  value        = var.supabase_db_url
  key_vault_id = azurerm_key_vault.kv.id
  depends_on   = [azurerm_key_vault_access_policy.deployer]
}

resource "azurerm_key_vault_secret" "groq" {
  name         = "groq-api-key"
  value        = var.groq_api_key
  key_vault_id = azurerm_key_vault.kv.id
  depends_on   = [azurerm_key_vault_access_policy.deployer]
}

# ---------------- Web tier scale set (nginx + frontend) ----------------
resource "azurerm_linux_virtual_machine_scale_set" "web" {
  name                            = "vmss-web"
  location                        = azurerm_resource_group.rg.location
  resource_group_name             = azurerm_resource_group.rg.name
  sku                             = var.web_vm_size
  instances                       = 1
  admin_username                  = "azureuser"
  admin_password                  = random_password.vm_admin.result
  disable_password_authentication = false
  upgrade_mode                    = "Manual"
  custom_data = base64encode(templatefile("${path.module}/web-init.sh.tpl", {
    ghcr_owner     = var.ghcr_owner
    internal_lb_ip = var.internal_lb_ip
  }))

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  os_disk {
    storage_account_type = "StandardSSD_LRS"
    caching              = "ReadWrite"
  }

  network_interface {
    name    = "nic-web"
    primary = true
    ip_configuration {
      name                                   = "internal"
      primary                                = true
      subnet_id                              = azurerm_subnet.web.id
      load_balancer_backend_address_pool_ids = [azurerm_lb_backend_address_pool.web.id]
    }
  }

  depends_on = [azurerm_subnet_nat_gateway_association.web]
}

# ---------------- App tier scale set (FastAPI) ----------------
resource "azurerm_linux_virtual_machine_scale_set" "app" {
  name                            = "vmss-app"
  location                        = azurerm_resource_group.rg.location
  resource_group_name             = azurerm_resource_group.rg.name
  sku                             = var.app_vm_size
  instances                       = 1
  admin_username                  = "azureuser"
  admin_password                  = random_password.vm_admin.result
  disable_password_authentication = false
  upgrade_mode                    = "Manual"
  custom_data = base64encode(templatefile("${path.module}/app-init.sh.tpl", {
    ghcr_owner = var.ghcr_owner
    vault_uri  = azurerm_key_vault.kv.vault_uri
  }))

  identity {
    type = "SystemAssigned"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  os_disk {
    storage_account_type = "StandardSSD_LRS"
    caching              = "ReadWrite"
    disk_size_gb         = 64
  }

  network_interface {
    name    = "nic-app"
    primary = true
    ip_configuration {
      name                                   = "internal"
      primary                                = true
      subnet_id                              = azurerm_subnet.app.id
      load_balancer_backend_address_pool_ids = [azurerm_lb_backend_address_pool.app.id]
    }
  }

  lifecycle {
    ignore_changes = [instances]
  }

  depends_on = [azurerm_subnet_nat_gateway_association.app]
}

# Let the app VMs read secrets with their managed identity (no passwords on disk)
resource "azurerm_key_vault_access_policy" "app_vmss" {
  key_vault_id       = azurerm_key_vault.kv.id
  tenant_id          = data.azurerm_client_config.current.tenant_id
  object_id          = azurerm_linux_virtual_machine_scale_set.app.identity[0].principal_id
  secret_permissions = ["Get"]
}

# ---------------- Autoscale (app tier: 1 to 2, limited by 6 vCPU quota) ----------------
resource "azurerm_monitor_autoscale_setting" "app" {
  name                = "autoscale-app"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  target_resource_id  = azurerm_linux_virtual_machine_scale_set.app.id

  profile {
    name = "cpu-based"
    capacity {
      default = 1
      minimum = 1
      maximum = 2
    }
    rule {
      metric_trigger {
        metric_name        = "Percentage CPU"
        metric_resource_id = azurerm_linux_virtual_machine_scale_set.app.id
        time_grain         = "PT1M"
        statistic          = "Average"
        time_window        = "PT5M"
        time_aggregation   = "Average"
        operator           = "GreaterThan"
        threshold          = 70
      }
      scale_action {
        direction = "Increase"
        type      = "ChangeCount"
        value     = "1"
        cooldown  = "PT5M"
      }
    }
    rule {
      metric_trigger {
        metric_name        = "Percentage CPU"
        metric_resource_id = azurerm_linux_virtual_machine_scale_set.app.id
        time_grain         = "PT1M"
        statistic          = "Average"
        time_window        = "PT10M"
        time_aggregation   = "Average"
        operator           = "LessThan"
        threshold          = 30
      }
      scale_action {
        direction = "Decrease"
        type      = "ChangeCount"
        value     = "1"
        cooldown  = "PT10M"
      }
    }
  }
}
