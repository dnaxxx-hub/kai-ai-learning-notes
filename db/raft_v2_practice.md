# Raft v2 Practice Notes

## Overview
Implemented a pure Python Raft consensus algorithm (v2) from scratch.
File: `projects/raft_v2/raft_v2.py` (~900 lines)
Tests: `projects/raft_v2/test_raft_v2.py` (~500 lines, 12 tests, all passing)

## Architecture

### Core Components
- **RaftNode**: Single peer with Follower/Candidate/Leader states
- **RaftCluster**: Multi-node simulation harness with two-phase stepping
- **NodeNetwork**: Message-passing infrastructure (in-memory)
- **StateMachine**: Deterministic state machine for command application
- **Entry**: Log entry with term, command, and index

### Raft Protocol Implementation
1. **Leader Election**: Randomized timeouts (150-300ms), RequestVote RPCs, majority wins
2. **Log Replication**: AppendEntries RPCs with heartbeat mechanism, prevLogIndex/prevLogTerm consistency checks
3. **Commit & Apply**: Leader tracks matchIndex per follower, commits when majority replicated
4. **Safety**: Only commits entries from current term, higher term causes step-down
5. **Persistence**: JSON serialization of currentTerm, votedFor, and log entries

### Simulation Model
- Two-phase stepping: Phase 1 processes messages, Phase 2 handles timeouts
- Cluster coordinates message delivery between phases for same-step delivery
- Crash/recovery simulation via network drop flags + persistance reload

## Key Bugs Fixed During Development

### 1. Vote Response Term Mismatch
The `_handle_request_vote` method was capturing `self.current_term` in the response object **before** calling `become_follower()`, which updates the term. Fixed by building the response after all term-related logic.

### 2. Message Delivery Timing
Initial design had each node doing `recv_all()` + processing + timeouts in one step. This meant node A would process a request, send a response, but node B had already drained its inbox. Fixed with two-phase processing at the cluster level.

### 3. Single Node Election
`become_candidate()` didn't check for immediate majority. For a 1-node cluster, `{self.node_id}` votes > 0/2 = 0 is already a majority. Added immediate check.

### 4. Follower Log Truncation
When the leader sends an empty AppendEntries (heartbeat with no new entries) and the follower has extra entries, the follower's extra entries were never removed. Added truncation logic for the `req.entries == []` case.

### 5. Tuple/List Serialization
JSON serialization converts Python tuples to lists. Tests had to handle this mismatch when comparing recovered log entries.

### 6. Configuration Change
The `set_configuration` method only updated the leader's config. Other nodes got their config via log replication (as a special command entry). Added explicit propagation in `RaftCluster.set_configuration()`.

## Test Results (12/12 Passing)

| # | Test | Status |
|---|------|--------|
| 1 | Single node becomes leader | ✅ |
| 2 | Three-node cluster elects leader | ✅ |
| 3 | Term increment after leader crash | ✅ |
| 4 | Leader replicates log to followers | ✅ |
| 5 | Log consistency check | ✅ |
| 6 | Log overwrite (follower inconsistency) | ✅ |
| 7 | Leader crash - data survives | ✅ |
| 8 | Five-node cluster election | ✅ |
| 9 | Persistence recovery with full log | ✅ |
| 10 | Batch submit 100 log entries | ✅ |
| 11 | Split-vote election | ✅ |
| 12 | Configuration change (add/remove nodes) | ✅ |
