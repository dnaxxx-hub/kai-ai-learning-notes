package main

// kellyFraction computes the half-Kelly fraction.
// winProb: probability of winning (up day)
// winLossRatio: average win / average loss
// Returns half-Kelly fraction capped at 0.25.
func kellyFraction(winProb, winLossRatio float64) float64 {
	if winLossRatio <= 0 || winProb <= 0 || winProb >= 1 {
		return 0
	}

	// Kelly formula: f* = (p * b - q) / b
	// where b = winLossRatio, p = winProb, q = 1 - p
	grossKelly := (winProb*winLossRatio - (1 - winProb)) / winLossRatio
	if grossKelly <= 0 {
		return 0
	}

	// Half Kelly
	halfKelly := grossKelly / 2
	if halfKelly > 0.25 {
		return 0.25
	}
	return halfKelly
}

// suggestPosition converts Kelly fraction to a human-readable suggestion and signal.
func suggestPosition(kelly float64, vol float64) (string, string) {
	if kelly <= 0 {
		return "观望", "→"
	}
	if kelly < 0.05 {
		return "轻仓", "→"
	}
	if kelly < 0.10 {
		return "持有", "↑"
	}
	if kelly < 0.20 {
		return "加仓", "↑↑"
	}
	return "重仓", "↑↑↑"
}
