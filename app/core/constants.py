PROXY_TYPE_MAPPING = {
    "ipv4": "4",
    "ipv6": "6",
    "ipv4shared": "3"
}
REVERSE_PROXY_TYPE_MAPPING = {v: k for k, v in PROXY_TYPE_MAPPING.items()}