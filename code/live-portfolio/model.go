package main

import "time"

// StockStatus holds the computed status for a single stock.
type StockStatus struct {
	Name         string       `json:"name"`
	Code         string       `json:"code"`
	CurrentPrice float64      `json:"currentPrice"`
	Change       float64      `json:"change"`
	Volatility   float64      `json:"volatility"`
	WinProb      float64      `json:"winProb"`
	WinLossRatio float64      `json:"winLossRatio"`
	KellyFrac    float64      `json:"kellyFrac"`
	SuggestedPos string       `json:"suggestedPos"`
	Signal       string       `json:"signal"`
	UpdatedAt    time.Time    `json:"updatedAt"`
	Points       []PricePoint `json:"points,omitempty"`
}

// PricePoint represents a single kline close price point.
type PricePoint struct {
	Time  int64   `json:"t"`
	Close float64 `json:"c"`
}

// DashboardResponse is the top-level API response.
type DashboardResponse struct {
	Stocks      []StockStatus `json:"stocks"`
	UpdatedAt   time.Time     `json:"updatedAt"`
	TotalPoints int           `json:"totalPoints"`
	Offline     bool          `json:"offline,omitempty"`
}
