import { expect } from "chai";
import { network } from "hardhat";

const { ethers } = await network.create();

describe("StreamPayment", function () {
  async function fixture() {
    const [deployer, sender, recipient, other] = await ethers.getSigners();
    const GLM = await ethers.getContractFactory("MockGLM");
    const glm = await GLM.deploy();
    const SP = await ethers.getContractFactory("StreamPayment");
    const sp = await SP.deploy(await glm.getAddress());
    await glm.mint(sender.address, ethers.parseEther("1000"));
    return { deployer, sender, recipient, other, glm, sp };
  }

  async function leaseQuote(sender, recipient, sp, deposit, rate, leaseSalt = "lease") {
    const now = BigInt((await ethers.provider.getBlock("latest")).timestamp);
    const quoteExpiresAt = now + 3600n;
    const leaseId = ethers.id(`${leaseSalt}-${Date.now()}-${Math.random()}`);
    const termsHash = ethers.keccak256(
      ethers.AbiCoder.defaultAbiCoder().encode(
        ["address", "address", "uint256", "uint128", "bytes32"],
        [sender.address, recipient.address, deposit, rate, leaseId]
      )
    );
    const domain = {
      name: "GolemStreamPayment",
      version: "2",
      chainId: (await ethers.provider.getNetwork()).chainId,
      verifyingContract: await sp.getAddress(),
    };
    const types = {
      LeaseQuote: [
        { name: "recipient", type: "address" },
        { name: "deposit", type: "uint256" },
        { name: "ratePerSecond", type: "uint128" },
        { name: "leaseId", type: "bytes32" },
        { name: "termsHash", type: "bytes32" },
        { name: "quoteExpiresAt", type: "uint128" },
      ],
    };
    const value = {
      recipient: recipient.address,
      deposit,
      ratePerSecond: rate,
      leaseId,
      termsHash,
      quoteExpiresAt,
    };
    const signature = await recipient.signTypedData(domain, types, value);
    return { leaseId, termsHash, quoteExpiresAt, signature };
  }

  async function createGlmStream(sender, recipient, glm, sp, seconds = 100n) {
    const rate = ethers.parseEther("1");
    const deposit = rate * seconds;
    const quote = await leaseQuote(sender, recipient, sp, deposit, rate);
    await glm.connect(sender).approve(await sp.getAddress(), deposit);
    const tx = await sp
      .connect(sender)
      .createStream(
        recipient.address,
        deposit,
        rate,
        quote.leaseId,
        quote.termsHash,
        quote.quoteExpiresAt,
        quote.signature
      );
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
    return { streamId: event.args.streamId, rate, deposit, ...quote };
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

  it("reports active, grace, expired, and terminated stream states", async () => {
    const { sender, recipient, glm, sp } = await fixture();
    const { streamId } = await createGlmStream(sender, recipient, glm, sp, 10n);

    expect(await sp.streamState(streamId)).to.equal("active");

    await ethers.provider.send("evm_increaseTime", [10]);
    await ethers.provider.send("evm_mine");
    expect(await sp.streamState(streamId)).to.equal("grace");

    await ethers.provider.send("evm_increaseTime", [30]);
    await ethers.provider.send("evm_mine");
    expect(await sp.streamState(streamId)).to.equal("expired");

    await sp.connect(sender).terminate(streamId);
    expect(await sp.streamState(streamId)).to.equal("terminated");
  });

  it("allows topUp during grace but rejects topUp after grace", async () => {
    const { sender, recipient, glm, sp } = await fixture();
    const { streamId, deposit } = await createGlmStream(sender, recipient, glm, sp, 10n);

    await ethers.provider.send("evm_increaseTime", [10]);
    await ethers.provider.send("evm_mine");
    expect(await sp.streamState(streamId)).to.equal("grace");

    await glm.connect(sender).approve(await sp.getAddress(), deposit);
    await sp.connect(sender).topUp(streamId, deposit);
    expect(await sp.streamState(streamId)).to.equal("active");

    await ethers.provider.send("evm_increaseTime", [41]);
    await ethers.provider.send("evm_mine");
    expect(await sp.streamState(streamId)).to.equal("expired");

    await glm.connect(sender).approve(await sp.getAddress(), deposit);
    await expect(sp.connect(sender).topUp(streamId, deposit)).to.be.revertedWith(
      "stream expired"
    );
  });

  it("allows recipient withdraw after expiry", async () => {
    const { sender, recipient, glm, sp } = await fixture();
    const { streamId } = await createGlmStream(sender, recipient, glm, sp, 10n);

    await ethers.provider.send("evm_increaseTime", [40]);
    await ethers.provider.send("evm_mine");
    expect(await sp.streamState(streamId)).to.equal("expired");

    const before = await glm.balanceOf(recipient.address);
    await sp.connect(recipient).withdraw(streamId);
    const after = await glm.balanceOf(recipient.address);
    expect(after - before).to.equal(ethers.parseEther("10"));
  });

  it("reverts invalid params", async () => {
    const { sender, recipient, glm, sp } = await fixture();
    await glm.connect(sender).approve(await sp.getAddress(), ethers.parseEther("1"));

    const quote = await leaseQuote(sender, recipient, sp, 1n, 1n, "invalid");
    await expect(
      sp
        .connect(sender)
        .createStream(
          recipient.address,
          0,
          1,
          quote.leaseId,
          quote.termsHash,
          quote.quoteExpiresAt,
          quote.signature
        )
    ).to.be.revertedWith("deposit=0");
    await expect(
      sp
        .connect(sender)
        .createStream(
          recipient.address,
          1,
          0,
          quote.leaseId,
          quote.termsHash,
          quote.quoteExpiresAt,
          quote.signature
        )
    ).to.be.revertedWith("rate=0");
  });

  it("rejects wrong signer, expired quote, and reused lease", async () => {
    const { sender, recipient, other, glm, sp } = await fixture();
    const rate = ethers.parseEther("1");
    const deposit = rate * 10n;
    const quote = await leaseQuote(sender, other, sp, deposit, rate, "wrong-signer");
    await glm.connect(sender).approve(await sp.getAddress(), deposit);
    await expect(
      sp
        .connect(sender)
        .createStream(
          recipient.address,
          deposit,
          rate,
          quote.leaseId,
          quote.termsHash,
          quote.quoteExpiresAt,
          quote.signature
        )
    ).to.be.revertedWith("bad provider signature");

    const expired = await leaseQuote(sender, recipient, sp, deposit, rate, "expired");
    await ethers.provider.send("evm_increaseTime", [3601]);
    await ethers.provider.send("evm_mine");
    await expect(
      sp
        .connect(sender)
        .createStream(
          recipient.address,
          deposit,
          rate,
          expired.leaseId,
          expired.termsHash,
          expired.quoteExpiresAt,
          expired.signature
        )
    ).to.be.revertedWith("quote expired");

    const fresh = await leaseQuote(sender, recipient, sp, deposit, rate, "reuse");
    await glm.connect(sender).approve(await sp.getAddress(), deposit * 2n);
    await sp
      .connect(sender)
      .createStream(
        recipient.address,
        deposit,
        rate,
        fresh.leaseId,
        fresh.termsHash,
        fresh.quoteExpiresAt,
        fresh.signature
      );
    await expect(
      sp
        .connect(sender)
        .createStream(
          recipient.address,
          deposit,
          rate,
          fresh.leaseId,
          fresh.termsHash,
          fresh.quoteExpiresAt,
          fresh.signature
        )
    ).to.be.revertedWith("lease used");
  });

  it("terminate settles vested payout, refunds unvested deposit, and closes stream", async () => {
    const { sender, recipient, glm, sp } = await fixture();
    const { streamId, deposit } = await createGlmStream(
      sender,
      recipient,
      glm,
      sp,
      100n
    );

    await ethers.provider.send("evm_increaseTime", [10]);
    await ethers.provider.send("evm_mine");

    const senderBefore = await glm.balanceOf(sender.address);
    const recipientBefore = await glm.balanceOf(recipient.address);

    await sp.connect(sender).terminate(streamId);

    const senderRefund = (await glm.balanceOf(sender.address)) - senderBefore;
    const recipientPayout =
      (await glm.balanceOf(recipient.address)) - recipientBefore;

    expect(recipientPayout).to.be.greaterThanOrEqual(ethers.parseEther("9"));
    expect(recipientPayout).to.be.lessThanOrEqual(ethers.parseEther("12"));
    expect(senderRefund + recipientPayout).to.equal(deposit);

    await expect(sp.connect(recipient).withdraw(streamId)).to.be.revertedWith(
      "no-stream"
    );
    await glm.connect(sender).approve(await sp.getAddress(), deposit);
    await expect(sp.connect(sender).topUp(streamId, deposit)).to.be.revertedWith(
      "no-stream"
    );
  });
});
