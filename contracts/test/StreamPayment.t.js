const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("StreamPayment", function () {
  async function fixture() {
    const [deployer, sender, recipient, oracle] = await ethers.getSigners();
    const GLM = await ethers.getContractFactory("MockGLM");
    const glm = await GLM.deploy();
    const SP = await ethers.getContractFactory("StreamPayment");
    const sp = await SP.deploy(oracle.address);

    // fund sender with GLM
    await glm.mint(sender.address, ethers.parseEther("1000"));
    return { deployer, sender, recipient, oracle, glm, sp };
  }

  it("creates stream and allows withdraw", async () => {
    const { sender, recipient, glm, sp } = await fixture();
    const rate = ethers.parseEther("1"); // 1 GLM / s
    const deposit = rate * 100n; // 100 s
    await glm.connect(sender).approve(sp.getAddress(), deposit);
    const tx = await sp.connect(sender).createStream(await glm.getAddress(), recipient.address, deposit, rate);
    const rc = await tx.wait();
    const ev = rc.logs.map(l => {
      try { return sp.interface.parseLog(l); } catch { return null; }
    }).filter(Boolean)[0];
    const streamId = ev.args.streamId;

    // advance time ~10s
    await ethers.provider.send("evm_increaseTime", [10]);
    await ethers.provider.send("evm_mine");
    const before = await glm.balanceOf(recipient.address);
    await sp.connect(recipient).withdraw(streamId);
    const after = await glm.balanceOf(recipient.address);
    expect(after - before).to.be.greaterThanOrEqual(ethers.parseEther("9"));
  });

  it("topUp extends stopTime", async () => {
    const { sender, recipient, glm, sp } = await fixture();
    const rate = ethers.parseEther("1");
    const deposit = rate * 10n; // 10s
    await glm.connect(sender).approve(sp.getAddress(), deposit);
    const tx = await sp.connect(sender).createStream(await glm.getAddress(), recipient.address, deposit, rate);
    const rc = await tx.wait();
    const ev = rc.logs.map(l => { try { return sp.interface.parseLog(l); } catch { return null; } }).filter(Boolean)[0];
    const streamId = ev.args.streamId;
    const s0 = await sp.streams(streamId);
    // top up another 10s
    await glm.connect(sender).approve(sp.getAddress(), deposit);
    await sp.connect(sender).topUp(streamId, deposit);
    const s1 = await sp.streams(streamId);
    expect(s1.stopTime).to.be.greaterThan(s0.stopTime);
  });

  it("reverts invalid params", async () => {
    const { sender, recipient, glm, sp } = await fixture();
    await glm.connect(sender).approve(sp.getAddress(), ethers.parseEther("1"));
    await expect(
      sp.connect(sender).createStream(await glm.getAddress(), recipient.address, 0, 1)
    ).to.be.revertedWith("deposit=0");
    await expect(
      sp.connect(sender).createStream(await glm.getAddress(), recipient.address, 1, 0)
    ).to.be.revertedWith("rate=0");
  });

  it("oracle halt prevents topUp", async () => {
    const { sender, recipient, glm, sp, oracle } = await fixture();
    const rate = ethers.parseEther("1");
    const deposit = rate * 5n;
    await glm.connect(sender).approve(sp.getAddress(), deposit);
    const tx = await sp.connect(sender).createStream(await glm.getAddress(), recipient.address, deposit, rate);
    const rc = await tx.wait();
    const streamId = rc.logs.map(l => { try { return sp.interface.parseLog(l); } catch { return null; } }).filter(Boolean)[0].args.streamId;
    await sp.connect(oracle).haltStream(streamId);
    await glm.connect(sender).approve(sp.getAddress(), deposit);
    await expect(sp.connect(sender).topUp(streamId, deposit)).to.be.revertedWith("halted");
  });
});

