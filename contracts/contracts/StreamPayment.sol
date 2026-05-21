// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

/**
 * @title StreamPayment
 * @notice GLM streaming payments with requestor-paid donation support.
 *         Sender deposits provider funds plus an optional donation up front.
 *         Provider and donation recipient receive vested funds over time.
 *         Stream creation is bound to a provider-signed lease quote.
 */
contract StreamPayment {
    uint128 public constant GRACE_PERIOD_SECONDS = 30;
    uint16 public constant MAX_DONATION_BPS = 1000;

    enum StreamState {
        Active,
        Grace,
        Expired,
        Terminated
    }

    bytes32 private constant LEASE_QUOTE_TYPEHASH = keccak256(
        "LeaseQuote(address recipient,uint256 providerDeposit,uint128 providerRatePerSecond,bytes32 leaseId,bytes32 termsHash,uint128 quoteExpiresAt)"
    );
    bytes32 private constant DOMAIN_TYPEHASH = keccak256(
        "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
    );
    bytes32 private constant NAME_HASH = keccak256("GolemStreamPayment");
    bytes32 private constant VERSION_HASH = keccak256("4");

    struct Stream {
        address token;
        address sender;
        address recipient;
        uint128 startTime;
        uint128 stopTime;
        uint128 providerRatePerSecond;
        uint256 providerDeposit;
        uint256 providerWithdrawn;
        uint16 donationBps;
        address donationRecipient;
        uint256 donationDeposit;
        uint256 donationWithdrawn;
        bytes32 leaseId;
        bytes32 termsHash;
    }

    address public immutable glmToken;
    address public immutable donationRecipient;
    uint256 public nextStreamId;
    mapping(uint256 => Stream) public streams;
    mapping(bytes32 => bool) public usedLeaseIds;

    event StreamCreated(
        uint256 indexed streamId,
        address indexed sender,
        address indexed recipient,
        address token,
        uint256 providerDeposit,
        uint256 donationDeposit,
        uint256 totalDeposit,
        uint256 providerRatePerSecond,
        uint16 donationBps,
        address donationRecipient,
        uint256 startTime,
        uint256 stopTime,
        bytes32 leaseId,
        bytes32 termsHash
    );
    event Withdraw(
        uint256 indexed streamId,
        address indexed recipient,
        uint256 providerAmount,
        address indexed donationRecipient,
        uint256 donationAmount
    );
    event Terminated(
        uint256 indexed streamId,
        uint256 senderRefund,
        uint256 providerPayout,
        uint256 donationPayout
    );
    event ToppedUp(
        uint256 indexed streamId,
        uint256 providerAmount,
        uint256 donationAmount,
        uint256 totalAmount,
        uint128 newStopTime
    );

    constructor(address _glmToken, address _donationRecipient) {
        require(_glmToken != address(0), "glm=0");
        require(_donationRecipient != address(0), "donation recipient=0");
        glmToken = _glmToken;
        donationRecipient = _donationRecipient;
    }

    /**
     * @notice Create a GLM stream. Caller must approve providerDeposit plus donation.
     * @param recipient Provider address that will receive the base stream
     * @param providerDeposit GLM base units streamed to the provider
     * @param providerRatePerSecond Provider GLM base units per second
     * @param donationBps Requestor-paid donation basis points, 0-1000
     * @param leaseId Provider-generated unique lease identifier
     * @param termsHash Provider-generated canonical hash of VM/payment terms
     * @param quoteExpiresAt Latest timestamp where the quote can be used
     * @param providerSignature EIP-712 signature from `recipient`
     */
    function createStream(
        address recipient,
        uint256 providerDeposit,
        uint128 providerRatePerSecond,
        uint16 donationBps,
        bytes32 leaseId,
        bytes32 termsHash,
        uint128 quoteExpiresAt,
        bytes calldata providerSignature
    ) external returns (uint256 streamId) {
        require(recipient != address(0), "recipient=0");
        require(providerDeposit > 0, "deposit=0");
        require(providerRatePerSecond > 0, "rate=0");
        require(donationBps <= MAX_DONATION_BPS, "donation too high");
        require(leaseId != bytes32(0), "lease=0");
        require(termsHash != bytes32(0), "terms=0");
        require(block.timestamp <= quoteExpiresAt, "quote expired");
        require(!usedLeaseIds[leaseId], "lease used");
        require(
            _recoverLeaseSigner(
                recipient,
                providerDeposit,
                providerRatePerSecond,
                leaseId,
                termsHash,
                quoteExpiresAt,
                providerSignature
            ) == recipient,
            "bad provider signature"
        );

        uint128 start = uint128(block.timestamp);
        uint256 duration = providerDeposit / uint256(providerRatePerSecond);
        require(duration > 0, "duration=0");
        uint128 stop = start + uint128(duration);

        uint256 donationDeposit = _donationFor(providerDeposit, donationBps);
        uint256 totalDeposit = providerDeposit + donationDeposit;

        usedLeaseIds[leaseId] = true;
        require(IERC20(glmToken).transferFrom(msg.sender, address(this), totalDeposit), "transferFrom failed");

        streamId = ++nextStreamId;
        streams[streamId] = Stream({
            token: glmToken,
            sender: msg.sender,
            recipient: recipient,
            startTime: start,
            stopTime: stop,
            providerRatePerSecond: providerRatePerSecond,
            providerDeposit: providerDeposit,
            providerWithdrawn: 0,
            donationBps: donationBps,
            donationRecipient: donationRecipient,
            donationDeposit: donationDeposit,
            donationWithdrawn: 0,
            leaseId: leaseId,
            termsHash: termsHash
        });

        emit StreamCreated(
            streamId,
            msg.sender,
            recipient,
            glmToken,
            providerDeposit,
            donationDeposit,
            totalDeposit,
            providerRatePerSecond,
            donationBps,
            donationRecipient,
            start,
            stop,
            leaseId,
            termsHash
        );
    }

    function _effectiveTime(Stream memory s) internal view returns (uint128) {
        uint128 t = uint128(block.timestamp);
        if (t <= s.startTime) return s.startTime;
        if (t >= s.stopTime) return s.stopTime;
        return t;
    }

    function _providerVested(Stream memory s) internal view returns (uint256) {
        uint128 t = _effectiveTime(s);
        if (t <= s.startTime) return 0;
        uint256 elapsed = uint256(t - s.startTime);
        uint256 vested = elapsed * uint256(s.providerRatePerSecond);
        if (vested > s.providerDeposit) vested = s.providerDeposit;
        return vested;
    }

    function _donationVested(Stream memory s, uint256 providerVested) internal pure returns (uint256) {
        uint256 vested = _donationFor(providerVested, s.donationBps);
        if (vested > s.donationDeposit) vested = s.donationDeposit;
        return vested;
    }

    function _donationFor(uint256 providerAmount, uint16 donationBps_) internal pure returns (uint256) {
        return providerAmount * uint256(donationBps_) / 10_000;
    }

    function _streamState(Stream memory s) internal view returns (StreamState) {
        if (s.recipient == address(0)) return StreamState.Terminated;
        if (block.timestamp < s.stopTime) return StreamState.Active;
        if (block.timestamp < uint256(s.stopTime) + GRACE_PERIOD_SECONDS) return StreamState.Grace;
        return StreamState.Expired;
    }

    function streamState(uint256 streamId) external view returns (string memory) {
        StreamState state = _streamState(streams[streamId]);
        if (state == StreamState.Active) return "active";
        if (state == StreamState.Grace) return "grace";
        if (state == StreamState.Expired) return "expired";
        return "terminated";
    }

    function withdraw(uint256 streamId) external {
        Stream storage s = streams[streamId];
        require(s.recipient != address(0), "no-stream");
        require(msg.sender == s.recipient || msg.sender == s.donationRecipient, "not authorized");

        uint256 providerVested = _providerVested(s);
        uint256 donationVested = _donationVested(s, providerVested);
        uint256 providerAmount = providerVested - s.providerWithdrawn;
        uint256 donationAmount = donationVested - s.donationWithdrawn;
        require(providerAmount > 0 || donationAmount > 0, "nothing to withdraw");

        s.providerWithdrawn += providerAmount;
        s.donationWithdrawn += donationAmount;

        if (providerAmount > 0) {
            require(IERC20(s.token).transfer(s.recipient, providerAmount), "transfer provider failed");
        }
        if (donationAmount > 0) {
            require(IERC20(s.token).transfer(s.donationRecipient, donationAmount), "transfer donation failed");
        }
        emit Withdraw(streamId, s.recipient, providerAmount, s.donationRecipient, donationAmount);
    }

    function terminate(uint256 streamId) external {
        Stream storage s = streams[streamId];
        require(s.recipient != address(0), "no-stream");
        require(msg.sender == s.sender || msg.sender == s.recipient, "not authorized");

        uint256 providerVested = _providerVested(s);
        uint256 donationVested = _donationVested(s, providerVested);
        uint256 providerPayout = providerVested - s.providerWithdrawn;
        uint256 donationPayout = donationVested - s.donationWithdrawn;
        uint256 providerRefund = s.providerDeposit - providerVested;
        uint256 donationRefund = s.donationDeposit - donationVested;
        uint256 senderRefund = providerRefund + donationRefund;

        address token = s.token;
        address recipient = s.recipient;
        address donationRecipient_ = s.donationRecipient;
        address sender = s.sender;
        s.recipient = address(0);

        if (providerPayout > 0) {
            require(IERC20(token).transfer(recipient, providerPayout), "transfer provider failed");
        }
        if (donationPayout > 0) {
            require(IERC20(token).transfer(donationRecipient_, donationPayout), "transfer donation failed");
        }
        if (senderRefund > 0) {
            require(IERC20(token).transfer(sender, senderRefund), "transfer refund failed");
        }
        emit Terminated(streamId, senderRefund, providerPayout, donationPayout);
    }

    /**
     * @notice Top up an existing stream by increasing the provider deposit.
     *         Caller must approve providerAmount plus its matching donation.
     */
    function topUp(uint256 streamId, uint256 providerAmount) external {
        Stream storage s = streams[streamId];
        require(s.recipient != address(0), "no-stream");
        StreamState state = _streamState(s);
        require(state == StreamState.Active || state == StreamState.Grace, "stream expired");
        require(msg.sender == s.sender, "not sender");
        require(providerAmount > 0, "amount=0");
        require(s.token == glmToken, "token != GLM");

        uint256 donationAmount = _donationFor(providerAmount, s.donationBps);
        uint256 totalAmount = providerAmount + donationAmount;
        require(IERC20(s.token).transferFrom(msg.sender, address(this), totalAmount), "transferFrom failed");

        s.providerDeposit += providerAmount;
        s.donationDeposit += donationAmount;
        uint128 delta = uint128(providerAmount / uint256(s.providerRatePerSecond));
        require(delta > 0, "delta=0");
        uint128 base = s.stopTime < uint128(block.timestamp) ? uint128(block.timestamp) : s.stopTime;
        s.stopTime = base + delta;
        emit ToppedUp(streamId, providerAmount, donationAmount, totalAmount, s.stopTime);
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
        uint256 providerDeposit,
        uint128 providerRatePerSecond,
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
                providerDeposit,
                providerRatePerSecond,
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
