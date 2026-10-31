output "public_url" {
  value = "http://${azurerm_public_ip.lb.ip_address}"
}

output "nat_outbound_ip" {
  value = azurerm_public_ip.nat.ip_address
}

output "key_vault_name" {
  value = azurerm_key_vault.kv.name
}
