const fs = require("fs");
const path = require("path");

async function main() {
  const hre = require("hardhat");
  const { ethers, network } = hre;
  const glm = process.env.GLM_TOKEN_ADDRESS || "0x0000000000000000000000000000000000000000";
  const oracle = process.env.ORACLE_ADDRESS || (await (await ethers.getSigners())[0].getAddress());

  const StreamPayment = await ethers.getContractFactory("StreamPayment");
  const contract = await StreamPayment.deploy(oracle);
  await contract.waitForDeployment();
  const address = await contract.getAddress();
  console.log("StreamPayment deployed to:", address);

  const outDir = path.join(__dirname, "..", "deployments");
  fs.mkdirSync(outDir, { recursive: true });
  const netName = (network && network.name) ? network.name.toLowerCase() : (process.env.HARDHAT_NETWORK || "unknown");
  const outFile = path.join(outDir, `${netName}.json`);
  const payload = {
    network: netName,
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
