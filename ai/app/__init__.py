# Use the OS trust store for TLS (handles corporate/local CA on this machine,
# the Python analog of Node's --use-system-ca). No-op if truststore is absent.
try:
    import truststore

    truststore.inject_into_ssl()
except Exception:  # noqa: BLE001
    pass
