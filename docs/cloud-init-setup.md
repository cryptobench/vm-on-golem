# Cloud-Init Directory Setup

The Golem Provider needs a directory to store cloud-init configurations that are used when creating VMs. This guide explains how this directory is set up on different operating systems.

## Linux with Snap Multipass

When using Multipass installed via snap on Linux, the cloud-init configurations need to be stored in `/var/snap/multipass/common/cloud-init`. The Golem Provider will attempt to set this up automatically on first run.

### Automatic Setup

On first run, the provider will:
1. Detect that you're using snap Multipass
2. Try to create and configure the cloud-init directory with proper permissions
3. If successful, store a flag to avoid running setup again

### Manual Setup

If automatic setup fails (usually due to sudo permissions), you'll need to run these commands manually:

```bash
sudo mkdir -p /var/snap/multipass/common/cloud-init
sudo chown -R $USER:$USER /var/snap/multipass/common/cloud-init
sudo chmod -R 755 /var/snap/multipass/common/cloud-init
```

### Fallback Behavior

If the provider can't set up or access the optimal directory, it will fall back to:
1. First try `~/.local/share/golem/provider/cloud-init`
2. If that fails, use a temporary directory

A warning will be logged if using a fallback location.

## Linux without Snap

When using Multipass installed without snap, configurations are stored in:
```
~/.local/share/golem/provider/cloud-init
```

No special setup is required as this is in your home directory.

## macOS

On macOS, configurations are stored in:
```
~/Library/Application Support/golem/provider/cloud-init
```

No special setup is required.

## Windows

On Windows, configurations are stored in:
```
%LOCALAPPDATA%\golem\provider\cloud-init
```

No special setup is required.

## Troubleshooting

### Permission Denied Errors

If you see "Permission denied" errors when creating VMs:

1. Check if you're using snap Multipass:
   ```bash
   which multipass
   ```
   If it shows `/snap/bin/multipass`, follow the manual setup steps above.

2. Verify directory permissions:
   ```bash
   ls -la /var/snap/multipass/common/cloud-init
   ```
   You should see your user as the owner with 755 permissions.

3. Try removing the setup flag to force reconfiguration:
   ```bash
   rm ~/.golem/provider/.setup-complete
   ```

### Custom Directory Location

You can override the default location by setting the environment variable:
```bash
export GOLEM_PROVIDER_CLOUD_INIT_DIR=/path/to/your/directory
```

The directory must be:
- Readable by Multipass
- Writable by your user
- Have 755 permissions on Unix systems
