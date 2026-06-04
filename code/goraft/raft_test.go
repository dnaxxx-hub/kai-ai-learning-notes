package main

import (
	"sync"
	"testing"
	"time"
)

// makeCluster creates n Raft nodes and connects them with in-memory transports.
func makeCluster(n int) []*Raft {
	var ids []string
	for i := 0; i < n; i++ {
		ids = append(ids, string(rune('A'+i)))
	}

	nodes := make([]*Raft, n)
	for i, id := range ids {
		var peers []string
		for _, pid := range ids {
			if pid != id {
				peers = append(peers, pid)
			}
		}
		nodes[i] = NewRaft(id, peers)
	}

	// Set up transports (mutex-protected, point-to-point)
	for i := range nodes {
		for j := range nodes {
			if i == j {
				continue
			}
			// Capture i, j by value
			src := i
			dst := j
			nodes[src].SetTransport(ids[dst], PeerTransport{
				AppendEntries: func(req AppendEntriesRequest) AppendEntriesResponse {
					return nodes[dst].handleAppendEntries(req)
				},
				RequestVote: func(req RequestVoteRequest) RequestVoteResponse {
					return nodes[dst].handleRequestVote(req)
				},
			})
		}
	}

	return nodes
}

// startCluster starts all nodes in the cluster.
func startCluster(nodes []*Raft) {
	for _, node := range nodes {
		go node.Run()
	}
}

// stopCluster stops all nodes in the cluster.
func stopCluster(nodes []*Raft) {
	for _, node := range nodes {
		node.Stop()
	}
}

// waitForLeader waits up to timeout for a single leader to be elected.
// Returns the leader index or -1 if no leader.
// If excludeStopped is true, stopped nodes won't be considered.
func waitForLeader(nodes []*Raft, timeout time.Duration) int {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		leaderCount := 0
		leaderIdx := -1
		for i, node := range nodes {
			_, isLeader := node.GetState()
			if isLeader {
				leaderCount++
				leaderIdx = i
			}
		}
		if leaderCount == 1 {
			return leaderIdx
		}
		time.Sleep(10 * time.Millisecond)
	}
	return -1
}

// countLeaders counts how many nodes think they are leader.
func countLeaders(nodes []*Raft) int {
	count := 0
	for _, node := range nodes {
		_, isLeader := node.GetState()
		if isLeader {
			count++
		}
	}
	return count
}

func TestInitialElection(t *testing.T) {
	nodes := makeCluster(3)
	startCluster(nodes)
	defer stopCluster(nodes)

	leaderIdx := waitForLeader(nodes, 2*time.Second)
	if leaderIdx == -1 {
		t.Fatal("expected a leader to be elected within 2s, but no leader found")
	}

	leaders := countLeaders(nodes)
	if leaders != 1 {
		t.Fatalf("expected exactly 1 leader, got %d", leaders)
	}

	t.Logf("leader elected: node %c (index %d)", 'A'+leaderIdx, leaderIdx)
}

func TestLeaderStaysLeader(t *testing.T) {
	nodes := makeCluster(3)
	startCluster(nodes)
	defer stopCluster(nodes)

	leaderIdx := waitForLeader(nodes, 2*time.Second)
	if leaderIdx == -1 {
		t.Fatal("expected a leader to be elected")
	}

	// Wait a bit (a few heartbeat cycles)
	time.Sleep(300 * time.Millisecond)

	// Verify still exactly one leader
	leaders := countLeaders(nodes)
	if leaders != 1 {
		t.Fatalf("expected exactly 1 leader after stabilization, got %d", leaders)
	}

	// Verify same leader
	_, isStillLeader := nodes[leaderIdx].GetState()
	if !isStillLeader {
		t.Fatalf("expected node %c to still be leader", 'A'+leaderIdx)
	}

	t.Logf("leader %c remains leader after stabilization", 'A'+leaderIdx)
}

func TestLeaderReElection(t *testing.T) {
	nodes := makeCluster(3)
	startCluster(nodes)
	defer stopCluster(nodes)

	leaderIdx := waitForLeader(nodes, 2*time.Second)
	if leaderIdx == -1 {
		t.Fatal("expected a leader to be elected")
	}

	// Stop the leader
	t.Logf("stopping leader node %c (at index %d)", 'A'+leaderIdx, leaderIdx)
	nodes[leaderIdx].Stop()

	// Wait for the remaining 2 nodes to elect a new leader
	// The remaining nodes are at indices other than leaderIdx
	var remaining []*Raft
	for i, n := range nodes {
		if i != leaderIdx {
			remaining = append(remaining, n)
		}
	}

	newLeaderIdx := waitForLeader(remaining, 3*time.Second)
	if newLeaderIdx == -1 {
		t.Fatal("expected a new leader to be elected after old leader stopped")
	}

	// Make sure the new leader is not the stopped one
	if !nodes[leaderIdx].stopped {
		// Stopped node should be stopped
		t.Fatal("expected leader node to be stopped")
	}

	// The new leader must be one of the running nodes
	found := false
	for i := range nodes {
		if i == leaderIdx {
			continue
		}
		_, isL := nodes[i].GetState()
		if isL {
			found = true
			t.Logf("new leader elected: node %c", 'A'+i)
			break
		}
	}
	if !found {
		t.Fatal("expected a running node to be the new leader")
	}

	// Verify exactly one leader among remaining nodes
	leaders := countLeaders(remaining)
	if leaders != 1 {
		t.Fatalf("expected exactly 1 leader among remaining nodes, got %d", leaders)
	}
}

func TestBasicLogReplication(t *testing.T) {
	nodes := makeCluster(3)
	startCluster(nodes)
	defer stopCluster(nodes)

	// Wait for leader
	leaderIdx := waitForLeader(nodes, 2*time.Second)
	if leaderIdx == -1 {
		t.Fatal("expected a leader to be elected")
	}

	leader := nodes[leaderIdx]

	// Submit a command
	const testCommand = "set x=42"
	submitted := leader.SubmitCommand(testCommand)
	if !submitted {
		t.Fatal("expected SubmitCommand to succeed (we are the leader)")
	}

	// Wait for log replication
	time.Sleep(300 * time.Millisecond)

	// Verify all nodes have the same log length
	for i, node := range nodes {
		logLen := node.GetLogLength()
		if logLen != 1 {
			t.Fatalf("node %c expected log length 1, got %d", 'A'+i, logLen)
		}
	}

	t.Logf("log replicated to all %d nodes", len(nodes))
}

func TestLogReplicationMultiple(t *testing.T) {
	nodes := makeCluster(3)
	startCluster(nodes)
	defer stopCluster(nodes)

	leaderIdx := waitForLeader(nodes, 2*time.Second)
	if leaderIdx == -1 {
		t.Fatal("expected a leader to be elected")
	}

	leader := nodes[leaderIdx]

	// Submit multiple commands
	cmds := []string{"set x=1", "set y=2", "set z=3"}
	for _, cmd := range cmds {
		submitted := leader.SubmitCommand(cmd)
		if !submitted {
			t.Fatal("expected SubmitCommand to succeed")
		}
	}

	// Wait for replication
	time.Sleep(500 * time.Millisecond)

	// Verify all nodes have the same log
	for i, node := range nodes {
		logLen := node.GetLogLength()
		if logLen != len(cmds) {
			t.Fatalf("node %c expected log length %d, got %d", 'A'+i, len(cmds), logLen)
		}
	}

	t.Logf("all %d commands replicated to all %d nodes", len(cmds), len(nodes))
}

func TestLogReplicationWithDisconnect(t *testing.T) {
	nodes := makeCluster(5)
	startCluster(nodes)
	defer stopCluster(nodes)

	leaderIdx := waitForLeader(nodes, 2*time.Second)
	if leaderIdx == -1 {
		t.Fatal("expected a leader to be elected")
	}

	leader := nodes[leaderIdx]

	// Submit a first command that everyone should get
	leader.SubmitCommand("set a=1")
	time.Sleep(300 * time.Millisecond)

	// Stop one follower
	var stoppedIdx int
	for i, node := range nodes {
		if i != leaderIdx {
			stoppedIdx = i
			node.Stop()
			break
		}
	}
	t.Logf("stopped follower node %c", 'A'+stoppedIdx)

	// Submit more commands (should still be committed with majority of 5)
	for _, cmd := range []string{"set b=2", "set c=3"} {
		leader.SubmitCommand(cmd)
	}
	time.Sleep(300 * time.Millisecond)

	// Verify the two followers that are still running have all 3 commands
	for i, node := range nodes {
		if i == stoppedIdx {
			continue
		}
		logLen := node.GetLogLength()
		if logLen != 3 {
			t.Fatalf("node %c expected log length 3, got %d", 'A'+i, logLen)
		}
	}

	t.Logf("majority retained, all commands replicated to running nodes")
}

func TestNoSplitVote(t *testing.T) {
	// With 2 nodes, Raft requires 2 votes for a majority.
	// In practice, the first node to start an election can get the other's vote
	// IF the other hasn't started its own election yet.
	// If both start at the same time or close to it, neither gets 2 votes.
	// So this test just verifies no more than 1 leader exists.
	nodes := makeCluster(2)
	startCluster(nodes)
	defer stopCluster(nodes)

	time.Sleep(2 * time.Second)

	leaders := countLeaders(nodes)
	if leaders > 1 {
		t.Fatalf("expected at most 1 leader with 2 nodes, got %d", leaders)
	}

	t.Logf("2-node cluster: leaders=%d (0 is ideal but 1 can happen in practice)", leaders)
}

func TestConcurrentSubmits(t *testing.T) {
	nodes := makeCluster(3)
	startCluster(nodes)
	defer stopCluster(nodes)

	leaderIdx := waitForLeader(nodes, 2*time.Second)
	if leaderIdx == -1 {
		t.Fatal("expected a leader to be elected")
	}

	leader := nodes[leaderIdx]

	// Concurrent submissions
	var wg sync.WaitGroup
	const numCmds = 10
	for i := 0; i < numCmds; i++ {
		wg.Add(1)
		go func(n int) {
			defer wg.Done()
			leader.SubmitCommand(string(rune('A' + n)))
		}(i)
	}
	wg.Wait()

	time.Sleep(500 * time.Millisecond)

	// All nodes should have the same log length
	expectedLen := -1
	for i, node := range nodes {
		ll := node.GetLogLength()
		if expectedLen == -1 {
			expectedLen = ll
		} else if ll != expectedLen {
			t.Fatalf("node %c log length %d != expected %d", 'A'+i, ll, expectedLen)
		}
	}

	t.Logf("concurrent submits: all nodes have %d log entries", expectedLen)
}

func TestCommitChannel(t *testing.T) {
	nodes := makeCluster(3)
	startCluster(nodes)
	defer stopCluster(nodes)

	leaderIdx := waitForLeader(nodes, 2*time.Second)
	if leaderIdx == -1 {
		t.Fatal("expected a leader to be elected")
	}

	leader := nodes[leaderIdx]

	// Subscribe to committed entries from the leader only
	var committedCommands []string
	var commitMu sync.Mutex
	done := make(chan struct{})

	go func() {
		ch := leader.GetCommitCh()
		for cmd := range ch {
			commitMu.Lock()
			committedCommands = append(committedCommands, cmd)
			if len(committedCommands) >= 3 {
				commitMu.Unlock()
				close(done)
				return
			}
			commitMu.Unlock()
		}
	}()

	// Submit and replicate
	leader.SubmitCommand("commit test 1")
	leader.SubmitCommand("commit test 2")
	leader.SubmitCommand("commit test 3")

	// Wait for commits to be observed
	select {
	case <-done:
	case <-time.After(2 * time.Second):
	}

	commitMu.Lock()
	t.Logf("total committed entries observed: %d", len(committedCommands))
	commitMu.Unlock()

	if len(committedCommands) < 3 {
		t.Fatalf("expected at least 3 committed entries, got %d", len(committedCommands))
	}
}
