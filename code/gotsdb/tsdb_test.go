package main

import (
	"math"
	"os"
	"sync"
	"testing"
)

func TestBasicWriteAndQuery(t *testing.T) {
	db := NewDB("test_data.gob")
	defer os.Remove("test_data.gob")
	defer db.Close()

	// Write 100 points for metric "cpu"
	for i := 0; i < 100; i++ {
		err := db.Write("cpu", int64(i*1000+1000), float64(i+10))
		if err != nil {
			t.Fatalf("write error: %v", err)
		}
	}

	// Query first 50 points (ts 1000 to 50000)
	points := db.Query("cpu", 1000, 50000)
	if len(points) != 50 {
		t.Fatalf("expected 50 points, got %d", len(points))
	}

	// Verify first point
	if points[0].Timestamp != 1000 || points[0].Value != 10.0 {
		t.Fatalf("first point mismatch: ts=%d v=%f", points[0].Timestamp, points[0].Value)
	}

	// Aggregate
	result := db.Aggregate("cpu", 1000, 100000)
	if result.Count != 100 {
		t.Fatalf("expected count 100, got %d", result.Count)
	}
	if result.Min != 10.0 {
		t.Fatalf("expected min 10.0, got %f", result.Min)
	}
	if result.Max != 109.0 {
		t.Fatalf("expected max 109.0, got %f", result.Max)
	}
	expectedAvg := (10.0 + 109.0) / 2.0
	if math.Abs(result.Avg-expectedAvg) > 0.001 {
		t.Fatalf("expected avg ~%f, got %f", expectedAvg, result.Avg)
	}

	t.Logf("min=%.2f max=%.2f avg=%.2f count=%d", result.Min, result.Max, result.Avg, result.Count)

	// Close and reopen to verify WAL replay
	db.Close()
	db2 := NewDB("test_data.gob")
	defer os.Remove("test_data.gob")
	defer db2.Close()

	points2 := db2.Query("cpu", 1000, 100000)
	if len(points2) != 100 {
		t.Fatalf("WAL replay: expected 100 points, got %d", len(points2))
	}
}

func TestMultiMetric(t *testing.T) {
	db := NewDB("test_data_multi.gob")
	defer os.Remove("test_data_multi.gob")
	defer db.Close()

	// Write to multiple metrics
	for i := 0; i < 50; i++ {
		err := db.Write("cpu", int64(i*1000), float64(i))
		if err != nil {
			t.Fatal(err)
		}
		err = db.Write("mem", int64(i*1000), float64(i*2))
		if err != nil {
			t.Fatal(err)
		}
		err = db.Write("disk", int64(i*1000), float64(i)*1.5)
		if err != nil {
			t.Fatal(err)
		}
	}

	// Verify each metric
	for _, m := range []string{"cpu", "mem", "disk"} {
		pts := db.Query(m, 0, 1<<63-1)
		if len(pts) != 50 {
			t.Fatalf("metric %s: expected 50 points, got %d", m, len(pts))
		}
	}

	// WAL replay check
	db.Close()
	db2 := NewDB("test_data_multi.gob")
	defer os.Remove("test_data_multi.gob")
	defer db2.Close()

	for _, m := range []string{"cpu", "mem", "disk"} {
		pts := db2.Query(m, 0, 1<<63-1)
		if len(pts) != 50 {
			t.Fatalf("WAL replay metric %s: expected 50 points, got %d", m, len(pts))
		}
	}
}

func TestEmptyQuery(t *testing.T) {
	db := NewDB("test_data_empty.gob")
	defer os.Remove("test_data_empty.gob")
	defer db.Close()

	// Query non-existent metric
	pts := db.Query("nonexistent", 0, 1000)
	if pts != nil {
		t.Fatalf("expected nil for non-existent metric, got %v", pts)
	}

	// Aggregate on non-existent metric
	result := db.Aggregate("nonexistent", 0, 1000)
	if result.Count != 0 {
		t.Fatalf("expected count 0 for non-existent metric, got %d", result.Count)
	}

	// Write then query empty range
	err := db.Write("test", 500, 1.0)
	if err != nil {
		t.Fatal(err)
	}

	// Query outside the range
	pts = db.Query("test", 0, 100)
	if pts != nil {
		t.Fatalf("expected nil for empty range, got %v", pts)
	}
}

func TestHighConcurrency(t *testing.T) {
	db := NewDB("test_data_conc.gob")
	defer os.Remove("test_data_conc.gob")
	defer db.Close()

	var wg sync.WaitGroup
	metrics := []string{"a", "b", "c", "d", "e", "f", "g", "h", "i", "j"}

	// 10 concurrent writers, each writing 100 points to a different metric
	for _, m := range metrics {
		wg.Add(1)
		go func(metric string) {
			defer wg.Done()
			for i := 0; i < 100; i++ {
				err := db.Write(metric, int64(i*100), float64(i))
				if err != nil {
					t.Errorf("write error on %s: %v", metric, err)
					return
				}
			}
		}(m)
	}

	// Concurrent queries while writing
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for _, m := range metrics {
				db.Query(m, 0, 1<<63-1)
				db.Aggregate(m, 0, 1<<63-1)
			}
		}()
	}

	wg.Wait()

	// Verify all data written
	for _, m := range metrics {
		pts := db.Query(m, 0, 1<<63-1)
		if len(pts) != 100 {
			t.Fatalf("metric %s: expected 100 points, got %d", m, len(pts))
		}
	}
}

func TestPointOrdering(t *testing.T) {
	db := NewDB("test_data_order.gob")
	defer os.Remove("test_data_order.gob")
	defer db.Close()

	// Write points out of order
	err := db.Write("test", 3000, 3.0)
	if err != nil {
		t.Fatal(err)
	}
	err = db.Write("test", 1000, 1.0)
	if err != nil {
		t.Fatal(err)
	}
	err = db.Write("test", 2000, 2.0)
	if err != nil {
		t.Fatal(err)
	}

	pts := db.Query("test", 0, 1<<63-1)
	if len(pts) != 3 {
		t.Fatalf("expected 3 points, got %d", len(pts))
	}

	// Verify ordering
	expected := []struct {
		ts int64
		v  float64
	}{
		{1000, 1.0},
		{2000, 2.0},
		{3000, 3.0},
	}
	for i, p := range pts {
		if p.Timestamp != expected[i].ts || p.Value != expected[i].v {
			t.Fatalf("point %d: expected ts=%d v=%f, got ts=%d v=%f",
				i, expected[i].ts, expected[i].v, p.Timestamp, p.Value)
		}
	}
}
