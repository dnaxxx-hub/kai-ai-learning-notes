package main

import (
	"encoding/gob"
	"os"
	"sync"
)

// WALEntry represents a single entry in the write-ahead log.
type WALEntry struct {
	Metric    string
	Timestamp int64
	Value     float64
}

// WAL implements a write-ahead log using gob encoding.
type WAL struct {
	mu   sync.Mutex
	file *os.File
	enc  *gob.Encoder
	path string
}

// NewWAL opens (or creates) a WAL file at the given path.
func NewWAL(path string) *WAL {
	w := &WAL{path: path}

	// Open for append; create if not exists
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		// Fallback: create new file
		f, err = os.Create(path)
		if err != nil {
			panic("failed to open WAL: " + err.Error())
		}
	}

	w.file = f
	w.enc = gob.NewEncoder(f)
	gob.Register(WALEntry{})

	return w
}

// Append writes a single entry to the WAL.
func (w *WAL) Append(metric string, ts int64, val float64) {
	w.mu.Lock()
	defer w.mu.Unlock()

	entry := WALEntry{
		Metric:    metric,
		Timestamp: ts,
		Value:     val,
	}

	if err := w.enc.Encode(entry); err != nil {
		// Log and continue - WAL failures should not crash the DB
		panic("WAL write failed: " + err.Error())
	}
}

// Replay reads all entries from the WAL file and calls callback for each.
func (w *WAL) Replay(callback func(WALEntry)) {
	f, err := os.Open(w.path)
	if err != nil {
		// File doesn't exist yet; nothing to replay
		return
	}
	defer f.Close()

	dec := gob.NewDecoder(f)
	for {
		var entry WALEntry
		err := dec.Decode(&entry)
		if err != nil {
			break // EOF or error
		}
		callback(entry)
	}
}

// Close closes the WAL file.
func (w *WAL) Close() {
	if w.file != nil {
		w.file.Close()
		w.file = nil
	}
}
