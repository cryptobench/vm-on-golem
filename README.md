# VM on Golem

> 🎯 **Building the Future of Cloud Computing**
> 
> VM on Golem is revolutionizing DePIN by making decentralized cloud computing as simple as possible. Our vision is to become the AWS of Web3, setting new standards for simplicity in decentralized infrastructure.

## 📚 Strategic Vision & Roadmap

### Current Phase: Smart Contract Integration 🚧
We're building a trustless payment system and intuitive datacenter management interface.
[View Full Roadmap →](VM-on-Golem-VISION/ROADMAP.md)

### Our Vision
- **Simplicity First**: One command deployment, no complex protocols
- **Zero Learning Curve**: Works exactly like traditional cloud providers
- **Complete Freedom**: Run anything - from simple web servers to full Kubernetes clusters
- **True Decentralization**: Direct provider connections worldwide
[Learn More About Our Vision →](VM-on-Golem-VISION/VISION.md)

### Design Philosophy
Built with modern, sleek interfaces that work in both light and dark modes, focusing on clarity and usability.
[Explore Our Design System →](VM-on-Golem-VISION/VISUALS.md)

---

## 🚀 One Command to Get Started

```bash
golem vm create my-webserver --size small
```

That's it. No complex protocols. No specialized knowledge needed.

## ✨ Why VM on Golem?

- **Simple** - One command to get a VM
- **Familiar** - Works just like AWS or DigitalOcean
- **Flexible** - Run anything - Docker, Kubernetes, web servers
- **Decentralized** - Connect with providers worldwide

Built with simplicity in mind:
- Standard SSH for access (not a custom protocol in sight)
- Multipass for VM management (because why reinvent the wheel?)
- FastAPI for simple APIs (no complex frameworks needed)
- SQLite for storage (sometimes a file is all you need)

## 🏃‍♂️ Quick Start

### For Users (Requestors)

```bash
# Install the requestor CLI
pip install request-vm-on-golem

# List available providers
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

# Connect via SSH
golem vm ssh my-webserver
```

### For Providers

```bash
# Install the provider software
pip install golem-vm-provider

# Start earning by sharing your resources
golem-provider
```

## 🧩 Core Components

Each component has its own detailed documentation:

- **[Requestor CLI](requestor-server/README.md)** - Rent and manage VMs
- **[Provider Node](provider-server/README.md)** - Share computing power
- **[Discovery Service](discovery-server/README.md)** - Find available providers
- **[Port Checker](port-checker-server/README.md)** - Verify network setup

## 👥 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the tests
5. Submit a pull request

Remember: Keep it simple. If you can't explain your change to a 12-year-old, it's probably too complex.

For instructions on publishing new versions of the packages to PyPI, see [PUBLISHING.md](PUBLISHING.md).
