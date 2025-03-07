# VM on Golem - Project Roadmap

## 1. Project Timeline Overview

```mermaid
gantt
    title VM on Golem Development Phases
    dateFormat  YYYY-MM-DD
    section Phase 1 ✅
    Core Infrastructure    :done, p1, 2025-02-20, 1d
    section Phase 2 ✅
    Port Verification     :done, p2, 2025-02-21, 1d
    section Phase 3 🚧
    Smart Contract Payments :active, p3, 2025-02-23, 30d
    Provider GUI Development :active, gui1, 2025-02-23, 45d
    section Phase 4
    Verifier Network      :p4, 2025-03-24, 45d
    Requestor Web Interface :web1, 2025-03-24, 45d
    section Phase 5
    Decentralized Discovery :p5, 2025-05-08, 30d
```

## 2. Technical Architecture Evolution

```mermaid
graph TB
    subgraph "Phase 1: Core Infrastructure ✅"
        R[Requestor CLI]
        P[Provider Node]
        D[Discovery Service]
        R -->|Find Providers| D
        R -->|Create VM| P
    end

    subgraph "Phase 2: Port Verification ✅"
        PV[Port Verifier]
        P -->|Verify Ports| PV
    end

    subgraph "Phase 3: Smart Contracts 🚧"
        SC[Smart Contract]
        W[Wallet Integration]
        PM[Payment Manager]
        SC -->|Manage Funds| PM
        W -->|Handle Transactions| SC
    end

    subgraph "Phase 4: Verifier Network"
        VN[Verifier Nodes]
        VC[Verification Consensus]
        VM[VM Monitor]
        VN -->|Report Status| VC
        VC -->|Update| VM
    end

    subgraph "Phase 5: Decentralized Discovery"
        BC[Blockchain Registry]
        PD[Provider Directory]
        BC -->|Provider Info| PD
    end

    P --> SC
    PV --> VN
    D --> BC
```

## 3. Detailed Phase Breakdown

### Phase 1: Core Infrastructure (✅ Completed Feb 20, 2025)
- **Achievement**: Built in 24 hours
- **Components**:
  - Requestor CLI with intuitive commands
  - Provider Node with VM management
  - Discovery Service for matchmaking
  - SSH key management system
  - Resource monitoring
  - Basic provider advertisement

### Phase 2: Port Verification (✅ Completed Feb 21, 2025)
- **Achievement**: Completed in 24 hours
- **Features**:
  - Automated port accessibility validation
  - Real-time verification status
  - Network diagnostics
  - Temporary port check servers
  - Provider readiness confirmation

### Phase 3: Smart Contract Payments (🚧 In Progress - Feb 23 to Mar 24, 2025)
- **Objective**: Create a trustless payment system
- **Key Components**:
  - Smart contract for fund management
  - Deposit and withdrawal system
  - Usage-based billing
  - Payment verification
  - Automated fund distribution
- **Technical Focus**:
  - Implement time-based billing
  - Secure fund management
  - Transaction optimization
  - Gas cost efficiency

### Phase 3: Provider GUI Development (🚧 In Progress - Feb 23 to Apr 8, 2025)
- **Objective**: Create an intuitive datacenter management interface
- **Key Components**:
  - Resource Dashboard
    - Total CPU cores (used vs. available)
    - Memory allocation (used vs. available)
    - Storage utilization
    - Network bandwidth usage
  - Market Analytics
    - Your pricing vs. market average
    - Demand trends in your region
    - Competitive analysis
  - Revenue Tracking
    - Current monthly earnings
    - Historical earnings graph
    - Projected revenue based on current usage
  - Active VMs
    - Status indicators for each VM
    - Resource allocation per VM
    - Uptime statistics
    - Current revenue per VM

### Phase 4: Verifier Network (🔒 Planned - Mar 24 to May 8, 2025)
- **Objective**: Ensure VM integrity and uptime
- **Components**:
  - Decentralized verifier nodes
  - Cryptographic proof system
  - Consensus mechanism
  - Smart contract integration
  - Port verification service
- **Technical Implementation**:
  - VM fingerprinting system
  - Cryptographic signature verification
  - Consensus protocol
  - Automated status updates
  - Provider reputation tracking

### Phase 4: Requestor Web Interface (🔒 Planned - Mar 24 to May 8, 2025)
- **Objective**: Develop a sleek, intuitive website for VM rental and management
- **Core Features**:
  - **Authentication**
    - MetaMask integration
    - Wallet connection status
    - Account overview
    - Transaction history
  - **VM Management Dashboard**
    - Quick-launch VM templates
    - Active VMs status grid
    - Resource usage metrics
    - Cost tracking per VM
  - **Provider Marketplace**
    - Available providers list
    - Provider ratings and metrics
    - Price comparisons
    - Resource availability
    - Quick-rent functionality
  - **VM Control Center**
    - SSH access management
    - Start/Stop/Restart controls
    - Resource scaling options
    - Performance monitoring
    - Cost projections

### Phase 5: Decentralized Discovery (🌐 Future - May 8 to Jun 7, 2025)
- **Objective**: Simple decentralized provider directory
- **Features**:
  - On-chain provider registry
  - Provider self-advertisement
    - Resource specifications (CPU, RAM, etc.)
    - Location information
    - Pricing details
  - Simple filtering capabilities for requestors
    - Filter by minimum resource requirements
    - Filter by location
    - Filter by price range
