import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { network } from "hardhat";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function main() {
  const { ethers } = await network.create();
  const glm = process.env.GLM_TOKEN_ADDRESS;
  if (!glm) {
    throw new Error("GLM_TOKEN_ADDRESS is required for GLM-only StreamPayment deployment");
  }
  const oracle = process.env.ORACLE_ADDRESS || (await (await ethers.getSigners())[0].getAddress());

  const StreamPayment = await ethers.getContractFactory("StreamPayment");
  const contract = await StreamPayment.deploy(oracle, glm);
  await contract.waitForDeployment();
  const address = await contract.getAddress();
  console.log("StreamPayment deployed to:", address);

  const outDir = path.join(__dirname, "..", "deployments");
  fs.mkdirSync(outDir, { recursive: true });
  const netName = process.env.HARDHAT_NETWORK || "unknown";
  const outFile = path.join(outDir, `${netName}.json`);
  const payload = {
    network: netName,
    timestamp: new Date().toISOString(),
    StreamPayment: {
      address,
      oracle,
      paymentToken: glm,
      glmToken: glm
    }
  };
  fs.writeFileSync(outFile, JSON.stringify(payload, null, 2));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
