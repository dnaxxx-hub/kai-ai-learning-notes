package main

import (
	"encoding/json"
	"log"
	"net/http"
	"strconv"
)

// writeRequestJSON is the JSON format accepted by /write.
type writeRequestJSON struct {
	Metric    string  `json:"metric"`
	Timestamp int64   `json:"ts"`
	Value     float64 `json:"v"`
}

func main() {
	db := NewDB("data.gob")
	defer db.Close()

	// POST /write — ingest a data point
	http.HandleFunc("/write", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		var req writeRequestJSON
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "invalid JSON: "+err.Error(), http.StatusBadRequest)
			return
		}

		if req.Metric == "" {
			http.Error(w, "metric is required", http.StatusBadRequest)
			return
		}

		if err := db.Write(req.Metric, req.Timestamp, req.Value); err != nil {
			http.Error(w, "write failed: "+err.Error(), http.StatusInternalServerError)
			return
		}

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	})

	// GET /query?metric=xxx&start=0&end=999999 — range query
	http.HandleFunc("/query", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		metric := r.URL.Query().Get("metric")
		startStr := r.URL.Query().Get("start")
		endStr := r.URL.Query().Get("end")

		if metric == "" {
			http.Error(w, "metric is required", http.StatusBadRequest)
			return
		}

		start, err := strconv.ParseInt(startStr, 10, 64)
		if err != nil {
			start = 0
		}
		end, err := strconv.ParseInt(endStr, 10, 64)
		if err != nil {
			end = 1<<63 - 1 // max int64
		}

		points := db.Query(metric, start, end)
		if points == nil {
			points = []Point{} // return empty array, not null
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(points)
	})

	// GET /aggregate?metric=xxx&start=0&end=999999 — aggregation
	http.HandleFunc("/aggregate", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		metric := r.URL.Query().Get("metric")
		startStr := r.URL.Query().Get("start")
		endStr := r.URL.Query().Get("end")

		if metric == "" {
			http.Error(w, "metric is required", http.StatusBadRequest)
			return
		}

		start, err := strconv.ParseInt(startStr, 10, 64)
		if err != nil {
			start = 0
		}
		end, err := strconv.ParseInt(endStr, 10, 64)
		if err != nil {
			end = 1<<63 - 1
		}

		result := db.Aggregate(metric, start, end)

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(result)
	})

	log.Println("gotsdb listening on :8080")
	log.Fatal(http.ListenAndServe(":8080", nil))
}
