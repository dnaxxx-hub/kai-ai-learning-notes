package main

import (
	"math/rand"
	"sync"
	"time"
)

// Role represents the current role of a Raft node.
type Role int

const (
	Follower Role = iota
	Candidate
	Leader
)

// LogEntry represents a single log entry in the Raft log.
type LogEntry struct {
	Term    int
	Command string
}

// AppendEntriesRequest is the RPC request for log replication / heartbeat.
type AppendEntriesRequest struct {
	Term         int
	LeaderId     string
	PrevLogIndex int
	PrevLogTerm  int
	Entries      []LogEntry
	LeaderCommit int
}

// AppendEntriesResponse is the RPC response for log replication.
type AppendEntriesResponse struct {
	Term    int
	Success bool
	// Fast rollback optimization
	ConflictTerm  int
	ConflictIndex int
}

// RequestVoteRequest is the RPC request for leader election.
type RequestVoteRequest struct {
	Term         int
	CandidateId  string
	LastLogIndex int
	LastLogTerm  int
}

// RequestVoteResponse is the RPC response for leader election.
type RequestVoteResponse struct {
	Term        int
	VoteGranted bool
}

// PeerTransport simulates network RPC to a peer.
type PeerTransport struct {
	AppendEntries func(AppendEntriesRequest) AppendEntriesResponse
	RequestVote   func(RequestVoteRequest) RequestVoteResponse
}

// Raft implements the Raft consensus algorithm core logic.
type Raft struct {
	mu sync.Mutex

	// Persistent state
	currentTerm int
	votedFor    string
	log         []LogEntry

	// Volatile state
	role Role
	id   string

	// Leader volatile state
	nextIndex  map[string]int
	matchIndex map[string]int

	// Election (protected by mu)
	electionTimeout time.Duration
	lastHeartbeat   time.Time

	// Commit tracking
	commitIndex int
	lastApplied int

	// Channels
	commandCh chan string
	commitCh  chan string

	// Network simulation
	peers      []string
	transports map[string]PeerTransport

	// Lifecycle
	stopCh  chan struct{}
	stopped bool
}

// NewRaft creates a new Raft node with the given id and peers.
func NewRaft(id string, peers []string) *Raft {
	rf := &Raft{
		id:          id,
		peers:       peers,
		role:        Follower,
		votedFor:    "",
		log:         []LogEntry{},
		nextIndex:   make(map[string]int),
		matchIndex:  make(map[string]int),
		transports:  make(map[string]PeerTransport),
		commandCh:   make(chan string, 100),
		commitCh:    make(chan string, 100),
		stopCh:      make(chan struct{}),
		commitIndex: 0,
		lastApplied: 0,
	}
	rf.initializeElectionTimer()
	return rf
}

// SetTransport registers the transport for a peer.
func (rf *Raft) SetTransport(peerId string, transport PeerTransport) {
	rf.mu.Lock()
	defer rf.mu.Unlock()
	rf.transports[peerId] = transport
}

// initializeElectionTimer sets a random election timeout (150-300ms).
// Must be called with rf.mu held.
func (rf *Raft) initializeElectionTimer() {
	rf.electionTimeout = time.Duration(150+rand.Intn(150)) * time.Millisecond
	rf.lastHeartbeat = time.Now()
}

// resetElectionTimer sets a random election timeout and resets the heartbeat.
// Must be called with rf.mu held.
func (rf *Raft) resetElectionTimer() {
	rf.electionTimeout = time.Duration(150+rand.Intn(150)) * time.Millisecond
	rf.lastHeartbeat = time.Now()
}

// isElectionTimeout checks if the election timer has expired.
// Must be called with rf.mu held.
func (rf *Raft) isElectionTimeout() bool {
	return time.Since(rf.lastHeartbeat) > rf.electionTimeout
}

// lastLogTermAndIndex returns the term and index of the last log entry.
// Index is 1-based (0 means no entries).
// Must be called with rf.mu held.
func (rf *Raft) lastLogTermAndIndex() (int, int) {
	if len(rf.log) == 0 {
		return 0, 0
	}
	lastIdx := len(rf.log)
	return rf.log[lastIdx-1].Term, lastIdx
}

// startElection transitions to Candidate and requests votes from peers.
func (rf *Raft) startElection() {
	rf.mu.Lock()
	if rf.role == Leader {
		rf.mu.Unlock()
		return
	}
	rf.role = Candidate
	rf.currentTerm++
	rf.votedFor = rf.id
	lastTerm, lastIndex := rf.lastLogTermAndIndex()
	request := RequestVoteRequest{
		Term:         rf.currentTerm,
		CandidateId:  rf.id,
		LastLogIndex: lastIndex,
		LastLogTerm:  lastTerm,
	}
	rf.resetElectionTimer()
	rf.mu.Unlock()

	votes := 1
	var voteMu sync.Mutex
	var wg sync.WaitGroup

	for _, peer := range rf.peers {
		if peer == rf.id {
			continue
		}
		wg.Add(1)
		go func(p string) {
			defer wg.Done()
			transport, ok := rf.transports[p]
			if !ok {
				return
			}
			resp := transport.RequestVote(request)

			rf.mu.Lock()
			if resp.Term > rf.currentTerm {
				rf.role = Follower
				rf.currentTerm = resp.Term
				rf.votedFor = ""
				rf.resetElectionTimer()
				rf.mu.Unlock()
				return
			}
			rf.mu.Unlock()

			if resp.VoteGranted {
				voteMu.Lock()
				votes++
				voteMu.Unlock()
			}
		}(peer)
	}
	wg.Wait()

	rf.mu.Lock()
	if votes > len(rf.peers)/2 && rf.role == Candidate {
		rf.role = Leader
		for _, p := range rf.peers {
			if p == rf.id {
				continue
			}
			rf.nextIndex[p] = len(rf.log) + 1
			rf.matchIndex[p] = 0
		}
	}
	rf.mu.Unlock()
}

// handleRequestVote handles an incoming RequestVote RPC.
func (rf *Raft) handleRequestVote(req RequestVoteRequest) RequestVoteResponse {
	rf.mu.Lock()
	defer rf.mu.Unlock()

	// Reply false if term < currentTerm
	if req.Term < rf.currentTerm {
		return RequestVoteResponse{Term: rf.currentTerm, VoteGranted: false}
	}

	// If term > currentTerm, step down
	if req.Term > rf.currentTerm {
		rf.currentTerm = req.Term
		rf.role = Follower
		rf.votedFor = ""
		rf.resetElectionTimer()
	}

	// Check if already voted in this term
	if rf.votedFor != "" && rf.votedFor != req.CandidateId {
		return RequestVoteResponse{Term: rf.currentTerm, VoteGranted: false}
	}

	// Check log up-to-dateness
	lastTerm, lastIndex := rf.lastLogTermAndIndex()
	upToDate := false
	if req.LastLogTerm > lastTerm {
		upToDate = true
	} else if req.LastLogTerm == lastTerm && req.LastLogIndex >= lastIndex {
		upToDate = true
	}

	if !upToDate {
		return RequestVoteResponse{Term: rf.currentTerm, VoteGranted: false}
	}

	// Grant vote
	rf.votedFor = req.CandidateId
	rf.resetElectionTimer()
	return RequestVoteResponse{Term: rf.currentTerm, VoteGranted: true}
}

// handleAppendEntries handles an incoming AppendEntries RPC (heartbeat or log replication).
func (rf *Raft) handleAppendEntries(req AppendEntriesRequest) AppendEntriesResponse {
	rf.mu.Lock()
	defer rf.mu.Unlock()

	// 1. Reply false if term < currentTerm
	if req.Term < rf.currentTerm {
		return AppendEntriesResponse{Term: rf.currentTerm, Success: false}
	}

	// If term > currentTerm, step down
	if req.Term > rf.currentTerm {
		rf.currentTerm = req.Term
		rf.votedFor = ""
	}
	rf.role = Follower
	rf.resetElectionTimer()

	// 2. Log consistency check
	if req.PrevLogIndex > 0 {
		// If log is too short, return conflict info
		if req.PrevLogIndex > len(rf.log) {
			return AppendEntriesResponse{
				Term:          rf.currentTerm,
				Success:       false,
				ConflictTerm:  -1,
				ConflictIndex: len(rf.log) + 1,
			}
		}
		// If term doesn't match at PrevLogIndex
		if rf.log[req.PrevLogIndex-1].Term != req.PrevLogTerm {
			conflictTerm := rf.log[req.PrevLogIndex-1].Term
			// Find the first index of the conflicting term
			conflictIndex := req.PrevLogIndex
			for i := conflictIndex - 1; i > 0; i-- {
				if rf.log[i-1].Term != conflictTerm {
					conflictIndex = i
					break
				}
			}
			return AppendEntriesResponse{
				Term:          rf.currentTerm,
				Success:       false,
				ConflictTerm:  conflictTerm,
				ConflictIndex: conflictIndex,
			}
		}
	}

	// 3. Delete conflicting entries and append new ones
	if len(req.Entries) > 0 {
		logIndex := req.PrevLogIndex // 0-based index in slice
		for i, entry := range req.Entries {
			entryIdx := logIndex + i
			if entryIdx < len(rf.log) {
				if rf.log[entryIdx].Term != entry.Term {
					// Conflict: truncate from here
					rf.log = rf.log[:entryIdx]
					rf.log = append(rf.log, req.Entries[i:]...)
					break
				}
			} else if entryIdx == len(rf.log) {
				// Append new entry
				rf.log = append(rf.log, req.Entries[i:]...)
				break
			}
		}
	}

	// 4. Update commitIndex
	if req.LeaderCommit > rf.commitIndex {
		lastNewIndex := len(rf.log)
		if req.LeaderCommit < lastNewIndex {
			rf.commitIndex = req.LeaderCommit
		} else {
			rf.commitIndex = lastNewIndex
		}
		// Apply committed entries (fire them to commitCh)
		for rf.lastApplied < rf.commitIndex {
			rf.lastApplied++
			entry := rf.log[rf.lastApplied-1]
			select {
			case rf.commitCh <- entry.Command:
			default:
			}
		}
	}

	return AppendEntriesResponse{Term: rf.currentTerm, Success: true}
}

// sendAppendEntries sends an AppendEntries RPC (with logs if any) to a peer.
func (rf *Raft) sendAppendEntries(peer string) {
	rf.mu.Lock()
	nextIdx := rf.nextIndex[peer]
	var entries []LogEntry
	if nextIdx-1 < len(rf.log) {
		entries = rf.log[nextIdx-1:]
	}

	var prevLogIndex, prevLogTerm int
	if nextIdx > 1 {
		prevLogIndex = nextIdx - 1
		prevLogTerm = rf.log[prevLogIndex-1].Term
	}

	req := AppendEntriesRequest{
		Term:         rf.currentTerm,
		LeaderId:     rf.id,
		PrevLogIndex: prevLogIndex,
		PrevLogTerm:  prevLogTerm,
		Entries:      entries,
		LeaderCommit: rf.commitIndex,
	}
	rf.mu.Unlock()

	transport, ok := rf.transports[peer]
	if !ok {
		return
	}
	resp := transport.AppendEntries(req)

	rf.mu.Lock()
	defer rf.mu.Unlock()

	if resp.Term > rf.currentTerm {
		rf.role = Follower
		rf.currentTerm = resp.Term
		rf.votedFor = ""
		rf.resetElectionTimer()
		return
	}

	if rf.role != Leader {
		return
	}

	if resp.Success {
		rf.nextIndex[peer] = nextIdx + len(entries)
		rf.matchIndex[peer] = rf.nextIndex[peer] - 1
		// Try to advance commitIndex
		rf.updateCommitIndex()
	} else {
		// Fast rollback
		if resp.ConflictTerm == -1 {
			// Log too short on follower
			rf.nextIndex[peer] = resp.ConflictIndex
		} else {
			// Find last index of the conflicting term in our log
			newNextIndex := resp.ConflictIndex
			for i := len(rf.log) - 1; i >= 0; i-- {
				if rf.log[i].Term == resp.ConflictTerm {
					newNextIndex = i + 1
					break
				}
			}
			if newNextIndex > rf.nextIndex[peer] {
				newNextIndex = resp.ConflictIndex
			}
			rf.nextIndex[peer] = newNextIndex
		}
	}
}

// updateCommitIndex advances the commit index if a majority of nodes have replicated.
// Must be called with rf.mu held.
func (rf *Raft) updateCommitIndex() {
	for n := len(rf.log); n > rf.commitIndex; n-- {
		if rf.log[n-1].Term != rf.currentTerm {
			continue
		}
		count := 1 // self counts
		for _, p := range rf.peers {
			if p == rf.id {
				continue
			}
			if rf.matchIndex[p] >= n {
				count++
			}
		}
		if count > len(rf.peers)/2 {
			rf.commitIndex = n
			// Apply entries
			for rf.lastApplied < rf.commitIndex {
				rf.lastApplied++
				entry := rf.log[rf.lastApplied-1]
				select {
				case rf.commitCh <- entry.Command:
				default:
				}
			}
			return
		}
	}
}

// sendHeartbeats sends empty AppendEntries RPCs to all peers.
func (rf *Raft) sendHeartbeats() {
	rf.mu.Lock()
	if rf.role != Leader {
		rf.mu.Unlock()
		return
	}
	rf.mu.Unlock()

	for _, peer := range rf.peers {
		if peer == rf.id {
			continue
		}
		go rf.sendAppendEntries(peer)
	}
}

// SubmitCommand submits a command to the Raft cluster (only applies if leader).
func (rf *Raft) SubmitCommand(command string) bool {
	rf.mu.Lock()
	if rf.role != Leader {
		rf.mu.Unlock()
		return false
	}
	rf.log = append(rf.log, LogEntry{Term: rf.currentTerm, Command: command})
	rf.mu.Unlock()

	// Immediately try to replicate
	rf.sendHeartbeats()
	return true
}

// Run starts the main Raft loop.
func (rf *Raft) Run() {
	for {
		rf.mu.Lock()
		select {
		case <-rf.stopCh:
			rf.mu.Unlock()
			return
		default:
		}
		role := rf.role
		isTimeout := rf.isElectionTimeout()
		rf.mu.Unlock()

		switch role {
		case Follower:
			if isTimeout {
				rf.startElection()
			}
			time.Sleep(10 * time.Millisecond)

		case Candidate:
			if isTimeout {
				rf.startElection()
			}
			time.Sleep(10 * time.Millisecond)

		case Leader:
			rf.sendHeartbeats()
			time.Sleep(50 * time.Millisecond)
		}
	}
}

// Stop stops the Raft node. Safe to call multiple times.
func (rf *Raft) Stop() {
	rf.mu.Lock()
	defer rf.mu.Unlock()
	if rf.stopped {
		return
	}
	rf.stopped = true
	close(rf.stopCh)
}

// GetState returns the current term and whether this node is the leader.
func (rf *Raft) GetState() (int, bool) {
	rf.mu.Lock()
	defer rf.mu.Unlock()
	return rf.currentTerm, rf.role == Leader
}

// GetRoleName returns the string representation of the current role.
func (rf *Raft) GetRoleName() string {
	rf.mu.Lock()
	defer rf.mu.Unlock()
	switch rf.role {
	case Follower:
		return "Follower"
	case Candidate:
		return "Candidate"
	case Leader:
		return "Leader"
	}
	return "Unknown"
}

// GetLogLength returns the current length of the log.
func (rf *Raft) GetLogLength() int {
	rf.mu.Lock()
	defer rf.mu.Unlock()
	return len(rf.log)
}

// GetCommitCh returns the commit channel.
func (rf *Raft) GetCommitCh() chan string {
	return rf.commitCh
}
