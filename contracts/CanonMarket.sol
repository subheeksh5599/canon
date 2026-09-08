// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// Minimal ERC20 surface (USDC on Base Sepolia).
interface IUSDC {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

/// @title CanonMarket
/// @notice The Base side of CANON — escrow, bonds, claims, appeals, settlement,
///         denominated in USDC (6 decimals; all amounts are raw token units).
///         Terms are NEVER decided here; the venue (Python engine over Sibyl)
///         generates the terms and this contract executes them.
///         The venue acts as clearinghouse/CCP: it advances escrow + bonds from
///         its USDC collateral so members (agent identities, held off-chain in
///         the engine) transact without per-member deposits. Payouts go to the
///         member addresses recorded on each transaction.
contract CanonMarket {
    enum TxStatus { None, Proposed, Termed, Funded, InProgress, Completed, Failed, Claimed, Cancelled }

    struct Tx {
        address buyer;
        address provider;
        uint256 jobValue; // token units (USDC 1e6 = $1)
        uint256 upfront;
        uint256 escrowLocked; // sum of milestones still held
        uint256 bond;
        TxStatus status;
        string termsDigest; // hash of the doctrine-backed terms (set by venue)
    }

    struct Appeal {
        address challenger;
        uint256 bond;
        bool resolved;
        bool accepted;
        string targetRuleId;
    }

    IUSDC public immutable token;
    address public venue;
    address public adjudicator;

    uint256 public txCounter;
    uint256 public appealCounter;
    uint256 public pool; // forfeited appeal bonds fund claim coverage

    mapping(uint256 => Tx) public txs;
    mapping(uint256 => Appeal) public appeals;
    mapping(uint256 => mapping(uint256 => bool)) public milestoneReleased;

    event TxCreated(uint256 indexed txId, address buyer, address provider, uint256 jobValue);
    event TxTermed(uint256 indexed txId, string termsDigest);
    event EscrowLocked(uint256 indexed txId, uint256 amount);
    event MilestoneReleased(uint256 indexed txId, uint256 milestoneIndex, uint256 amount);
    event JobCompleted(uint256 indexed txId, bool ok);
    event ClaimResolved(uint256 indexed txId, uint256 payout);
    event AppealOpened(uint256 indexed appealId, address challenger, uint256 bond, string ruleId);
    event AppealResolved(uint256 indexed appealId, bool accepted);
    event BondForfeited(uint256 indexed appealId, uint256 amount);
    event VenueRuleChanged(address venue, address adjudicator);

    modifier onlyVenue() {
        require(msg.sender == venue, "CanonMarket: venue only");
        _;
    }

    modifier onlyAdjudicator() {
        require(msg.sender == adjudicator, "CanonMarket: adjudicator only");
        _;
    }

    constructor(address _venue, address _adjudicator, address _token) {
        venue = _venue;
        adjudicator = _adjudicator;
        token = IUSDC(_token);
    }

    /// Venue registers a transaction under doctrine-generated terms. The
    /// contract stores the terms digest so post-funding tampering is visible.
    function createTransaction(
        address buyer,
        address provider,
        uint256 jobValue,
        uint256 upfront,
        uint256 milestoneTotal,
        uint256 bond,
        string calldata termsDigest
    ) external onlyVenue returns (uint256 txId) {
        require(buyer != address(0) && provider != address(0), "CanonMarket: parties");
        require(buyer != provider, "CanonMarket: same party");
        require(upfront + milestoneTotal <= jobValue, "CanonMarket: terms exceed value");
        txId = ++txCounter;
        txs[txId] = Tx({
            buyer: buyer,
            provider: provider,
            jobValue: jobValue,
            upfront: upfront,
            escrowLocked: milestoneTotal,
            bond: bond,
            status: TxStatus.Termed,
            termsDigest: termsDigest
        });
        emit TxCreated(txId, buyer, provider, jobValue);
        emit TxTermed(txId, termsDigest);
    }

    /// CCP funding: the venue advances escrow (milestones) + bond in USDC.
    /// Requires venue -> CanonMarket allowance (one approve at onboarding).
    function fund(uint256 txId) external onlyVenue {
        Tx storage t = txs[txId];
        require(t.status == TxStatus.Termed, "CanonMarket: not termed");
        uint256 required = t.escrowLocked + t.bond;
        require(required > 0, "CanonMarket: underfunded");
        require(token.transferFrom(venue, address(this), required), "CanonMarket: pull failed");
        t.status = TxStatus.Funded;
        emit EscrowLocked(txId, required);
    }

    /// Adjudicator releases a verified milestone to the provider.
    function releaseMilestone(uint256 txId, uint256 milestoneIndex, uint256 amount)
        external
        onlyAdjudicator
    {
        Tx storage t = txs[txId];
        require(t.status == TxStatus.Funded || t.status == TxStatus.InProgress, "CanonMarket: state");
        require(!milestoneReleased[txId][milestoneIndex], "CanonMarket: already released");
        require(amount <= t.escrowLocked, "CanonMarket: exceeds escrow");
        milestoneReleased[txId][milestoneIndex] = true;
        t.escrowLocked -= amount;
        _pay(t.provider, amount);
        emit MilestoneReleased(txId, milestoneIndex, amount);
    }

    function markCompleted(uint256 txId, bool ok) external onlyVenue {
        Tx storage t = txs[txId];
        require(t.status == TxStatus.Funded || t.status == TxStatus.InProgress, "CanonMarket: state");
        t.status = ok ? TxStatus.Completed : TxStatus.Failed;
        if (ok) {
            _pay(t.provider, t.escrowLocked); // remaining escrow to provider
            t.escrowLocked = 0;
        }
        emit JobCompleted(txId, ok);
    }

    /// Adjudicator resolves a claim: refund buyer's remaining escrow, apply
    /// the provider bond, and top up coverage from the pool within its balance.
    function resolveClaim(uint256 txId, address payee, uint256 escrowRefund, uint256 coverage)
        external
        onlyAdjudicator
    {
        Tx storage t = txs[txId];
        require(t.status == TxStatus.Failed, "CanonMarket: not failed");
        require(escrowRefund <= t.escrowLocked, "CanonMarket: refund exceeds escrow");
        t.escrowLocked -= escrowRefund;
        _pay(payee, escrowRefund + t.bond); // bond forfeited to the victim
        t.bond = 0;
        uint256 cov = coverage > pool ? pool : coverage;
        pool -= cov;
        _pay(payee, cov);
        t.status = TxStatus.Claimed;
        emit ClaimResolved(txId, escrowRefund + t.bond + cov);
    }

    /// Challenger opens an appeal against a doctrine rule; the CCP advances the
    /// bond in USDC on the challenger's behalf (production: challenger allowance).
    function openAppeal(address challenger, string calldata targetRuleId, uint256 bondAmount)
        external
        onlyVenue
        returns (uint256 appealId)
    {
        require(bondAmount > 0, "CanonMarket: bond required");
        require(token.transferFrom(venue, address(this), bondAmount), "CanonMarket: pull failed");
        appealId = ++appealCounter;
        appeals[appealId] = Appeal({
            challenger: challenger,
            bond: bondAmount,
            resolved: false,
            accepted: false,
            targetRuleId: targetRuleId
        });
        emit AppealOpened(appealId, challenger, bondAmount, targetRuleId);
    }

    function resolveAppeal(uint256 appealId, bool accepted, bool refundChallenger)
        external
        onlyAdjudicator
    {
        Appeal storage a = appeals[appealId];
        require(!a.resolved, "CanonMarket: already resolved");
        a.resolved = true;
        a.accepted = accepted;
        if (accepted && refundChallenger) {
            _pay(a.challenger, a.bond);
        } else {
            pool += a.bond; // forfeited bond funds the pool
            emit BondForfeited(appealId, a.bond);
        }
        emit AppealResolved(appealId, accepted);
    }

    function cancel(uint256 txId) external onlyVenue {
        Tx storage t = txs[txId];
        require(t.status == TxStatus.Termed || t.status == TxStatus.Funded, "CanonMarket: state");
        _pay(t.buyer, t.escrowLocked + t.bond);
        t.escrowLocked = 0;
        t.bond = 0;
        t.status = TxStatus.Cancelled;
    }

    function setRoles(address _venue, address _adjudicator) external onlyVenue {
        venue = _venue;
        adjudicator = _adjudicator;
        emit VenueRuleChanged(_venue, _adjudicator);
    }

    function _pay(address to, uint256 amount) internal {
        if (amount == 0) return;
        require(token.transfer(to, amount), "CanonMarket: payout failed");
    }
}
