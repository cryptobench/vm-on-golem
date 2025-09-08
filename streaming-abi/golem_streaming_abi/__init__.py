STREAM_PAYMENT_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "token", "type": "address"},
            {"internalType": "address", "name": "recipient", "type": "address"},
            {"internalType": "uint256", "name": "deposit", "type": "uint256"},
            {"internalType": "uint128", "name": "ratePerSecond", "type": "uint128"},
        ],
        "name": "createStream",
        "outputs": [{"internalType": "uint256", "name": "streamId", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "streamId", "type": "uint256"}],
        "name": "withdraw",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "streamId", "type": "uint256"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "topUp",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "streamId", "type": "uint256"}],
        "name": "terminate",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "name": "streams",
        "outputs": [
            {"internalType": "address", "name": "token", "type": "address"},
            {"internalType": "address", "name": "sender", "type": "address"},
            {"internalType": "address", "name": "recipient", "type": "address"},
            {"internalType": "uint128", "name": "startTime", "type": "uint128"},
            {"internalType": "uint128", "name": "stopTime", "type": "uint128"},
            {"internalType": "uint128", "name": "ratePerSecond", "type": "uint128"},
            {"internalType": "uint256", "name": "deposit", "type": "uint256"},
            {"internalType": "uint256", "name": "withdrawn", "type": "uint256"},
            {"internalType": "bool", "name": "halted", "type": "bool"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "streamId", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "sender", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "recipient", "type": "address"},
            {"indexed": False, "internalType": "address", "name": "token", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "deposit", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "ratePerSecond", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "startTime", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "stopTime", "type": "uint256"},
        ],
        "name": "StreamCreated",
        "type": "event",
    },
]

ERC20_ABI = [
    {
        "name": "approve",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "name": "allowance",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"},
        ],
        "outputs": [{"name": "", "type": "uint256"}],
    },
]

__all__ = ["STREAM_PAYMENT_ABI", "ERC20_ABI"]

