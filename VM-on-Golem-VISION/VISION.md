# Why VM on Golem  
In my view, the biggest challenge with adopting the Golem Network has always been the **complex user experience**. Users are required to learn Golem-specific components that **don’t apply elsewhere**, which takes **time and trust**. This complexity can be a deal-breaker, leading to **uncertainty and slow development**.  

With **VM on Golem**, I believe in focusing on **simplicity**. My goal is to create a product that’s **easy to use**, allowing anyone to migrate their existing workloads **without limitations**. I envision a platform where you can **get started in just five minutes**.  

I’m passionate about **building a community** that transforms the **crypto (Web3) landscape**. Web3 is often seen as **complex**, and I want to **change that perception**. We’re creating a platform that’s **easy to use**, setting a **new standard for simplicity** in Web3 and **DePIN**. **VM on Golem will define the combination of simplicity and Web3**.  

---

# What's the Goal?  
Our goal is to **revolutionize DePIN** by making it **as simple as possible** to rent and deploy VMs in the crypto world. We’re creating a platform that’s **so intuitive**, even someone with **minimal technical experience** can get started **in minutes**.  

VM on Golem will be **one of the core foundations** of cloud computing, just like **AWS conquered Web2 cloud computing**. In the future, **VM on Golem will be the first mover** that everyone recognizes, changing the landscape of **Web3 and DePIN** by making **complex cloud computing easy and accessible to everyone**.  

### What Are We Building First?  
We’re starting with **simple VMs** that anyone can **compute anything inside**, just like renting a **VPS** from any cloud provider.  

- **No limitations on use cases**, giving you **full control** over what you do inside the VM.  
- **Run whatever you need**, including Docker containers, local projects, Discord bots, Kubernetes, or Docker Compose.  
- **Works just like everywhere else**. If you have used **AWS, DigitalOcean, or any VPS**, you can use **VM on Golem without relearning anything**.  
- **No complex setup**. It is **just simple**.  

Once we have **established the foundation**, we will **expand into more advanced areas**, building a **full ecosystem of tools** so developers **don’t have to look elsewhere**.  

- **Serverless computing on Golem**  
- **Kubernetes on Golem**  
- **S3-compatible storage on Golem**  
- **Decentralized storage on Golem**  
- **Low-latency computing on Golem**  
- **Lambdas on Golem**  

Everything will be **centered around the Golem ecosystem**, making it the **natural hub for decentralized cloud computing**.  

---

# What Challenges Does It Solve?  
### 1. **Fixing the bad UX in Golem Network**  
Right now, Golem **isn’t easy to use**. **VM on Golem is here to change that** by making everything **simple, intuitive, and frictionless**.  

### 2. **No limitations, just possibilities**  
The **technology won’t be the limitation**. Whatever you want to do, **you can do it**.  

### 3. **A no-brainer to use**  
We’re creating an ecosystem that is **so good, there’s no reason not to be in it**. VM on Golem will be the **default space for Web3 and DePIN**.  

We’re setting a **new standard for decentralized cloud computing** where **simplicity and power go hand in hand**.


---

# Core Principles  

## 1. Intuitive User Experience  

In cloud computing, **user experience is everything**. With **VM on Golem**, the goal is to create an interface that is **powerful yet intuitive**, making it **accessible to users of all skill levels**. Here’s how we plan to achieve this:  

### Commands That Make Sense at First Glance  

#### **Clarity and Simplicity**  
Our command-line interface is designed to be **self-explanatory**. Each command is crafted to **make sense instantly**, reducing the need for extensive documentation and allowing users to get started quickly.  

**Example:**  
Creating a new virtual machine is as simple as:  
```bash
golem vm create my-webserver --size small
```  
This command clearly defines the action (**create**), the resource (**vm**), the name (**my-webserver**), and the size (**small**).  

#### **Consistency with Industry Standards**  
We align our command syntax with **familiar patterns** from traditional cloud providers like AWS and DigitalOcean. This makes our interface **instantly recognizable** for experienced users while keeping it simple for newcomers.  

**Example:**  
Listing available VM sizes is straightforward:  
```bash
golem vm list-sizes
```  
This follows the same intuitive structure found in other cloud platforms.  

#### **Clear Feedback and Error Handling**  
We ensure that every action provides **immediate and useful feedback**, making it easy to confirm success or troubleshoot issues.  

**Example:**  
After creating a VM, users get clear, structured feedback:  
```bash
✅ VM 'my-webserver' deployed successfully on Golem Network!  
SSH Access  : ssh root@83.233.10.2  
Password    : xG8f7Lk3  
IP Address  : 83.233.10.2  
Port        : 22  
VM Status   : Running  
Allocated Size : small  
```  
This response provides **all necessary details** upfront, removing the need for users to search for additional setup steps.  

#### **Modern, Clean Interface**  
A simple and modern interface improves usability and enhances the **overall experience**. The focus is on **removing friction**, so users can focus on running their workloads, not learning how to navigate complex configurations.  

---

## **Comparison: VM on Golem vs. Current Golem vs. Other Cloud Providers**  

### **Current Golem Network: A Complicated Setup Process**  
Right now, setting up and accessing a VM on the Golem Network requires **learning multiple Golem-specific concepts before you can even start working**.  

1. **Learn about Golem**—Understand the decentralized structure.  
2. **Learn GVMI**, Golem’s custom image format, which is **similar to Docker but doesn’t work exactly the same**.  
3. **Learn either the JS or Python SDK**, since interacting with Golem requires custom scripts.  
4. **Write 135 lines of Python code just to start an SSH server** and gain access to the VM.  

This setup **takes time, requires learning new tools, and adds friction for developers** who just want a simple way to deploy and manage virtual machines.  

### **VM on Golem: Simplicity From the Start**  
With **VM on Golem**, the entire process is reduced to **one command**.  

```bash
golem vm create my-webserver --size small
```  

The VM **already includes SSH** and is **ready to use immediately**. No SDKs, no scripting, no manual setup.  

**Example: SSH details appear instantly after deployment**  
```bash
✅ VM 'my-webserver' deployed successfully on Golem Network!  
SSH Access  : ssh root@83.233.10.2  
Password    : xG8f7Lk3  
IP Address  : 83.233.10.2  
Port        : 22  
VM Status   : Running  
Allocated Size : small  
```  

With **zero extra configuration needed**, users can **immediately connect and start working**.  

### **Traditional Cloud Providers (AWS, DigitalOcean, etc.)**  
- Offer simple SSH access but often require **choosing key pairs, firewall rules, and networking configurations** before deployment.  
- **Still more steps than VM on Golem**, where SSH is ready out of the box.  

---

## **Bottom Line: VM on Golem Removes the Complexity**  
We **eliminate the 135 lines of code** needed in the current Golem setup and replace it with **one simple command**.  

This is what **user-friendly decentralized cloud computing** should look like.
   
---

## **2. Zero Learning Curve**  

### **Works Just Like Any Other Cloud Provider**  
VM on Golem enables seamless adoption by using the same tools and workflows developers already know. There is no need to learn new protocols, SDKs, or complex configurations. If you know AWS, DigitalOcean, or any standard cloud provider, you can use VM on Golem immediately.  

- **Familiar Tools, No Adjustments Needed**  
  - SSH, Linux commands, and standard cloud management practices work exactly the same way.  
  - No proprietary software or custom integrations. You launch a VM and start working.  

- **1:1 Migration Without Modifications**  
  - Applications and workloads running on AWS, DigitalOcean, or other cloud providers can move to Golem without any changes.  
  - Same configurations, same scripts, and the same deployment process on a decentralized infrastructure.  

  **Example:** A web application running on AWS can be migrated to VM on Golem without any reconfiguration. Deploying it is as simple as switching cloud providers, ensuring a smooth transition without extra work.  

- **Instant Familiarity, No Learning Curve**  
  - The CLI and interface mirror traditional cloud environments, making it instantly recognizable for developers.  
  - No steep onboarding. Anyone familiar with VMs can start using it immediately.  

By removing friction and eliminating the need for relearning, VM on Golem makes decentralized cloud computing as accessible as any traditional cloud provider.

---

## **3. Complete Transparency**  

Everything about **VM on Golem is public**. There are no hidden details, no vague plans, and no closed-door decisions. The vision is clear, and because of that, we can **move fast, make quick decisions, and keep everyone informed**.  

### **A Roadmap That Everyone Can See**  
We maintain a **public roadmap** that is always up to date. Anyone can check our progress, see what we are working on, and know exactly what comes next. There is no guesswork or uncertainty. The plan is laid out for everyone to follow.  

### **Open Development, No Gatekeeping**  
VM on Golem is built in the open. Every major decision, improvement, or discussion happens where everyone can see and contribute. I believe in **collaboration over secrecy**.  

- Everything happens in **GitHub, Discord, and open discussions**.  
- **Regular updates** keep everyone in the loop.  
- **If you have a question, you will get a clear answer the same day**. The vision is clear to me, so there is no delay in providing answers or direction.  

### **Clear and Accessible Documentation**  
Everything you need to understand VM on Golem is always available. The documentation is **well-structured, easy to follow, and constantly updated**. Whether you are deploying your first VM or migrating a full workload, the information is there when you need it.  

### **Engaged and Responsive Community**  
Transparency is not just about making things public. It is about **making sure people feel heard and valued**.  

- If you ask something, you get a **fast and clear response**.  
- The community is **kept informed with frequent updates**.  
- Feedback matters. If something needs to be improved, we **act on it**.  

### **Regular Progress Reports**  
I will personally ensure that **updates on efforts and goals** are shared regularly. Whether it is new features, optimizations, or upcoming milestones, you will **always** know what is happening.  

With **VM on Golem, nothing is hidden**. The **vision is clear, the roadmap is open, and you always know what is coming next**.

---

## **Join Us in Building the Future of Decentralized Cloud Computing**  

I hope you are just as excited about **VM on Golem** as I am. This is more than just a project. It is an opportunity to make **Web3 and DePIN more accessible, open, and easy to use for everyone**.  

If this vision resonates with you, I would love for you to be part of it. Whether you come from **engineering, design, finance, marketing, security, or are simply interested in decentralized technology**, there are many ways to get involved.  

- **If you are a developer**, you can explore the code, share feedback, or help refine the CLI.  
- **If you are a designer**, your ideas can help shape a seamless and intuitive experience.  
- **If you love writing**, you can help make documentation and guides clearer for new users.  
- **If you enjoy marketing or community building**, you can help spread the word and grow our network.  
- **If you are simply curious and want to learn**, your perspective and engagement are just as valuable.  

Every skill, idea, and conversation helps shape what we are building. If this excites you, join us on **Discord, GitHub, or our community spaces**, jump into the discussion, or just follow along. There is no pressure, just an open space to be part of something new. Let’s build this together.