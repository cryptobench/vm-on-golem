import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { network } from "hardhat";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_DONATION_RECIPIENT = "0x94153E31AA476cE30C3AF64C255C623f80920BfF";

async function main() {
  const connection = await network.create();
  const { ethers } = connection;
  const glm = process.env.GLM_TOKEN_ADDRESS;
  if (!glm) {
    throw new Error("GLM_TOKEN_ADDRESS is required for GLM-only StreamPayment deployment");
  }
  const donationRecipient =
    process.env.DONATION_RECIPIENT || DEFAULT_DONATION_RECIPIENT;

  const StreamPayment = await ethers.getContractFactory("StreamPayment");
  const contract = await StreamPayment.deploy(glm, donationRecipient);
  await contract.waitForDeployment();
  const address = await contract.getAddress();
  console.log("StreamPayment deployed to:", address);

  const outDir = path.join(__dirname, "..", "deployments");
  fs.mkdirSync(outDir, { recursive: true });
  const netName =
    process.env.HARDHAT_NETWORK ||
    connection.networkName ||
    connection.network?.name ||
    network.name ||
    "unknown";
  const outFile = path.join(outDir, `${netName}.json`);
  const payload = {
    network: netName,
    timestamp: new Date().toISOString(),
    StreamPayment: {
      address,
      paymentToken: glm,
      glmToken: glm,
      donationRecipient
    }
  };
  fs.writeFileSync(outFile, JSON.stringify(payload, null, 2));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
