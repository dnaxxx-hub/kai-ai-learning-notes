package main

import "sort"

// Query returns all points in [start, end] for the given metric.
// Returns a copy of the data to avoid exposing internal state.
func (db *DB) Query(metric string, start, end int64) []Point {
	db.mu.RLock()
	store, ok := db.metrics[metric]
	db.mu.RUnlock()

	if !ok {
		return nil
	}

	store.mu.RLock()
	defer store.mu.RUnlock()

	if len(store.points) == 0 {
		return nil
	}

	// Binary search for start and end boundaries
	lo := sort.Search(len(store.points), func(i int) bool {
		return store.points[i].Timestamp >= start
	})
	hi := sort.Search(len(store.points), func(i int) bool {
		return store.points[i].Timestamp > end
	})

	if lo >= hi {
		return nil
	}

	// Return a copy to avoid exposing internal slice
	result := make([]Point, hi-lo)
	copy(result, store.points[lo:hi])
	return result
}

// AggregateResult holds the result of an aggregation query.
type AggregateResult struct {
	Min   float64 `json:"min"`
	Max   float64 `json:"max"`
	Avg   float64 `json:"avg"`
	Count int     `json:"count"`
}

// Aggregate computes min, max, avg, count over the query range.
func (db *DB) Aggregate(metric string, start, end int64) AggregateResult {
	points := db.Query(metric, start, end)
	var result AggregateResult

	if len(points) == 0 {
		return result
	}

	result.Min = points[0].Value
	result.Max = points[0].Value
	sum := 0.0

	for _, p := range points {
		if p.Value < result.Min {
			result.Min = p.Value
		}
		if p.Value > result.Max {
			result.Max = p.Value
		}
		sum += p.Value
	}

	result.Count = len(points)
	result.Avg = sum / float64(len(points))
	return result
}
