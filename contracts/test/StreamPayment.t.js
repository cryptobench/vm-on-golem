const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("StreamPayment", function () {
  async function fixture() {
    const [deployer, sender, recipient, oracle] = await ethers.getSigners();
    const GLM = await ethers.getContractFactory("MockGLM");
    const glm = await GLM.deploy();
    const SP = await ethers.getContractFactory("StreamPayment");
    const sp = await SP.deploy(oracle.address, await glm.getAddress());
    await glm.mint(sender.address, ethers.parseEther("1000"));
    return { deployer, sender, recipient, oracle, glm, sp };
  }

  async function createGlmStream(sender, recipient, glm, sp, seconds = 100n) {
    const rate = ethers.parseEther("1");
    const deposit = rate * seconds;
    await glm.connect(sender).approve(await sp.getAddress(), deposit);
    const tx = await sp
      .connect(sender)
      .createStream(await glm.getAddress(), recipient.address, deposit, rate);
    const receipt = await tx.wait();
    const event = receipt.logs
      .map((log) => {
        try {
          return sp.interface.parseLog(log);
        } catch {
          return null;
        }
      })
      .filter(Boolean)[0];
    return { streamId: event.args.streamId, rate, deposit };
  }

  it("creates GLM stream and allows withdraw", async () => {
    const { sender, recipient, glm, sp } = await fixture();
    const { streamId } = await createGlmStream(sender, recipient, glm, sp);

    await ethers.provider.send("evm_increaseTime", [10]);
    await ethers.provider.send("evm_mine");

    const before = await glm.balanceOf(recipient.address);
    await sp.connect(recipient).withdraw(streamId);
    const after = await glm.balanceOf(recipient.address);
    expect(after - before).to.be.greaterThanOrEqual(ethers.parseEther("9"));
  });

  it("topUp extends stopTime", async () => {
    const { sender, recipient, glm, sp } = await fixture();
    const { streamId, deposit } = await createGlmStream(sender, recipient, glm, sp, 10n);
    const s0 = await sp.streams(streamId);

    await glm.connect(sender).approve(await sp.getAddress(), deposit);
    await sp.connect(sender).topUp(streamId, deposit);

    const s1 = await sp.streams(streamId);
    expect(s1.stopTime).to.be.greaterThan(s0.stopTime);
  });

  it("reverts invalid params", async () => {
    const { sender, recipient, glm, sp } = await fixture();
    await glm.connect(sender).approve(await sp.getAddress(), ethers.parseEther("1"));

    await expect(
      sp.connect(sender).createStream(await glm.getAddress(), recipient.address, 0, 1)
    ).to.be.revertedWith("deposit=0");
    await expect(
      sp.connect(sender).createStream(await glm.getAddress(), recipient.address, 1, 0)
    ).to.be.revertedWith("rate=0");
    await expect(
      sp
        .connect(sender)
        .createStream(
          "0x1111111111111111111111111111111111111111",
          recipient.address,
          1,
          1
        )
    ).to.be.revertedWith("token != GLM");
  });

  it("oracle halt prevents topUp", async () => {
    const { sender, recipient, glm, sp, oracle } = await fixture();
    const { streamId, deposit } = await createGlmStream(sender, recipient, glm, sp, 5n);

    await sp.connect(oracle).haltStream(streamId);
    await glm.connect(sender).approve(await sp.getAddress(), deposit);

    await expect(
      sp.connect(sender).topUp(streamId, deposit)
    ).to.be.revertedWith("halted");
  });
});
