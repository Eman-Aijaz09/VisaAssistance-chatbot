# ---------------- Public load balancer -> web tier ----------------
resource "azurerm_public_ip" "lb" {
  name                = "pip-lb-visa"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  allocation_method   = "Static"
  sku                 = "Standard"
}

resource "azurerm_lb" "public" {
  name                = "lb-public-visa"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "Standard"

  frontend_ip_configuration {
    name                 = "public-frontend"
    public_ip_address_id = azurerm_public_ip.lb.id
  }
}

resource "azurerm_lb_backend_address_pool" "web" {
  name            = "pool-web"
  loadbalancer_id = azurerm_lb.public.id
}

resource "azurerm_lb_probe" "web" {
  name            = "probe-web-80"
  loadbalancer_id = azurerm_lb.public.id
  protocol        = "Tcp"
  port            = 80
}

resource "azurerm_lb_rule" "web" {
  name                           = "rule-http"
  loadbalancer_id                = azurerm_lb.public.id
  protocol                       = "Tcp"
  frontend_port                  = 80
  backend_port                   = 80
  frontend_ip_configuration_name = "public-frontend"
  backend_address_pool_ids       = [azurerm_lb_backend_address_pool.web.id]
  probe_id                       = azurerm_lb_probe.web.id
}

# ---------------- Internal load balancer -> app tier ----------------
resource "azurerm_lb" "internal" {
  name                = "lb-internal-visa"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "Standard"

  frontend_ip_configuration {
    name                          = "internal-frontend"
    subnet_id                     = azurerm_subnet.app.id
    private_ip_address_allocation = "Static"
    private_ip_address            = var.internal_lb_ip
  }
}

resource "azurerm_lb_backend_address_pool" "app" {
  name            = "pool-app"
  loadbalancer_id = azurerm_lb.internal.id
}

resource "azurerm_lb_probe" "app" {
  name                = "probe-app-health"
  loadbalancer_id     = azurerm_lb.internal.id
  protocol            = "Http"
  port                = 8000
  request_path        = "/health"
  interval_in_seconds = 15
  number_of_probes    = 4
}

resource "azurerm_lb_rule" "app" {
  name                           = "rule-app-8000"
  loadbalancer_id                = azurerm_lb.internal.id
  protocol                       = "Tcp"
  frontend_port                  = 8000
  backend_port                   = 8000
  frontend_ip_configuration_name = "internal-frontend"
  backend_address_pool_ids       = [azurerm_lb_backend_address_pool.app.id]
  probe_id                       = azurerm_lb_probe.app.id
}
