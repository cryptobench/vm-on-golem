import { expect } from "chai";
import { network } from "hardhat";

const { ethers } = await network.create();

const DONATION_RECIPIENT = "0x94153E31AA476cE30C3AF64C255C623f80920BfF";
const DEFAULT_DONATION_BPS = 150n;
const MAX_DONATION_BPS = 1000n;

function donationFor(providerAmount, donationBps) {
  return (providerAmount * BigInt(donationBps)) / 10_000n;
}

describe("StreamPayment", function () {
  async function fixture() {
    const [deployer, sender, recipient, other] = await ethers.getSigners();
    const GLM = await ethers.getContractFactory("MockGLM");
    const glm = await GLM.deploy();
    const SP = await ethers.getContractFactory("StreamPayment");
    const sp = await SP.deploy(await glm.getAddress(), DONATION_RECIPIENT);
    await glm.mint(sender.address, ethers.parseEther("1000"));
    return { deployer, sender, recipient, other, glm, sp };
  }

  async function leaseQuote(
    sender,
    recipient,
    sp,
    providerDeposit,
    providerRate,
    leaseSalt = "lease",
  ) {
    const now = BigInt((await ethers.provider.getBlock("latest")).timestamp);
    const quoteExpiresAt = now + 3600n;
    const leaseId = ethers.id(`${leaseSalt}-${Date.now()}-${Math.random()}`);
    const termsHash = ethers.keccak256(
      ethers.AbiCoder.defaultAbiCoder().encode(
        [
          "address",
          "address",
          "uint256",
          "uint128",
          "bytes32",
        ],
        [
          sender.address,
          recipient.address,
          providerDeposit,
          providerRate,
          leaseId,
        ],
      ),
    );
    const domain = {
      name: "GolemStreamPayment",
      version: "4",
      chainId: (await ethers.provider.getNetwork()).chainId,
      verifyingContract: await sp.getAddress(),
    };
    const types = {
      LeaseQuote: [
        { name: "recipient", type: "address" },
        { name: "providerDeposit", type: "uint256" },
        { name: "providerRatePerSecond", type: "uint128" },
        { name: "leaseId", type: "bytes32" },
        { name: "termsHash", type: "bytes32" },
        { name: "quoteExpiresAt", type: "uint128" },
      ],
    };
    const value = {
      recipient: recipient.address,
      providerDeposit,
      providerRatePerSecond: providerRate,
      leaseId,
      termsHash,
      quoteExpiresAt,
    };
    const signature = await recipient.signTypedData(domain, types, value);
    return { leaseId, termsHash, quoteExpiresAt, signature };
  }

  async function createGlmStream(
    sender,
    recipient,
    glm,
    sp,
    seconds = 100n,
    donationBps = DEFAULT_DONATION_BPS,
  ) {
    const providerRate = ethers.parseEther("1");
    const providerDeposit = providerRate * seconds;
    const donationDeposit = donationFor(providerDeposit, donationBps);
    const totalDeposit = providerDeposit + donationDeposit;
    const quote = await leaseQuote(
      sender,
      recipient,
      sp,
      providerDeposit,
      providerRate,
    );
    await glm.connect(sender).approve(await sp.getAddress(), totalDeposit);
    const tx = await sp
      .connect(sender)
      .createStream(
        recipient.address,
        providerDeposit,
        providerRate,
        donationBps,
        quote.leaseId,
        quote.termsHash,
        quote.quoteExpiresAt,
        quote.signature,
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
      .filter((event) => event?.name === "StreamCreated")[0];
    return {
      streamId: event.args.streamId,
      providerRate,
      providerDeposit,
      donationDeposit,
      totalDeposit,
      donationBps,
      ...quote,
    };
  }

  it("creates GLM stream with requestor-paid donation deposit", async () => {
    const { sender, recipient, glm, sp } = await fixture();
    const senderBefore = await glm.balanceOf(sender.address);
    const stream = await createGlmStream(sender, recipient, glm, sp);

    const chain = await sp.streams(stream.streamId);
    expect(chain.recipient).to.equal(recipient.address);
    expect(chain.donationRecipient).to.equal(DONATION_RECIPIENT);
    expect(chain.providerDeposit).to.equal(stream.providerDeposit);
    expect(chain.donationDeposit).to.equal(stream.donationDeposit);
    expect(chain.donationBps).to.equal(DEFAULT_DONATION_BPS);
    expect(senderBefore - (await glm.balanceOf(sender.address))).to.equal(
      stream.totalDeposit,
    );
  });

  it("withdraw pays provider and donation recipient", async () => {
    const { sender, recipient, glm, sp } = await fixture();
    const { streamId } = await createGlmStream(sender, recipient, glm, sp);

    await ethers.provider.send("evm_increaseTime", [10]);
    await ethers.provider.send("evm_mine");

    const providerBefore = await glm.balanceOf(recipient.address);
    const donationBefore = await glm.balanceOf(DONATION_RECIPIENT);
    await sp.connect(recipient).withdraw(streamId);
    const providerPayout = (await glm.balanceOf(recipient.address)) - providerBefore;
    const donationPayout =
      (await glm.balanceOf(DONATION_RECIPIENT)) - donationBefore;

    expect(providerPayout).to.be.greaterThanOrEqual(ethers.parseEther("9"));
    expect(providerPayout).to.be.lessThanOrEqual(ethers.parseEther("12"));
    expect(donationPayout).to.equal(
      donationFor(providerPayout, DEFAULT_DONATION_BPS),
    );
  });

  it("supports zero percent donation opt-out", async () => {
    const { sender, recipient, glm, sp } = await fixture();
    const { streamId } = await createGlmStream(sender, recipient, glm, sp, 10n, 0n);

    await ethers.provider.send("evm_increaseTime", [40]);
    await ethers.provider.send("evm_mine");

    const providerBefore = await glm.balanceOf(recipient.address);
    const donationBefore = await glm.balanceOf(DONATION_RECIPIENT);
    await sp.connect(recipient).withdraw(streamId);

    expect((await glm.balanceOf(recipient.address)) - providerBefore).to.equal(
      ethers.parseEther("10"),
    );
    expect(await glm.balanceOf(DONATION_RECIPIENT)).to.equal(donationBefore);
  });

  it("rejects donation above max", async () => {
    const { sender, recipient, glm, sp } = await fixture();
    const providerRate = ethers.parseEther("1");
    const providerDeposit = providerRate * 10n;
    const badBps = MAX_DONATION_BPS + 1n;
    const quote = await leaseQuote(
      sender,
      recipient,
      sp,
      providerDeposit,
      providerRate,
    );
    await glm.connect(sender).approve(await sp.getAddress(), providerDeposit);

    await expect(
      sp
        .connect(sender)
        .createStream(
          recipient.address,
          providerDeposit,
          providerRate,
          badBps,
          quote.leaseId,
          quote.termsHash,
          quote.quoteExpiresAt,
          quote.signature,
        ),
    ).to.be.revertedWith("donation too high");
  });

  it("topUp extends stopTime and charges matching donation", async () => {
    const { sender, recipient, glm, sp } = await fixture();
    const { streamId, providerDeposit } = await createGlmStream(
      sender,
      recipient,
      glm,
      sp,
      10n,
    );
    const s0 = await sp.streams(streamId);
    const donationTopUp = donationFor(providerDeposit, DEFAULT_DONATION_BPS);
    const totalTopUp = providerDeposit + donationTopUp;

    await glm.connect(sender).approve(await sp.getAddress(), totalTopUp);
    await sp.connect(sender).topUp(streamId, providerDeposit);

    const s1 = await sp.streams(streamId);
    expect(s1.stopTime).to.be.greaterThan(s0.stopTime);
    expect(s1.providerDeposit).to.equal(s0.providerDeposit + providerDeposit);
    expect(s1.donationDeposit).to.equal(s0.donationDeposit + donationTopUp);
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
    const { streamId, providerDeposit, totalDeposit } = await createGlmStream(
      sender,
      recipient,
      glm,
      sp,
      10n,
    );

    await ethers.provider.send("evm_increaseTime", [10]);
    await ethers.provider.send("evm_mine");
    expect(await sp.streamState(streamId)).to.equal("grace");

    await glm.connect(sender).approve(await sp.getAddress(), totalDeposit);
    await sp.connect(sender).topUp(streamId, providerDeposit);
    expect(await sp.streamState(streamId)).to.equal("active");

    await ethers.provider.send("evm_increaseTime", [41]);
    await ethers.provider.send("evm_mine");
    expect(await sp.streamState(streamId)).to.equal("expired");

    await glm.connect(sender).approve(await sp.getAddress(), totalDeposit);
    await expect(
      sp.connect(sender).topUp(streamId, providerDeposit),
    ).to.be.revertedWith("stream expired");
  });

  it("reverts invalid params", async () => {
    const { sender, recipient, glm, sp } = await fixture();
    await glm.connect(sender).approve(await sp.getAddress(), ethers.parseEther("1"));

    const quote = await leaseQuote(sender, recipient, sp, 1n, 1n);
    await expect(
      sp
        .connect(sender)
        .createStream(
          recipient.address,
          0,
          1,
          DEFAULT_DONATION_BPS,
          quote.leaseId,
          quote.termsHash,
          quote.quoteExpiresAt,
          quote.signature,
        ),
    ).to.be.revertedWith("deposit=0");
    await expect(
      sp
        .connect(sender)
        .createStream(
          recipient.address,
          1,
          0,
          DEFAULT_DONATION_BPS,
          quote.leaseId,
          quote.termsHash,
          quote.quoteExpiresAt,
          quote.signature,
        ),
    ).to.be.revertedWith("rate=0");
  });

  it("rejects wrong signer, expired quote, reused lease, and allows requestor-selected donation", async () => {
    const { sender, recipient, other, glm, sp } = await fixture();
    const providerRate = ethers.parseEther("1");
    const providerDeposit = providerRate * 10n;
    const totalDeposit =
      providerDeposit + donationFor(providerDeposit, DEFAULT_DONATION_BPS);
    const quote = await leaseQuote(
      sender,
      other,
      sp,
      providerDeposit,
      providerRate,
      "wrong-signer",
    );
    await glm.connect(sender).approve(await sp.getAddress(), totalDeposit);
    await expect(
      sp
        .connect(sender)
        .createStream(
          recipient.address,
          providerDeposit,
          providerRate,
          DEFAULT_DONATION_BPS,
          quote.leaseId,
          quote.termsHash,
          quote.quoteExpiresAt,
          quote.signature,
        ),
    ).to.be.revertedWith("bad provider signature");

    const expired = await leaseQuote(
      sender,
      recipient,
      sp,
      providerDeposit,
      providerRate,
      "expired",
    );
    await ethers.provider.send("evm_increaseTime", [3601]);
    await ethers.provider.send("evm_mine");
    await expect(
      sp
        .connect(sender)
        .createStream(
          recipient.address,
          providerDeposit,
          providerRate,
          DEFAULT_DONATION_BPS,
          expired.leaseId,
          expired.termsHash,
          expired.quoteExpiresAt,
          expired.signature,
        ),
    ).to.be.revertedWith("quote expired");

    const fresh = await leaseQuote(
      sender,
      recipient,
      sp,
      providerDeposit,
      providerRate,
      "reuse",
    );
    await glm.connect(sender).approve(await sp.getAddress(), totalDeposit * 2n);
    await sp
      .connect(sender)
      .createStream(
        recipient.address,
        providerDeposit,
        providerRate,
        DEFAULT_DONATION_BPS,
        fresh.leaseId,
        fresh.termsHash,
        fresh.quoteExpiresAt,
        fresh.signature,
      );
    await expect(
      sp
        .connect(sender)
        .createStream(
          recipient.address,
          providerDeposit,
          providerRate,
          DEFAULT_DONATION_BPS,
          fresh.leaseId,
          fresh.termsHash,
          fresh.quoteExpiresAt,
          fresh.signature,
        ),
    ).to.be.revertedWith("lease used");

    const altered = await leaseQuote(
      sender,
      recipient,
      sp,
      providerDeposit,
      providerRate,
      "altered",
    );
    const tx = await sp
      .connect(sender)
      .createStream(
        recipient.address,
        providerDeposit,
        providerRate,
        0,
        altered.leaseId,
        altered.termsHash,
        altered.quoteExpiresAt,
        altered.signature,
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
      .filter((event) => event?.name === "StreamCreated")[0];
    const chain = await sp.streams(event.args.streamId);
    expect(chain.donationBps).to.equal(0n);
    expect(chain.donationDeposit).to.equal(0n);
  });

  it("terminate settles vested payouts, refunds unvested deposits, and closes stream", async () => {
    const { sender, recipient, glm, sp } = await fixture();
    const { streamId, totalDeposit } = await createGlmStream(
      sender,
      recipient,
      glm,
      sp,
      100n,
    );

    await ethers.provider.send("evm_increaseTime", [10]);
    await ethers.provider.send("evm_mine");

    const senderBefore = await glm.balanceOf(sender.address);
    const recipientBefore = await glm.balanceOf(recipient.address);
    const donationBefore = await glm.balanceOf(DONATION_RECIPIENT);

    await sp.connect(sender).terminate(streamId);

    const senderRefund = (await glm.balanceOf(sender.address)) - senderBefore;
    const providerPayout =
      (await glm.balanceOf(recipient.address)) - recipientBefore;
    const donationPayout =
      (await glm.balanceOf(DONATION_RECIPIENT)) - donationBefore;

    expect(providerPayout).to.be.greaterThanOrEqual(ethers.parseEther("9"));
    expect(providerPayout).to.be.lessThanOrEqual(ethers.parseEther("12"));
    expect(donationPayout).to.equal(
      donationFor(providerPayout, DEFAULT_DONATION_BPS),
    );
    expect(senderRefund + providerPayout + donationPayout).to.equal(totalDeposit);

    await expect(sp.connect(recipient).withdraw(streamId)).to.be.revertedWith(
      "no-stream",
    );
    await glm.connect(sender).approve(await sp.getAddress(), totalDeposit);
    await expect(
      sp.connect(sender).topUp(streamId, totalDeposit),
    ).to.be.revertedWith("no-stream");
  });
});
