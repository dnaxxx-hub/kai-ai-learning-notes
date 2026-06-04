package main

import (
	"embed"
	"encoding/json"
	"log"
	"math"
	"net/http"
	"sync"
	"time"
)

//go:embed portfolio.html
var portfolioHTML embed.FS

var (
	dashboard DashboardResponse
	mu        sync.RWMutex
)

// Stock definition for the two stocks we track.
type stockDef struct {
	Name string
	Code string
}

var trackedStocks = []stockDef{
	{Name: "中国宝安", Code: "sz000009"},
	{Name: "仙琚制药", Code: "sz002332"},
}

func main() {
	// Initial refresh on startup
	go refreshData()

	// Auto-refresh every 30 minutes during trading hours (9:30-15:00)
	go func() {
		ticker := time.NewTicker(30 * time.Minute)
		for range ticker.C {
			now := time.Now()
			hour := now.Hour()
			minute := now.Minute()
			weekday := now.Weekday()

			// Only refresh on weekdays during trading hours
			if weekday >= time.Monday && weekday <= time.Friday {
				totalMin := hour*60 + minute
				if totalMin >= 9*60+30 && totalMin <= 15*60 {
					log.Println("Auto-refresh triggered")
					refreshData()
				}
			}
		}
	}()

	// Routes
	http.HandleFunc("/", handleRoot)
	http.HandleFunc("/api/status", handleStatus)
	http.HandleFunc("/api/prices", handlePrices)
	http.HandleFunc("/api/history", handleHistory)
	http.HandleFunc("/api/refresh", handleRefresh)

	log.Println("📊 仓位仪表盘启动: http://localhost:8080")
	log.Fatal(http.ListenAndServe(":8080", nil))
}

func handleRoot(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	data, err := portfolioHTML.ReadFile("portfolio.html")
	if err != nil {
		http.Error(w, "Internal error", http.StatusInternalServerError)
		return
	}
	w.Write(data)
}

func handleStatus(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	mu.RLock()
	defer mu.RUnlock()
	json.NewEncoder(w).Encode(dashboard)
}

func handlePrices(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	mu.RLock()
	defer mu.RUnlock()
	json.NewEncoder(w).Encode(dashboard)
}

func handleHistory(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	mu.RLock()
	defer mu.RUnlock()
	json.NewEncoder(w).Encode(dashboard)
}

func handleRefresh(w http.ResponseWriter, r *http.Request) {
	go refreshData()
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	json.NewEncoder(w).Encode(map[string]string{"status": "refreshing"})
}

// refreshData fetches data for all tracked stocks and updates the dashboard.
func refreshData() {
	log.Println("🔄 Refreshing data...")
	now := time.Now()

	var stocks []StockStatus
	totalPoints := 0
	offline := false

	for _, st := range trackedStocks {
		status := processStock(st.Name, st.Code, now)
		if status.CurrentPrice <= 0 {
			offline = true
		}
		status.UpdatedAt = now
		totalPoints += len(status.Points)
		stocks = append(stocks, status)
	}

	mu.Lock()
	dashboard = DashboardResponse{
		Stocks:      stocks,
		UpdatedAt:   now,
		TotalPoints: totalPoints,
		Offline:     offline,
	}
	mu.Unlock()

	log.Printf("✅ Data refreshed: %d stocks, %d points", len(stocks), totalPoints)
}

// processStock fetches kline, calculates GARCH, Kelly, and builds StockStatus.
func processStock(name, code string, now time.Time) StockStatus {
	status := StockStatus{
		Name: name,
		Code: code,
	}

	// Fetch kline data (up to 120 days for enough data, but we keep 60 for display)
	points, err := fetchKline(code, 120)
	if err != nil {
		log.Printf("⚠️  fetch error for %s: %v", code, err)
		// Try alternate API as fallback
		altPoints, altErr := fetchKlineAlt(code)
		if altErr != nil {
			log.Printf("⚠️  alt fetch also failed for %s: %v", code, altErr)
			status.CurrentPrice = 0
			return status
		}
		points = altPoints
	}

	// Keep only the most recent 60 points for display
	if len(points) > 60 {
		status.Points = points[len(points)-60:]
	} else {
		status.Points = points
	}

	// Set current price from the last point
	if len(points) > 0 {
		status.CurrentPrice = points[len(points)-1].Close
	}

	// Calculate day change (last close vs second-to-last)
	if len(points) >= 2 {
		prev := points[len(points)-2].Close
		if prev > 0 {
			status.Change = (status.CurrentPrice - prev) / prev * 100
		}
	}

	// Compute returns from all available points for better estimates
	allCloses := extractCloses(points)
	returns := computeReturns(allCloses)

	// Calculate volatility with GARCH
	if len(returns) >= 5 {
		status.Volatility = predictVol(returns, 1)
	} else {
		status.Volatility = 0.0
	}

	// If GARCH failed, use simple historical volatility as fallback
	if status.Volatility <= 0 || math.IsNaN(status.Volatility) || math.IsInf(status.Volatility, 0) {
		status.Volatility = simpleAnnualVol(returns)
	}

	// Calculate win probability and win/loss ratio
	if len(allCloses) >= 5 {
		wp, wlr := calcHistoricalProb(allCloses)
		status.WinProb = wp
		status.WinLossRatio = wlr
	} else {
		status.WinProb = 0.5
		status.WinLossRatio = 1.0
	}

	// Kelly fraction
	status.KellyFrac = kellyFraction(status.WinProb, status.WinLossRatio)

	// Position suggestion
	status.SuggestedPos, status.Signal = suggestPosition(status.KellyFrac, status.Volatility)

	return status
}

// simpleAnnualVol calculates simple (non-GARCH) annualized volatility as fallback.
func simpleAnnualVol(returns []float64) float64 {
	if len(returns) < 2 {
		return 0.3 // default 30%
	}

	mean := 0.0
	for _, r := range returns {
		mean += r
	}
	mean /= float64(len(returns))

	var sumSq float64
	for _, r := range returns {
		diff := r - mean
		sumSq += diff * diff
	}
	variance := sumSq / float64(len(returns)-1)

	if variance <= 0 {
		return 0.3
	}

	annual := math.Sqrt(variance) * math.Sqrt(252)
	if annual <= 0 || math.IsNaN(annual) || math.IsInf(annual, 0) {
		return 0.3
	}
	return annual
}
