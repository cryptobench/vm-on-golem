// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

/**
 * @title StreamPayment
 * @notice Minimal EIP-1620-inspired streaming payments for GLM.
 *         Sender deposits GLM up-front; recipient withdraws vested amount over time.
 *         Sender/recipient can terminate. Stream creation is bound to a
 *         provider-signed lease quote.
 */
contract StreamPayment {
    bytes32 private constant LEASE_QUOTE_TYPEHASH = keccak256(
        "LeaseQuote(address recipient,uint256 deposit,uint128 ratePerSecond,bytes32 leaseId,bytes32 termsHash,uint128 quoteExpiresAt)"
    );
    bytes32 private constant DOMAIN_TYPEHASH = keccak256(
        "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
    );
    bytes32 private constant NAME_HASH = keccak256("GolemStreamPayment");
    bytes32 private constant VERSION_HASH = keccak256("2");

    struct Stream {
        address token;           // GLM token address
        address sender;          // Requestor paying
        address recipient;       // Provider receiving
        uint128 startTime;       // Stream start
        uint128 stopTime;        // Stream end (derived from deposit/rate)
        uint128 ratePerSecond;   // GLM base units per second
        uint256 deposit;         // Total deposited (<= (stop-start)*rate)
        uint256 withdrawn;       // Amount already withdrawn by recipient
        bytes32 leaseId;         // Provider-unique lease identifier
        bytes32 termsHash;       // Provider-signed canonical VM/payment terms
    }

    address public immutable glmToken;
    uint256 public nextStreamId;
    mapping(uint256 => Stream) public streams;
    mapping(bytes32 => bool) public usedLeaseIds;

    event StreamCreated(uint256 indexed streamId, address indexed sender, address indexed recipient, address token, uint256 deposit, uint256 ratePerSecond, uint256 startTime, uint256 stopTime, bytes32 leaseId, bytes32 termsHash);
    event Withdraw(uint256 indexed streamId, address indexed recipient, uint256 amount);
    event Terminated(uint256 indexed streamId, uint256 senderRefund, uint256 recipientPayout);
    event ToppedUp(uint256 indexed streamId, uint256 amount, uint128 newStopTime);

    constructor(address _glmToken) {
        require(_glmToken != address(0), "glm=0");
        glmToken = _glmToken;
    }

    /**
     * @notice Create a GLM stream. Caller must approve `deposit` GLM beforehand.
     * @param recipient Provider address that will receive the stream
     * @param deposit Total GLM base units to be streamed
     * @param ratePerSecond GLM base units per second
     * @param leaseId Provider-generated unique lease identifier
     * @param termsHash Provider-generated canonical hash of VM/payment terms
     * @param quoteExpiresAt Latest timestamp where the quote can be used
     * @param providerSignature EIP-712 signature from `recipient`
     */
    function createStream(
        address recipient,
        uint256 deposit,
        uint128 ratePerSecond,
        bytes32 leaseId,
        bytes32 termsHash,
        uint128 quoteExpiresAt,
        bytes calldata providerSignature
    ) external returns (uint256 streamId) {
        require(recipient != address(0), "recipient=0");
        require(deposit > 0, "deposit=0");
        require(ratePerSecond > 0, "rate=0");
        require(leaseId != bytes32(0), "lease=0");
        require(termsHash != bytes32(0), "terms=0");
        require(block.timestamp <= quoteExpiresAt, "quote expired");
        require(!usedLeaseIds[leaseId], "lease used");
        require(
            _recoverLeaseSigner(
                recipient,
                deposit,
                ratePerSecond,
                leaseId,
                termsHash,
                quoteExpiresAt,
                providerSignature
            ) == recipient,
            "bad provider signature"
        );

        uint128 start = uint128(block.timestamp);
        // Compute duration and stop time; require exact division or allow remainder to be rounded down
        uint256 duration = deposit / uint256(ratePerSecond);
        require(duration > 0, "duration=0");
        uint128 stop = start + uint128(duration);

        usedLeaseIds[leaseId] = true;
        require(IERC20(glmToken).transferFrom(msg.sender, address(this), deposit), "transferFrom failed");

        streamId = ++nextStreamId;
        streams[streamId] = Stream({
            token: glmToken,
            sender: msg.sender,
            recipient: recipient,
            startTime: start,
            stopTime: stop,
            ratePerSecond: ratePerSecond,
            deposit: deposit,
            withdrawn: 0,
            leaseId: leaseId,
            termsHash: termsHash
        });

        emit StreamCreated(streamId, msg.sender, recipient, glmToken, deposit, ratePerSecond, start, stop, leaseId, termsHash);
    }

    function _effectiveTime(Stream memory s) internal view returns (uint128) {
        uint128 t = uint128(block.timestamp);
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
        require(IERC20(s.token).transfer(s.recipient, amount), "transfer failed");
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

        if (owedToRecipient > 0) {
            require(IERC20(token).transfer(recipient, owedToRecipient), "transfer payout failed");
        }
        if (refundToSender > 0) {
            require(IERC20(token).transfer(sender, refundToSender), "transfer refund failed");
        }
        emit Terminated(streamId, refundToSender, owedToRecipient);
    }

    /**
     * @notice Top up an existing stream by increasing the deposit and extending stopTime accordingly.
     *         Caller must be the original sender and must approve `amount` GLM.
     */
    function topUp(uint256 streamId, uint256 amount) external {
        Stream storage s = streams[streamId];
        require(s.recipient != address(0), "no-stream");
        require(msg.sender == s.sender, "not sender");
        require(amount > 0, "amount=0");
        require(s.token == glmToken, "token != GLM");
        require(IERC20(s.token).transferFrom(msg.sender, address(this), amount), "transferFrom failed");
        s.deposit += amount;
        // Extend stopTime by amount / rate
        uint128 delta = uint128(amount / uint256(s.ratePerSecond));
        require(delta > 0, "delta=0");
        // stopTime must be >= now
        uint128 base = s.stopTime < uint128(block.timestamp) ? uint128(block.timestamp) : s.stopTime;
        s.stopTime = base + delta;
        emit ToppedUp(streamId, amount, s.stopTime);
    }

    function _domainSeparator() internal view returns (bytes32) {
        return keccak256(
            abi.encode(
                DOMAIN_TYPEHASH,
                NAME_HASH,
                VERSION_HASH,
                block.chainid,
                address(this)
            )
        );
    }

    function _recoverLeaseSigner(
        address recipient,
        uint256 deposit,
        uint128 ratePerSecond,
        bytes32 leaseId,
        bytes32 termsHash,
        uint128 quoteExpiresAt,
        bytes calldata signature
    ) internal view returns (address) {
        require(signature.length == 65, "bad signature length");
        bytes32 structHash = keccak256(
            abi.encode(
                LEASE_QUOTE_TYPEHASH,
                recipient,
                deposit,
                ratePerSecond,
                leaseId,
                termsHash,
                quoteExpiresAt
            )
        );
        bytes32 digest = keccak256(
            abi.encodePacked("\x19\x01", _domainSeparator(), structHash)
        );

        bytes32 r;
        bytes32 s;
        uint8 v;
        assembly {
            r := calldataload(signature.offset)
            s := calldataload(add(signature.offset, 32))
            v := byte(0, calldataload(add(signature.offset, 64)))
        }
        if (v < 27) {
            v += 27;
        }
        require(v == 27 || v == 28, "bad signature v");
        return ecrecover(digest, v, r, s);
    }
}
