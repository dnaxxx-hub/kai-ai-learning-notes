package main

import (
	"sync"
)

// Point represents a single time-series data point.
type Point struct {
	Timestamp int64   `json:"ts"` // Unix milliseconds
	Value     float64 `json:"v"`
}

// MetricStore holds ordered points for a single metric.
type MetricStore struct {
	mu     sync.RWMutex
	points []Point // sorted by Timestamp ascending
}

// WriteRequest is sent to the writeWorker channel for serialized writes.
type WriteRequest struct {
	Metric    string
	Timestamp int64
	Value     float64
	Done      chan error
}

// DB is the core time-series database engine.
type DB struct {
	mu          sync.RWMutex
	metrics     map[string]*MetricStore
	wal         *WAL
	writeChan   chan WriteRequest
	insertCount int64
	insertMu    sync.Mutex
	done        chan struct{}
	closeOnce   sync.Once
}

// NewDB creates a new DB, optionally replaying WAL at path.
func NewDB(walPath string) *DB {
	db := &DB{
		metrics:   make(map[string]*MetricStore),
		writeChan: make(chan WriteRequest, 10000),
		done:      make(chan struct{}),
	}
	db.wal = NewWAL(walPath)

	// Replay WAL on startup
	db.wal.Replay(func(entry WALEntry) {
		db.insert(entry.Metric, entry.Timestamp, entry.Value)
	})

	go db.writeWorker()
	return db
}

// Write submits an async write request. Blocks until the write is committed.
func (db *DB) Write(metric string, timestamp int64, value float64) error {
	done := make(chan error, 1)
	db.writeChan <- WriteRequest{
		Metric:    metric,
		Timestamp: timestamp,
		Value:     value,
		Done:      done,
	}
	return <-done
}

// writeWorker is a single goroutine that processes all writes serially.
func (db *DB) writeWorker() {
	for req := range db.writeChan {
		db.insert(req.Metric, req.Timestamp, req.Value)
		db.wal.Append(req.Metric, req.Timestamp, req.Value)
		req.Done <- nil
	}
	close(db.done)
}

// insert inserts a point into the metric store, maintaining sorted order.
// Must only be called from writeWorker (the only writer).
func (db *DB) insert(metric string, timestamp int64, value float64) {
	db.mu.RLock()
	store, ok := db.metrics[metric]
	db.mu.RUnlock()

	if !ok {
		store = &MetricStore{}
		db.mu.Lock()
		// double-check after acquiring write lock
		if existing, found := db.metrics[metric]; found {
			store = existing
		} else {
			db.metrics[metric] = store
		}
		db.mu.Unlock()
	}

	store.mu.Lock()
	// Binary search for insertion position
	pos := searchPosition(store.points, timestamp)
	// Grow slice, insert at pos
	store.points = append(store.points, Point{})
	copy(store.points[pos+1:], store.points[pos:])
	store.points[pos] = Point{Timestamp: timestamp, Value: value}
	store.mu.Unlock()
}

// searchPosition returns the index where a point with given timestamp
// should be inserted to maintain sorted order.
// Assumes points are sorted by Timestamp ascending.
func searchPosition(points []Point, ts int64) int {
	lo, hi := 0, len(points)
	for lo < hi {
		mid := int(uint(lo+hi) >> 1)
		if points[mid].Timestamp < ts {
			lo = mid + 1
		} else {
			hi = mid
		}
	}
	return lo
}

// Close shuts down the write worker and WAL.
func (db *DB) Close() {
	db.closeOnce.Do(func() {
		close(db.writeChan)
		<-db.done
		if db.wal != nil {
			db.wal.Close()
		}
	})
}
