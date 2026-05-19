import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { network } from "hardhat";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function main() {
  const { ethers } = await network.create();
  const [deployer] = await ethers.getSigners();

  console.log("Deploying MockGLM with deployer:", await deployer.getAddress());
  const MockGLM = await ethers.getContractFactory("MockGLM");
  const glm = await MockGLM.deploy();
  await glm.waitForDeployment();
  const glmAddress = await glm.getAddress();
  console.log("MockGLM deployed to:", glmAddress);

  const amount = ethers.parseEther("1000000");
  const mintTx = await glm.mint(await deployer.getAddress(), amount);
  await mintTx.wait();
  console.log("Minted", amount.toString(), "base units to", await deployer.getAddress());

  const outDir = path.join(__dirname, "..", "deployments");
  fs.mkdirSync(outDir, { recursive: true });
  const netName = process.env.HARDHAT_NETWORK || "unknown";
  const outFile = path.join(outDir, `${netName}-mockglm.json`);
  const payload = {
    network: netName,
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
