# VM on Golem

Rent computing power as easily as ordering a pizza. VM on Golem makes it simple to either rent out your spare computing resources or get the computing power you need, when you need it.

> **Want to understand our vision?** Check out our detailed vision documents:
> - [Vision](VM-on-Golem-VISION/VISION.md) - The why and what of VM on Golem
> - [Visual Design](VM-on-Golem-VISION/VISUALS.md) - Our design philosophy and UI direction
> - [Project Roadmap](VM-on-Golem-VISION/ROADMAP.md) - Where we're headed and how we'll get there

> **8 years of development vs 24 hours of simplicity**: Sometimes the simplest solution is the best solution. This MVP was built in a single day using standard tools and protocols - because renting computing power shouldn't be rocket science.

https://github.com/user-attachments/assets/4ab118f6-fa00-4612-8033-dea7b352deae

## What is VM on Golem?

Think of VM on Golem as the Airbnb for computing power:
- **Providers** are like hosts, offering their spare computing power
- **Requestors** are like guests, renting computing power when they need it

It's that simple. No complex protocols, no specialized knowledge needed - just straightforward virtual machines that work exactly like any cloud provider you're used to.

## How Simple? This Simple:

If you need computing power:

```bash
# Find available providers
golem vm providers

# See what's available
────────────────────────────────────────────────
  🌍 Available Providers (3 total)
────────────────────────────────────────────────
Provider ID     Country   CPU    Memory    Storage
provider-1      🌍 SE     💻 4    🧠 8GB    💾 40GB
provider-2      🌍 US     💻 8    🧠 16GB   💾 80GB
provider-3      🌍 DE     💻 2    🧠 4GB    💾 20GB
────────────────────────────────────────────────

# Create a VM
golem vm create my-webserver --provider-id provider-1 --cpu 2 --memory 4 --storage 20

# Connect via SSH, just like any other VM
golem vm ssh my-webserver
```

If you want to offer computing power:
1. Install the provider software
2. Choose how much CPU, memory, and storage to offer
3. Start earning by sharing your resources

## Why VM on Golem?

Traditional cloud platforms are complex and centralized. VM on Golem brings:
- **Simplicity**: One command to get a VM
- **Familiarity**: Works just like any VM you're used to
- **Freedom**: Run anything you want, it's your VM
- **Decentralization**: Connect directly with providers worldwide

Built with simplicity in mind:
- Standard SSH for access (not a custom protocol in sight)
- Multipass for VM management (because why reinvent the wheel?)
- FastAPI for simple APIs (no complex frameworks needed)
- SQLite for storage (sometimes a file is all you need)

## Getting Started

### For Users Wanting to Rent VMs (Requestors)

```bash
# Install the requestor CLI
pip install request-vm-on-golem

# List available providers
golem vm providers

# Create a VM
golem vm create my-webserver --cpu 2 --memory 4 --storage 20

# SSH into your VM
golem vm ssh my-webserver
```

### For Users Offering Computing Power (Providers)

```bash
# Install the provider software
pip install golem-vm-provider

# Start earning by sharing your resources
golem-provider
```

## Components

Each component has its own detailed documentation:
- [Requestor CLI Documentation](requestor-server/README.md)
- [Provider Node Documentation](provider-server/README.md)
- [Discovery Service Documentation](discovery-server/README.md)
- [Port Checker Documentation](port-checker-server/README.md)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the tests
5. Submit a pull request

Remember: Keep it simple. If you can't explain your change to a 12-year-old, it's probably too complex.

For instructions on publishing new versions of the packages to PyPI, see [PUBLISHING.md](PUBLISHING.md).
