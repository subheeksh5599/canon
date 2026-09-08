// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {CanonMarket} from "../CanonMarket.sol";

/// Minimal USDC stand-in with mint + the exact transfer semantics we assert.
contract MockUSDC {
    string public symbol = "USDC";
    uint8 public decimals = 6;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    function mint(address to, uint256 amount) external {
        balanceOf[to] += amount;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        require(balanceOf[msg.sender] >= amount, "USDC: insufficient balance");
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        require(balanceOf[from] >= amount, "USDC: insufficient balance");
        require(allowance[from][msg.sender] >= amount, "USDC: insufficient allowance");
        balanceOf[from] -= amount;
        allowance[from][msg.sender] -= amount;
        balanceOf[to] += amount;
        return true;
    }
}

/// Contract battery (B-001..B-018): role checks, escrow math, bond flow,
/// events — now all USDC-denominated (raw 1e6 units). Runs on the local EVM.
contract CanonMarketTest is Test {
    CanonMarket market;
    MockUSDC usdc;
    address venue = address(0xB0B);
    address adjudicator = address(0xA11);
    address buyer = address(0x1111);
    address provider = address(0x2222);
    address evil = address(0xE91);
    uint256 jobValue = 400e6; // $400
    uint256 upfront = 100e6; //  $100
    uint256 milestones = 300e6; // $300
    uint256 bond = 80e6; //     $80

    function setUp() public {
        usdc = new MockUSDC();
        market = new CanonMarket(venue, adjudicator, address(usdc));
        usdc.mint(venue, 100_000e6); // CCP collateral
        vm.prank(venue);
        usdc.approve(address(market), type(uint256).max);
    }

    function _newTx() internal returns (uint256 txId) {
        vm.prank(venue);
        txId = market.createTransaction(buyer, provider, jobValue, upfront, milestones, bond, "digest1");
        vm.prank(venue);
        market.fund(txId);
    }

    function test_deploy_sets_roles_and_token() public view {
        assertEq(market.venue(), venue);
        assertEq(market.adjudicator(), adjudicator);
        assertEq(address(market.token()), address(usdc));
    }

    function test_create_and_fund_locks_escrow_usdc() public {
        uint256 txId = _newTx();
        (,,,, uint256 esc, uint256 bnd, CanonMarket.TxStatus st,) = market.txs(txId);
        assertEq(uint8(st), uint8(CanonMarket.TxStatus.Funded));
        assertEq(esc, milestones);
        assertEq(bnd, bond);
        assertEq(usdc.balanceOf(address(market)), milestones + bond); // $380 held
    }

    function test_evil_cannot_create() public {
        vm.prank(evil);
        vm.expectRevert(bytes("CanonMarket: venue only"));
        market.createTransaction(buyer, provider, jobValue, upfront, milestones, bond, "x");
    }

    function test_buyer_cannot_release_milestone() public {
        uint256 txId = _newTx();
        vm.prank(buyer);
        vm.expectRevert(bytes("CanonMarket: adjudicator only"));
        market.releaseMilestone(txId, 0, 100e6);
    }

    function test_fund_without_allowance_rejected() public {
        vm.prank(venue);
        uint256 txId = market.createTransaction(buyer, provider, jobValue, upfront, milestones, bond, "d");
        // revoke allowance, then fund must revert on the token pull
        vm.prank(venue);
        usdc.approve(address(market), 0);
        vm.prank(venue);
        vm.expectRevert(bytes("USDC: insufficient allowance"));
        market.fund(txId);
    }

    function test_provider_cannot_resolve_claim() public {
        uint256 txId = _newTx();
        vm.prank(venue);
        market.markCompleted(txId, false);
        vm.prank(provider);
        vm.expectRevert(bytes("CanonMarket: adjudicator only"));
        market.resolveClaim(txId, buyer, 300e6, 0);
    }

    function test_milestone_release_pays_provider_usdc() public {
        uint256 txId = _newTx();
        uint256 p0 = usdc.balanceOf(provider);
        vm.prank(adjudicator);
        market.releaseMilestone(txId, 0, 100e6);
        (,,,, uint256 esc,,,) = market.txs(txId);
        assertEq(esc, 200e6);
        assertEq(usdc.balanceOf(provider) - p0, 100e6);
        vm.prank(adjudicator);
        vm.expectRevert(bytes("CanonMarket: already released"));
        market.releaseMilestone(txId, 0, 100e6);
    }

    function test_claim_payout_escrow_plus_bond() public {
        uint256 txId = _newTx();
        vm.prank(venue);
        market.markCompleted(txId, false);
        uint256 bal0 = usdc.balanceOf(buyer);
        vm.prank(adjudicator);
        market.resolveClaim(txId, buyer, 300e6, 1_000e6); // pool empty -> no coverage
        assertEq(usdc.balanceOf(buyer) - bal0, 380e6); // $300 escrow + $80 bond
    }

    function test_completion_pays_remaining_escrow() public {
        uint256 txId = _newTx();
        uint256 bal0 = usdc.balanceOf(provider);
        vm.prank(venue);
        market.markCompleted(txId, true);
        assertEq(usdc.balanceOf(provider) - bal0, 300e6);
    }

    function test_appeal_bond_forfeit_funds_pool() public {
        vm.prank(venue);
        uint256 appealId = market.openAppeal(buyer, "CANON-001", 25e6);
        vm.prank(adjudicator);
        market.resolveAppeal(appealId, false, false);
        assertEq(market.pool(), 25e6);
        assertEq(usdc.balanceOf(address(market)), 25e6);
    }

    function test_appeal_win_refunds_bond() public {
        vm.prank(venue);
        uint256 appealId = market.openAppeal(buyer, "CANON-001", 25e6);
        uint256 bal0 = usdc.balanceOf(buyer);
        vm.prank(adjudicator);
        market.resolveAppeal(appealId, true, true);
        assertEq(usdc.balanceOf(buyer) - bal0, 25e6);
        assertEq(market.pool(), 0);
    }

    function test_double_resolve_reverted() public {
        vm.prank(venue);
        uint256 appealId = market.openAppeal(buyer, "CANON-001", 10e6);
        vm.prank(adjudicator);
        market.resolveAppeal(appealId, false, false);
        vm.prank(adjudicator);
        vm.expectRevert(bytes("CanonMarket: already resolved"));
        market.resolveAppeal(appealId, true, true);
    }

    function test_terms_digest_stored() public {
        vm.prank(venue);
        uint256 txId = market.createTransaction(buyer, provider, jobValue, upfront, milestones, bond, "sha256terms");
        (,,,,,,, string memory digest) = market.txs(txId);
        assertEq(digest, "sha256terms");
    }

    function test_terms_cannot_exceed_job_value() public {
        vm.prank(venue);
        vm.expectRevert(bytes("CanonMarket: terms exceed value"));
        market.createTransaction(buyer, provider, jobValue, upfront, 500e6, bond, "bad");
    }

    function test_same_party_rejected() public {
        vm.prank(venue);
        vm.expectRevert(bytes("CanonMarket: same party"));
        market.createTransaction(buyer, buyer, jobValue, upfront, milestones, bond, "bad");
    }

    function test_zero_terms_fund_rejected() public {
        // valid terms but nothing to escrow -> fund must refuse to pull $0
        vm.prank(venue);
        uint256 txId = market.createTransaction(buyer, provider, 100e6, 100e6, 0, 0, "d");
        vm.prank(venue);
        vm.expectRevert(bytes("CanonMarket: underfunded"));
        market.fund(txId);
    }

    function test_cancel_refunds_buyer_usdc() public {
        uint256 txId = _newTx();
        uint256 bal0 = usdc.balanceOf(buyer);
        vm.prank(venue);
        market.cancel(txId);
        assertEq(usdc.balanceOf(buyer) - bal0, 380e6);
    }

    function test_claim_on_completed_rejected() public {
        uint256 txId = _newTx();
        vm.prank(venue);
        market.markCompleted(txId, true);
        vm.prank(adjudicator);
        vm.expectRevert(bytes("CanonMarket: not failed"));
        market.resolveClaim(txId, buyer, 300e6, 0);
    }

    function test_events_emitted_on_create() public {
        vm.expectEmit(true, true, true, true);
        emit CanonMarket.TxCreated(1, buyer, provider, jobValue);
        vm.prank(venue);
        market.createTransaction(buyer, provider, jobValue, upfront, milestones, bond, "d");
    }

    function test_events_emitted_on_appeal() public {
        vm.expectEmit(true, true, true, true);
        emit CanonMarket.AppealOpened(1, buyer, 25e6, "CANON-001");
        vm.prank(venue);
        market.openAppeal(buyer, "CANON-001", 25e6);
    }
}
