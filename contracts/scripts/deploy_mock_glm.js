const fs = require("fs");
const path = require("path");

async function main() {
  const { ethers } = require("hardhat");
  const [deployer] = await ethers.getSigners();

  console.log("Deploying MockGLM with deployer:", await deployer.getAddress());
  const MockGLM = await ethers.getContractFactory("MockGLM");
  const glm = await MockGLM.deploy();
  await glm.waitForDeployment();
  const glmAddress = await glm.getAddress();
  console.log("MockGLM deployed to:", glmAddress);

  // Optionally mint initial supply to the deployer (1,000,000 GLM)
  const amount = ethers.parseEther("1000000");
  const mintTx = await glm.mint(await deployer.getAddress(), amount);
  await mintTx.wait();
  console.log("Minted", amount.toString(), "wei to", await deployer.getAddress());

  const outDir = path.join(__dirname, "..", "deployments");
  fs.mkdirSync(outDir, { recursive: true });
  const network = (process.env.HARDHAT_NETWORK || "ethwarsaw").toLowerCase();
  const outFile = path.join(outDir, `${network}-mockglm.json`);
  const payload = {
    network,
    timestamp: new Date().toISOString(),
    MockGLM: {
      address: glmAddress,
      initialHolder: await deployer.getAddress(),
      initialMintWei: amount.toString(),
    },
  };
  fs.writeFileSync(outFile, JSON.stringify(payload, null, 2));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

