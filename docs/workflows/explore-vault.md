# Refresh vault discovery

When you've reorganised folders, added new MOCs, or changed tag conventions, refresh the discovery cache:

```
/explore-vault            # silent rebuild (uses prior confirmations)
/explore-vault --confirm  # walk through every detection step again
```

Discovery writes `tomo-instance/config/discovery-cache.yaml` and may update `vault-config.yaml` for the sections it owns (tags, callouts, relationships, trackers). Each section asks for confirmation before writing. Your vault is never modified — only Tomo's config files. See [Configuration → Override mechanism](../configuration.md#override-mechanism) for how the cache fits into the layer precedence.
