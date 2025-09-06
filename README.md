# VM-on-Golem

This project provides a framework for running virtual machines on the Golem Network.

## Environment Configuration

The applications within this repository (provider-server, requestor-server) can be configured to run in different environments, such as `production` or `development`. This is controlled via environment variables.

### Provider Server

To run the provider server in development mode, set the `GOLEM_PROVIDER_ENVIRONMENT` environment variable:

```bash
export GOLEM_PROVIDER_ENVIRONMENT="development"
# Now run your provider application
```

### Requestor Server

To run the requestor server in development mode, set the `GOLEM_REQUESTOR_ENVIRONMENT` environment variable:

```bash
export GOLEM_REQUESTOR_ENVIRONMENT="development"
# Now run your requestor application
```

If these variables are not set, the applications will default to `production` mode.
