StreamPayment

This package provides a minimal GLM streaming payments contract.

- Provider rate-per-second vesting funded up front with GLM
- Requestor-paid donation can be added on top of the provider price
- Provider and donation recipient can withdraw vested funds
- Sender or recipient can terminate and settle the stream
- Sender can extend runtime with `topUp(streamId, providerAmount)` while the stream is active or inside the 30-second grace period

The contract is deployed with one GLM ERC20 address and one immutable donation
recipient. The current donation recipient is
`0x94153E31AA476cE30C3AF64C255C623f80920BfF`.

Core interfaces

- `createStream(address recipient, uint256 providerDeposit, uint128 providerRatePerSecond, uint16 donationBps, bytes32 leaseId, bytes32 termsHash, uint128 quoteExpiresAt, bytes providerSignature) -> streamId`
  - provider signature authorizes only the V4 provider lease terms: recipient, provider deposit, provider rate, lease id, terms hash, and quote expiry
  - `leaseId` must be unique
  - caller must approve `providerDeposit + donationDeposit` GLM before calling
  - requestor-supplied `donationBps` must be between `0` and `1000`; `0` opts out
- `withdraw(uint256 streamId)`
- `terminate(uint256 streamId)`
- `streamState(uint256 streamId) -> active|grace|expired|terminated`
- `topUp(uint256 streamId, uint256 providerAmount)`
  - caller must approve `providerAmount + donationAmount` GLM before calling
  - reverts once `streamState` is `expired` or `terminated`
- `streams(uint256 id) -> (token, sender, recipient, startTime, stopTime, providerRatePerSecond, providerDeposit, providerWithdrawn, donationBps, donationRecipient, donationDeposit, donationWithdrawn, leaseId, termsHash)`

Recommended flow

1. Requestor fetches a provider-signed lease quote from `POST /api/v1/payments/lease-quotes`.
2. Requestor applies its own donation setting, then approves and deposits provider GLM coverage plus the computed donation.
3. Requestor calls provider `POST /api/v1/vms` with `stream_id`, `lease_id`, `terms_hash`, and provider rate.
4. Requestor can call `topUp` periodically to keep the rental running; late top-ups are accepted for 30 seconds after `stopTime`.
5. Stopping a VM does not settle payment; billing continues while the stream remains active.
6. Terminating a rental calls `terminate(streamId)`, paying vested provider and donation GLM and refunding unvested deposits to the requestor.
7. Provider can withdraw vested GLM during active, grace, or expired rentals and deletes VMs when streams expire or terminate.

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
HOODI_RPC_URL=https://rpc.hoodi.ethpandaops.io \
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

  const rpc = "https://rpc.hoodi.ethpandaops.io";
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

Deploy to Ethereum Hoodi:

```bash
HOODI_RPC_URL=https://rpc.hoodi.ethpandaops.io \
GLM_TOKEN_ADDRESS=0x... \
PRIVATE_KEY=0x... \
npx hardhat run scripts/deploy.js --network hoodi
```

For local/test networks without a GLM token, deploy `MockGLM` first and pass
its address as `GLM_TOKEN_ADDRESS`:

```bash
npx hardhat run scripts/deploy_mock_glm.js --network hoodi
```

Deployment info is written to `contracts/deployments/<network>.json`.
After changing Solidity, run `npm --prefix contracts run build`,
`npm run abi:sync`, and `npm run abi:check`. Provider and requestor ABIs are
generated from `contracts/artifacts/contracts/StreamPayment.sol/StreamPayment.json`
and must not be hand-edited.

Network notes

- Sepolia chain ID: `11155111` (`0xaa36a7`)
- Sepolia explorer: `https://sepolia.etherscan.io`
- Ethereum Hoodi chain ID: `560048` (`0x88bb0`)
- Ethereum Hoodi GLM token: `0x55555555555556AcFf9C332Ed151758858bd7a26`
- Ethereum Hoodi tGLM minter: `0x500F965199C63865A3E666cA3fF55B64F1c8Bc8b`
- Ethereum Hoodi explorer: `https://hoodi.etherscan.io`
