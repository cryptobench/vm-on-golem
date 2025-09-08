const fs = require("fs");
const path = require("path");

async function main() {
  const { ethers } = require("hardhat");
  const glm = process.env.GLM_TOKEN_ADDRESS;
  const oracle = process.env.ORACLE_ADDRESS || (await (await ethers.getSigners())[0].getAddress());
  if (!glm) throw new Error("GLM_TOKEN_ADDRESS env var required");

  const StreamPayment = await ethers.getContractFactory("StreamPayment");
  const contract = await StreamPayment.deploy(oracle);
  await contract.waitForDeployment();
  const address = await contract.getAddress();
  console.log("StreamPayment deployed to:", address);

  const outDir = path.join(__dirname, "..", "deployments");
  fs.mkdirSync(outDir, { recursive: true });
  const outFile = path.join(outDir, "polygon.json");
  const payload = {
    network: "polygon",
    timestamp: new Date().toISOString(),
    StreamPayment: {
      address,
      oracle,
      glmToken: glm
    }
  };
  fs.writeFileSync(outFile, JSON.stringify(payload, null, 2));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

