// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
    function allowance(address owner, address spender) external view returns (uint256);
    function approve(address spender, uint256 amount) external returns (bool);
}

/**
 * @title StreamPayment
 * @notice Minimal EIP-1620-inspired streaming payments for GLM.
 *         Sender deposits GLM up-front; recipient withdraws vested amount over time.
 *         Oracle can halt a stream (emergency stop). Sender/recipient can terminate.
 */
contract StreamPayment {
    struct Stream {
        address token;           // GLM token address
        address sender;          // Requestor paying
        address recipient;       // Provider receiving
        uint128 startTime;       // Stream start
        uint128 stopTime;        // Stream end (derived from deposit/rate)
        uint128 ratePerSecond;   // GLM per second (18 decimals)
        uint256 deposit;         // Total deposited (<= (stop-start)*rate)
        uint256 withdrawn;       // Amount already withdrawn by recipient
        bool halted;             // True if oracle halted the stream
    }

    address public immutable oracle;
    uint256 public nextStreamId;
    mapping(uint256 => Stream) public streams;

    event StreamCreated(uint256 indexed streamId, address indexed sender, address indexed recipient, address token, uint256 deposit, uint256 ratePerSecond, uint256 startTime, uint256 stopTime);
    event Withdraw(uint256 indexed streamId, address indexed recipient, uint256 amount);
    event Terminated(uint256 indexed streamId, uint256 senderRefund, uint256 recipientPayout);
    event Halted(uint256 indexed streamId);
    event ToppedUp(uint256 indexed streamId, uint256 amount, uint128 newStopTime);

    modifier onlyOracle() {
        require(msg.sender == oracle, "not oracle");
        _;
    }

    constructor(address _oracle) {
        require(_oracle != address(0), "oracle=0");
        oracle = _oracle;
    }

    /**
     * @notice Create a stream. In ERC20 mode, caller must approve `deposit` tokens beforehand.
     *         In native ETH mode (token=address(0)), send `deposit` as msg.value.
     * @param token ERC20 token address or address(0) for native ETH
     * @param recipient Provider address that will receive the stream
     * @param deposit Total amount to be streamed (18 decimals)
     * @param ratePerSecond Tokens per second (18 decimals)
     */
    function createStream(address token, address recipient, uint256 deposit, uint128 ratePerSecond) external payable returns (uint256 streamId) {
        require(recipient != address(0), "recipient=0");
        require(deposit > 0, "deposit=0");
        require(ratePerSecond > 0, "rate=0");

        uint128 start = uint128(block.timestamp);
        // Compute duration and stop time; require exact division or allow remainder to be rounded down
        uint256 duration = deposit / uint256(ratePerSecond);
        require(duration > 0, "duration=0");
        uint128 stop = start + uint128(duration);

        if (token == address(0)) {
            // Native ETH mode: deposit must be sent as value
            require(msg.value == deposit, "value != deposit");
        } else {
            // ERC20 mode: pull funds
            require(IERC20(token).transferFrom(msg.sender, address(this), deposit), "transferFrom failed");
        }

        streamId = ++nextStreamId;
        streams[streamId] = Stream({
            token: token,
            sender: msg.sender,
            recipient: recipient,
            startTime: start,
            stopTime: stop,
            ratePerSecond: ratePerSecond,
            deposit: deposit,
            withdrawn: 0,
            halted: false
        });

        emit StreamCreated(streamId, msg.sender, recipient, token, deposit, ratePerSecond, start, stop);
    }

    function _effectiveTime(Stream memory s) internal view returns (uint128) {
        uint128 t = uint128(block.timestamp);
        if (s.halted && t > s.stopTime) {
            // If halted after stopTime, normal stop applies anyway
            return s.stopTime;
        }
        if (s.halted) {
            // Treat current time as when it was halted (no further vesting after halt)
            // We can't store haltTime without additional state; for minimalism, on halt we clamp stopTime to now
            // so reading here is consistent. This is implemented in haltStream below.
            return s.stopTime;
        }
        if (t <= s.startTime) return s.startTime;
        if (t >= s.stopTime) return s.stopTime;
        return t;
    }

    function _vested(Stream memory s) internal view returns (uint256) {
        uint128 t = _effectiveTime(s);
        if (t <= s.startTime) return 0;
        uint256 elapsed = uint256(t - s.startTime);
        uint256 vested = elapsed * uint256(s.ratePerSecond);
        if (vested > s.deposit) vested = s.deposit;
        return vested;
    }

    function withdraw(uint256 streamId) external {
        Stream storage s = streams[streamId];
        require(s.recipient != address(0), "no-stream");
        require(msg.sender == s.recipient, "not recipient");
        uint256 vested = _vested(s);
        uint256 amount = vested - s.withdrawn;
        require(amount > 0, "nothing to withdraw");
        s.withdrawn += amount;
        if (s.token == address(0)) {
            (bool ok, ) = payable(s.recipient).call{value: amount}("");
            require(ok, "eth transfer failed");
        } else {
            require(IERC20(s.token).transfer(s.recipient, amount), "transfer failed");
        }
        emit Withdraw(streamId, s.recipient, amount);
    }

    function terminate(uint256 streamId) external {
        Stream storage s = streams[streamId];
        require(s.recipient != address(0), "no-stream");
        require(msg.sender == s.sender || msg.sender == s.recipient, "not authorized");

        uint256 vested = _vested(s);
        uint256 owedToRecipient = vested - s.withdrawn;
        uint256 refundToSender = s.deposit - vested;

        // Clear storage first to prevent reentrancy effects on accounting
        address token = s.token;
        address recipient = s.recipient;
        address sender = s.sender;
        s.recipient = address(0);

        if (token == address(0)) {
            if (owedToRecipient > 0) {
                (bool ok1, ) = payable(recipient).call{value: owedToRecipient}("");
                require(ok1, "eth payout failed");
            }
            if (refundToSender > 0) {
                (bool ok2, ) = payable(sender).call{value: refundToSender}("");
                require(ok2, "eth refund failed");
            }
        } else {
            if (owedToRecipient > 0) {
                require(IERC20(token).transfer(recipient, owedToRecipient), "transfer payout failed");
            }
            if (refundToSender > 0) {
                require(IERC20(token).transfer(sender, refundToSender), "transfer refund failed");
            }
        }
        emit Terminated(streamId, refundToSender, owedToRecipient);
    }

    function haltStream(uint256 streamId) external onlyOracle {
        Stream storage s = streams[streamId];
        require(s.recipient != address(0), "no-stream");
        if (!s.halted) {
            s.halted = true;
            // Clamp stopTime to now to stop further vesting deterministically
            uint128 nowTs = uint128(block.timestamp);
            if (nowTs < s.stopTime) {
                s.stopTime = nowTs;
            }
            emit Halted(streamId);
        }
    }

    /**
     * @notice Top up an existing stream by increasing the deposit and extending stopTime accordingly.
     *         Caller must be the original sender and must have approved `amount` GLM.
     */
    function topUp(uint256 streamId, uint256 amount) external payable {
        Stream storage s = streams[streamId];
        require(s.recipient != address(0), "no-stream");
        require(!s.halted, "halted");
        require(msg.sender == s.sender, "not sender");
        require(amount > 0, "amount=0");
        if (s.token == address(0)) {
            require(msg.value == amount, "value != amount");
        } else {
            require(IERC20(s.token).transferFrom(msg.sender, address(this), amount), "transferFrom failed");
        }
        s.deposit += amount;
        // Extend stopTime by amount / rate
        uint128 delta = uint128(amount / uint256(s.ratePerSecond));
        require(delta > 0, "delta=0");
        // stopTime must be >= now
        uint128 base = s.stopTime < uint128(block.timestamp) ? uint128(block.timestamp) : s.stopTime;
        s.stopTime = base + delta;
        emit ToppedUp(streamId, amount, s.stopTime);
    }
}
