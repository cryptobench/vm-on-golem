StreamPayment

This package provides a minimal GLM streaming payments contract.

- Rate-per-second vesting funded up front with GLM
- Recipient can withdraw vested funds
- Sender or recipient can terminate and settle the stream
- Oracle can halt a stream
- Sender can extend runtime with `topUp(streamId, amount)`

The contract is deployed with one GLM ERC20 address and only accepts streams
for that token.

Core interfaces

- `createStream(address token, address recipient, uint256 deposit, uint128 ratePerSecond) -> streamId`
  - `token` must match the deployed GLM token address
  - caller must approve `deposit` GLM before calling
- `withdraw(uint256 streamId)`
- `terminate(uint256 streamId)`
- `haltStream(uint256 streamId)`
- `topUp(uint256 streamId, uint256 amount)`
  - caller must approve `amount` GLM before calling
- `streams(uint256 id) -> (token, sender, recipient, startTime, stopTime, ratePerSecond, deposit, withdrawn, halted)`

Recommended flow

1. Requestor computes `ratePerSecond` in GLM base units from provider USD pricing and current GLM/USD.
2. Requestor approves and deposits initial GLM coverage, for example `rate * 3600` for one hour.
3. Requestor calls provider `POST /api/v1/vms` with `stream_id`.
4. Requestor can call `topUp` periodically to keep the rental running.
5. Provider withdraws vested GLM and stops VMs when stream runway is too low.

Deployment

Install dependencies:

```bash
npm install
```

Deploy to Ethereum Sepolia:

```bash
SEPOLIA_RPC_URL=https://rpc.sepolia.org \
GLM_TOKEN_ADDRESS=0x... \
PRIVATE_KEY=0x... \
npx hardhat run scripts/deploy.js --network sepolia
```

Deploy to Ethereum Hoodi using tGLM:

```bash
HOODI_RPC_URL=https://ethereum-hoodi-rpc.publicnode.com \
GLM_TOKEN_ADDRESS=0x55555555555556AcFf9C332Ed151758858bd7a26 \
PRIVATE_KEY=0x... \
npx hardhat run scripts/deploy.js --network hoodi
```

Acquire Hoodi test funds:

1. Fund the deployer/requestor wallet with Hoodi ETH for gas. Faucet links are
   published at `https://www.hoodi.dev/`.
2. Mint Hoodi tGLM by calling `create()` on the tGLM minter contract
   `0x500F965199C63865A3E666cA3fF55B64F1c8Bc8b`. Each successful call mints
   `1000` tGLM to the caller.

```bash
PRIVATE_KEY=0x... node - <<'NODE'
(async () => {
  const { ethers } = require("ethers");

  const rpc = "https://ethereum-hoodi-rpc.publicnode.com";
  const provider = new ethers.JsonRpcProvider(rpc);
  const wallet = new ethers.Wallet(process.env.PRIVATE_KEY, provider);

  const minter = new ethers.Contract(
    "0x500F965199C63865A3E666cA3fF55B64F1c8Bc8b",
    ["function create() external"],
    wallet,
  );

  const tx = await minter.create();
  console.log("mint tx:", tx.hash);
  await tx.wait();

  const glm = new ethers.Contract(
    "0x55555555555556AcFf9C332Ed151758858bd7a26",
    ["function balanceOf(address) view returns (uint256)"],
    provider,
  );

  console.log("tGLM:", ethers.formatEther(await glm.balanceOf(wallet.address)));
})().catch((error) => {
  console.error(error.shortMessage || error.message);
  process.exit(1);
});
NODE
```

Verify on Hoodi Etherscan:

```bash
ETHERSCAN_API_KEY=... \
npx hardhat verify --network hoodi <StreamPaymentAddress> \
  <OracleAddress> 0x55555555555556AcFf9C332Ed151758858bd7a26
```

Deploy to Arkiv L2 Hoodi:

```bash
L2_RPC_URL=https://l2.hoodi.arkiv.network/rpc \
L2_CHAIN_ID=393530 \
GLM_TOKEN_ADDRESS=0x... \
PRIVATE_KEY=0x... \
npx hardhat run scripts/deploy.js --network l2
```

For local/test networks without a GLM token, deploy `MockGLM` first and pass
its address as `GLM_TOKEN_ADDRESS`:

```bash
npx hardhat run scripts/deploy_mock_glm.js --network l2
```

Deployment info is written to `contracts/deployments/<network>.json`.

Network notes

- Sepolia chain ID: `11155111` (`0xaa36a7`)
- Sepolia explorer: `https://sepolia.etherscan.io`
- Ethereum Hoodi chain ID: `560048` (`0x88bb0`)
- Ethereum Hoodi GLM token: `0x55555555555556AcFf9C332Ed151758858bd7a26`
- Ethereum Hoodi tGLM minter: `0x500F965199C63865A3E666cA3fF55B64F1c8Bc8b`
- Ethereum Hoodi explorer: `https://hoodi.etherscan.io`
- Arkiv L2 Hoodi chain ID: `393530` (`0x6013a`)
- Arkiv L2 Hoodi explorer: `https://explorer.l2.hoodi.arkiv.network`
