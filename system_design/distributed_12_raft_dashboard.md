# Distributed_12 - Raft Dashboard

## What I Built

A real-time Raft consensus algorithm visualization dashboard with a distributed system simulator.

### Architecture

```
Browser (index.html) ←── WebSocket ──→ server.py ←──→ raft_runner.py ←──→ raft_practice/ (existing code)
```

- **Backend**: Python asyncio + websockets library
- **Frontend**: Single-page HTML with SVG topology, no external dependencies
- **Protocol**: JSON over WebSocket, 100ms broadcast loop

### Key Learnings

#### 1. WebSocket Architecture
- Server maintains a set of connected clients
- Broadcast loop pushes state every 100ms (like a game server)
- Bidirectional: server pushes state, client pushes commands
- `websockets` library is clean and production-grade

#### 2. Raft Cluster State
Each node exposes via `get_status()`:
- `role`: Leader/Follower/Candidate
- `term`: Current term number
- `logSize` / `commitIndex` / `lastApplied`
- `failed`: Node failure status
- `kvData`: Replicated key-value store

#### 3. Event Detection
The runner tracks state deltas across snapshot calls:
- Leader changes (elections)
- Term increments
- Node failures/recoveries
- Role transitions (Follower→Candidate→Leader)

Events are stored in a rolling buffer (max 200), displayed as a timeline.

#### 4. The 5 Scenarios

| Scenario | What It Tests |
|----------|---------------|
| normal_election | 3 nodes → leader emerges naturally |
| leader_fail | Kill leader → Raft re-elects |
| network_partition | Split cluster, majority continues |
| split_brain_recovery | Multi-step partitions, final heal |
| batch_write | 20 KV writes, observe log replication |

#### 5. Visualization Design
- **SVG ring topology**: Nodes arranged in circle, edges between all pairs
- **Color coding**: Blue=Leader, Green=Follower, Yellow=Candidate, Red=Failed
- **Glow effects**: Leader node has blue glow animation
- **Click interaction**: Click a node to kill/recover it
- **Real-time log**: Event timeline shows every state change

### File Structure
```
projects/raft_dashboard/
├── server.py               # WebSocket server + HTTP static
├── raft_runner.py          # Cluster wrapper + event tracking + scenarios
├── static/index.html       # Full dashboard UI (zero dependencies)
├── test_server.py          # 10 tests covering all features
├── smoke_test.py           # Interactive smoke test
└── README.md               # Documentation
```

### Running
```bash
python server.py --nodes 5
# Open static/index.html in browser
```
