# VM on Golem API Reference

## Overview

This document describes the APIs for the three main components of VM on Golem:
1. Discovery Service API - Advertisement board for providers
2. Provider API - VM management endpoints
3. Requestor API - CLI commands and client library

## Discovery Service API

The Discovery Service acts as a simple advertisement board where providers can post their available resources and requestors can find suitable providers.

### Base URL
```
http://discovery.golem.network:9001
```

### Endpoints

#### 1. Post Advertisement
```http
POST /api/v1/advertisements
```

Posts or updates a provider's resource advertisement.

**Headers:**
- `X-Provider-ID`: Provider's unique identifier
- `X-Provider-Signature`: Request signature

**Request Body:**
```json
{
    "ip_address": "83.233.10.2",
    "resources": {
        "cpu": 4,
        "memory": 8,
        "storage": 100
    },
    "country": "SE"
}
```

**Response:**
```json
{
    "provider_id": "provider123",
    "ip_address": "83.233.10.2",
    "resources": {
        "cpu": 4,
        "memory": 8,
        "storage": 100
    },
    "country": "SE",
    "updated_at": "2025-02-19T09:54:30Z"
}
```

#### 2. Query Advertisements
```http
GET /api/v1/advertisements
```

Find providers matching resource requirements.

**Query Parameters:**
- `cpu` (optional): Minimum CPU cores required
- `memory` (optional): Minimum memory (GB) required
- `storage` (optional): Minimum storage (GB) required
- `country` (optional): Preferred provider country (ISO 3166-1 alpha-2)

**Response:**
```json
[
    {
        "provider_id": "provider123",
        "ip_address": "83.233.10.2",
        "resources": {
            "cpu": 4,
            "memory": 8,
            "storage": 100
        },
        "country": "SE",
        "updated_at": "2025-02-19T09:54:30Z"
    }
]
```

## Provider API

Each provider exposes a REST API for VM management operations.

### Base URL
```
http://{provider_ip}:9001
```

### Endpoints

#### 1. Create VM
```http
POST /api/v1/vms
```

Create a new VM instance.

**Request Body:**
```json
{
    "name": "my-webserver",
    "cpu": 2,
    "memory": 4,
    "storage": 20
}
```

**Response:**
```json
{
    "id": "vm-123",
    "name": "my-webserver",
    "status": "running",
    "ip_address": "83.233.10.3",
    "ssh_port": 22,
    "created_at": "2025-02-19T09:54:30Z",
    "updated_at": "2025-02-19T09:54:30Z"
}
```

#### 2. Add SSH Key
```http
POST /api/v1/vms/{vm_id}/ssh-keys
```

Add SSH key to a VM.

**Request Body:**
```json
{
    "key": "ssh-rsa AAAA...",
    "name": "default"
}
```

**Response:**
```json
{
    "status": "success"
}
```

#### 3. Get VM Status
```http
GET /api/v1/vms/{vm_id}
```

Get current VM status.

**Response:**
```json
{
    "id": "vm-123",
    "name": "my-webserver",
    "status": "running",
    "ip_address": "83.233.10.3",
    "ssh_port": 22,
    "created_at": "2025-02-19T09:54:30Z",
    "updated_at": "2025-02-19T09:54:30Z"
}
```

## Requestor CLI

The requestor provides a CLI for easy VM management.

### Commands

#### 1. Create VM
```bash
golem vm create <name> --size <size> [--country <country>]
```

Create a new VM with specified size.

**Options:**
- `--size`: VM size (small, medium, large)
- `--country`: Preferred provider country code

**Example:**
```bash
golem vm create my-webserver --size medium --country SE
```

#### 2. SSH into VM
```bash
golem vm ssh <name>
```

SSH into a running VM.

**Example:**
```bash
golem vm ssh my-webserver
```

## Error Responses

All APIs use a standard error response format:

```json
{
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
        "additional": "error context"
    },
    "timestamp": "2025-02-19T09:54:30Z"
}
```

### Common Error Codes

1. Authentication Errors
   - `AUTH_001`: Invalid token
   - `AUTH_002`: Expired token
   - `AUTH_003`: Missing signature

2. Resource Errors
   - `RES_001`: Resource not found
   - `RES_002`: Resource exhausted
   - `RES_003`: Resource unavailable

3. VM Errors
   - `VM_001`: VM creation failed
   - `VM_002`: VM not found
   - `VM_003`: VM already exists

4. Network Errors
   - `NET_001`: Network timeout
   - `NET_002`: Network unreachable
   - `NET_003`: Port blocked

## Rate Limits

- Discovery Service: 100 requests per minute per IP
- Provider API: 60 requests per minute per requestor
- All limits use a sliding window

## Authentication

1. Provider Authentication
   ```http
   X-Provider-ID: provider123
   X-Provider-Signature: {signature}
   ```

2. Requestor Authentication
   - SSH key-based authentication for VM access
   - No authentication needed for discovery service queries

## Notes

1. Advertisements expire after 5 minutes if not updated
2. Providers should update their advertisement every 4 minutes
3. All timestamps are in UTC
4. All sizes are in GB
5. Country codes use ISO 3166-1 alpha-2 format
