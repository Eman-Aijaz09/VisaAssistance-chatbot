variable "subscription_id" {
  type = string
}

variable "location" {
  type    = string
  default = "malaysiawest"
}

variable "internal_lb_ip" {
  type    = string
  default = "10.0.2.10"
}

variable "web_vm_size" {
  type    = string
  default = "Standard_B2ls_v2"
}

variable "app_vm_size" {
  type    = string
  default = "Standard_B2s_v2"
}

variable "ghcr_owner" {
  type    = string
  default = "eman-aijaz09"
}

variable "supabase_db_url" {
  type      = string
  sensitive = true
}

variable "groq_api_key" {
  type      = string
  sensitive = true
}
