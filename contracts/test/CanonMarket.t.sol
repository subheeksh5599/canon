// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {CanonMarket} from "../CanonMarket.sol";

/// Contract battery (B-001..B-016): role checks, escrow math, bond flow,
/// events. Runs on the local EVM (anvil).
contract CanonMarketTest is Test {
    CanonMarket market;
    address venue = address(0xB0B);
    address adjudicator = address(0xA11);
    address buyer = address(0x1111);
    address provider = address(0x2222);
    address evil = address(0xE91);
    uint256 jobValue = 400 ether;
    uint256 upfront = 100 ether;
    uint256 milestones = 300 ether;
    uint256 bond = 80 ether;

    function setUp() public {
        market = new CanonMarket(venue, adjudicator);
        vm.deal(venue, 10_000 ether); // venue funds escrow/bonds on behalf of the flow
    }

    function _newTx() internal returns (uint256 txId) {
        vm.prank(venue);
        txId = market.createTransaction(buyer, provider, jobValue, upfront, milestones, bond, "digest1");
        vm.prank(venue);
        market.fund{value: milestones + bond}(txId);
    }

    function test_deploy_sets_roles() public view {
        assertEq(market.venue(), venue);
        assertEq(market.adjudicator(), adjudicator);
    }

    function test_create_and_fund_locks_escrow() public {
        uint256 txId = _newTx();
        (,,,, uint256 esc, uint256 bnd, CanonMarket.TxStatus st,) = market.txs(txId);
        assertEq(uint8(st), uint8(CanonMarket.TxStatus.Funded));
        assertEq(esc, milestones);
        assertEq(bnd, bond);
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
        market.releaseMilestone(txId, 0, 100 ether);
    }

    function test_provider_cannot_resolve_claim() public {
        uint256 txId = _newTx();
        vm.prank(venue);
        market.markCompleted(txId, false);
        vm.prank(provider);
        vm.expectRevert(bytes("CanonMarket: adjudicator only"));
        market.resolveClaim(txId, buyer, 300 ether, 0);
    }

    function test_milestone_release_decrements_escrow() public {
        uint256 txId = _newTx();
        vm.prank(adjudicator);
        market.releaseMilestone(txId, 0, 100 ether);
        (,,,, uint256 esc,,,) = market.txs(txId); // ok
        assertEq(esc, 200 ether);
        vm.prank(adjudicator);
        vm.expectRevert(bytes("CanonMarket: already released"));
        market.releaseMilestone(txId, 0, 100 ether);
    }

    function test_claim_payout_capped_by_escrow_plus_bond() public {
        uint256 txId = _newTx();
        vm.prank(venue);
        market.markCompleted(txId, false);
        uint256 bal0 = buyer.balance;
        vm.prank(adjudicator);
        market.resolveClaim(txId, buyer, 300 ether, 1_000 ether); // pool empty
        assertEq(buyer.balance - bal0, 380 ether); // 300 escrow + 80 bond, no coverage
    }

    function test_completion_pays_remaining_escrow() public {
        uint256 txId = _newTx();
        uint256 bal0 = provider.balance;
        vm.prank(venue);
        market.markCompleted(txId, true);
        assertEq(provider.balance - bal0, 300 ether);
    }

    function test_appeal_bond_forfeit_funds_pool() public {
        vm.prank(venue);
        uint256 appealId = market.openAppeal{value: 25 ether}(buyer, "CANON-001");
        vm.prank(adjudicator);
        market.resolveAppeal(appealId, false, false);
        assertEq(market.poolWei(), 25 ether);
    }

    function test_appeal_win_refunds_bond() public {
        vm.prank(venue);
        uint256 appealId = market.openAppeal{value: 25 ether}(buyer, "CANON-001");
        uint256 bal0 = buyer.balance;
        vm.prank(adjudicator);
        market.resolveAppeal(appealId, true, true);
        assertEq(buyer.balance - bal0, 25 ether);
        assertEq(market.poolWei(), 0);
    }

    function test_double_resolve_reverted() public {
        vm.prank(venue);
        uint256 appealId = market.openAppeal{value: 10 ether}(buyer, "CANON-001");
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
        market.createTransaction(buyer, provider, jobValue, upfront, 500 ether, bond, "bad");
    }

    function test_same_party_rejected() public {
        vm.prank(venue);
        vm.expectRevert(bytes("CanonMarket: same party"));
        market.createTransaction(buyer, buyer, jobValue, upfront, milestones, bond, "bad");
    }

    function test_underfunded_fund_rejected() public {
        vm.prank(venue);
        uint256 txId = market.createTransaction(buyer, provider, jobValue, upfront, milestones, bond, "d");
        vm.prank(venue);
        vm.expectRevert(bytes("CanonMarket: underfunded"));
        market.fund{value: 10 ether}(txId);
    }

    function test_cancel_refunds_buyer() public {
        uint256 txId = _newTx();
        uint256 bal0 = buyer.balance;
        vm.prank(venue);
        market.cancel(txId);
        assertEq(buyer.balance - bal0, 380 ether);
    }

    function test_claim_on_completed_rejected() public {
        uint256 txId = _newTx();
        vm.prank(venue);
        market.markCompleted(txId, true);
        vm.prank(adjudicator);
        vm.expectRevert(bytes("CanonMarket: not failed"));
        market.resolveClaim(txId, buyer, 300 ether, 0);
    }

    function test_events_emitted_on_create() public {
        vm.expectEmit(true, true, true, true);
        emit CanonMarket.TxCreated(1, buyer, provider, jobValue);
        vm.prank(venue);
        market.createTransaction(buyer, provider, jobValue, upfront, milestones, bond, "d");
    }

    function test_events_emitted_on_appeal() public {
        vm.expectEmit(true, true, true, true);
        emit CanonMarket.AppealOpened(1, buyer, 25 ether, "CANON-001");
        vm.prank(venue);
        market.openAppeal{value: 25 ether}(buyer, "CANON-001");
    }
}
