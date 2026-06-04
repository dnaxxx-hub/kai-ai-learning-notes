package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"
)

type ClusterNode struct {
	Raft   *Raft
	ID     string
	Port   string
}

var cluster []*ClusterNode

func main() {
	// Parse arguments
	if len(os.Args) < 3 {
		fmt.Println("Usage: goraft <node-id> <peer1:port> [peer2:port ...]")
		fmt.Println("Example: goraft A localhost:9001 B:localhost:9002 C:localhost:9003")
		os.Exit(1)
	}

	id := os.Args[1]
	argPeers := os.Args[2:]

	var peers []string
	for _, p := range argPeers {
		peers = append(peers, p)
	}

	// Create node
	node := NewRaft(id, peers)

	// Parse port from peers: format "id:host:port" e.g. "A:localhost:9001"
	myPort := "9001" // default
	myHost := "localhost"
	for _, p := range argPeers {
		var peerID, peerHost, peerPort string
		n, _ := fmt.Sscanf(p, "%1s:%s:%s", &peerID, &peerHost, &peerPort)
		if n >= 3 {
			if peerID == id {
				myHost = peerHost
				myPort = peerPort
				break
			}
		}
	}

	// Start the Raft loop
	go node.Run()
	log.Printf("Node %s started on %s:%s", id, myHost, myPort)

	// Set up HTTP handlers
	http.HandleFunc("/status", func(w http.ResponseWriter, r *http.Request) {
		term, isLeader := node.GetState()
		resp := map[string]interface{}{
			"id":          id,
			"role":        node.GetRoleName(),
			"term":        term,
			"isLeader":    isLeader,
			"logLength":   node.GetLogLength(),
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	})

	// Listen with the parsed port
	addr := fmt.Sprintf(":%s", myPort)
	log.Printf("HTTP API available at http://localhost%s/status", addr)
	if err := http.ListenAndServe(addr, nil); err != nil {
		log.Fatalf("HTTP server error: %v", err)
	}

	// Keep the process running
	select {}
}

func init() {
	// Ensure random seed
	_ = time.Now().UnixNano()
}
