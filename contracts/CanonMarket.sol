// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title CanonMarket
/// @notice The Base side of CANON — escrow, bonds, claims, appeals, settlement.
///         Terms are NEVER decided here; the venue (Python engine over Sibyl)
///         generates the terms and this contract executes them. Roles:
///         owner/venue = the CANON backend, adjudicator = independent reviewer.
///         Every state change emits an event the CANON history page indexes.
contract CanonMarket {
    enum TxStatus { None, Proposed, Termed, Funded, InProgress, Completed, Failed, Claimed, Cancelled }

    struct Tx {
        address buyer;
        address provider;
        uint256 jobValueWei;
        uint256 upfrontWei;
        uint256 escrowLockedWei; // sum of milestones still held
        uint256 bondWei;
        TxStatus status;
        string termsDigest; // hash of the doctrine-backed terms (set by venue, not contract)
    }

    struct Appeal {
        address challenger;
        uint256 bondWei;
        bool resolved;
        bool accepted;
        string targetRuleId;
    }

    address public venue;
    address public adjudicator;

    uint256 public txCounter;
    uint256 public appealCounter;
    uint256 public poolWei; // fees + forfeited bonds fund claim coverage

    mapping(uint256 => Tx) public txs;
    mapping(uint256 => Appeal) public appeals;
    mapping(uint256 => mapping(uint256 => bool)) public milestoneReleased;

    event TxCreated(uint256 indexed txId, address buyer, address provider, uint256 jobValue);
    event TxTermed(uint256 indexed txId, string termsDigest);
    event EscrowLocked(uint256 indexed txId, uint256 amount);
    event MilestoneReleased(uint256 indexed txId, uint256 milestoneIndex, uint256 amount);
    event JobCompleted(uint256 indexed txId, bool ok);
    event ClaimResolved(uint256 indexed txId, uint256 payoutWei);
    event AppealOpened(uint256 indexed appealId, address challenger, uint256 bondWei, string ruleId);
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

    constructor(address _venue, address _adjudicator) {
        venue = _venue;
        adjudicator = _adjudicator;
    }

    /// Venue registers a transaction under doctrine-generated terms. The
    /// contract stores the terms digest so post-funding tampering is visible.
    function createTransaction(
        address buyer,
        address provider,
        uint256 jobValueWei,
        uint256 upfrontWei,
        uint256 milestoneTotalWei,
        uint256 bondWei,
        string calldata termsDigest
    ) external onlyVenue returns (uint256 txId) {
        require(buyer != address(0) && provider != address(0), "CanonMarket: parties");
        require(buyer != provider, "CanonMarket: same party");
        require(upfrontWei + milestoneTotalWei <= jobValueWei, "CanonMarket: terms exceed value");
        txId = ++txCounter;
        txs[txId] = Tx({
            buyer: buyer,
            provider: provider,
            jobValueWei: jobValueWei,
            upfrontWei: upfrontWei,
            escrowLockedWei: milestoneTotalWei,
            bondWei: bondWei,
            status: TxStatus.Termed, // registered under doctrine terms -> fundable
            termsDigest: termsDigest
        });
        emit TxCreated(txId, buyer, provider, jobValueWei);
        emit TxTermed(txId, termsDigest);
    }

    /// Buyer funds: escrow (milestones) + bond are held by the contract.
    function fund(uint256 txId) external payable onlyVenue {
        Tx storage t = txs[txId];
        require(t.status == TxStatus.Termed, "CanonMarket: not termed");
        uint256 required = t.escrowLockedWei + t.bondWei;
        require(msg.value >= required, "CanonMarket: underfunded");
        t.status = TxStatus.Funded;
        emit EscrowLocked(txId, required);
    }

    /// Adjudicator releases a verified milestone to the provider.
    function releaseMilestone(uint256 txId, uint256 milestoneIndex, uint256 amountWei)
        external
        onlyAdjudicator
    {
        Tx storage t = txs[txId];
        require(t.status == TxStatus.Funded || t.status == TxStatus.InProgress, "CanonMarket: state");
        require(!milestoneReleased[txId][milestoneIndex], "CanonMarket: already released");
        require(amountWei <= t.escrowLockedWei, "CanonMarket: exceeds escrow");
        milestoneReleased[txId][milestoneIndex] = true;
        t.escrowLockedWei -= amountWei;
        _pay(t.provider, amountWei);
        emit MilestoneReleased(txId, milestoneIndex, amountWei);
    }

    function markCompleted(uint256 txId, bool ok) external onlyVenue {
        Tx storage t = txs[txId];
        require(t.status == TxStatus.Funded || t.status == TxStatus.InProgress, "CanonMarket: state");
        t.status = ok ? TxStatus.Completed : TxStatus.Failed;
        if (ok) {
            _pay(t.provider, t.escrowLockedWei); // remaining escrow to provider
            t.escrowLockedWei = 0;
        }
        emit JobCompleted(txId, ok);
    }

    /// Adjudicator resolves a claim: refund buyer's remaining escrow, apply
    /// the provider bond, and top up coverage from the pool within its balance.
    function resolveClaim(uint256 txId, address payee, uint256 escrowRefundWei, uint256 coverageWei)
        external
        onlyAdjudicator
    {
        Tx storage t = txs[txId];
        require(t.status == TxStatus.Failed, "CanonMarket: not failed");
        require(escrowRefundWei <= t.escrowLockedWei, "CanonMarket: refund exceeds escrow");
        t.escrowLockedWei -= escrowRefundWei;
        _pay(payee, escrowRefundWei + t.bondWei); // bond forfeited to the victim
        t.bondWei = 0;
        uint256 cov = coverageWei > poolWei ? poolWei : coverageWei;
        poolWei -= cov;
        _pay(payee, cov);
        t.status = TxStatus.Claimed;
        emit ClaimResolved(txId, escrowRefundWei + t.bondWei + cov);
    }

    /// Challenger opens an appeal against a doctrine rule; the bond is real.
    function openAppeal(address challenger, string calldata targetRuleId)
        external
        payable
        onlyVenue
        returns (uint256 appealId)
    {
        require(msg.value > 0, "CanonMarket: bond required");
        appealId = ++appealCounter;
        appeals[appealId] = Appeal({
            challenger: challenger,
            bondWei: msg.value,
            resolved: false,
            accepted: false,
            targetRuleId: targetRuleId
        });
        emit AppealOpened(appealId, challenger, msg.value, targetRuleId);
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
            _pay(a.challenger, a.bondWei);
        } else {
            poolWei += a.bondWei; // forfeited bond funds the pool
            emit BondForfeited(appealId, a.bondWei);
        }
        emit AppealResolved(appealId, accepted);
    }

    function cancel(uint256 txId) external onlyVenue {
        Tx storage t = txs[txId];
        require(t.status == TxStatus.Termed || t.status == TxStatus.Funded, "CanonMarket: state");
        _pay(t.buyer, t.escrowLockedWei + t.bondWei);
        t.escrowLockedWei = 0;
        t.bondWei = 0;
        t.status = TxStatus.Cancelled;
    }

    function setRoles(address _venue, address _adjudicator) external {
        require(msg.sender == venue, "CanonMarket: venue only");
        venue = _venue;
        adjudicator = _adjudicator;
        emit VenueRuleChanged(_venue, _adjudicator);
    }

    function _pay(address to, uint256 amount) internal {
        if (amount == 0) return;
        (bool ok, ) = payable(to).call{value: amount}("");
        require(ok, "CanonMarket: payout failed");
    }

    receive() external payable {}
}
