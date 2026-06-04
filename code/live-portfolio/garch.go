package main

import (
	"math"
	"sort"
)

// garchLogLik computes the log-likelihood for GARCH(1,1) with parameters theta[0]=omega,
// theta[1]=alpha, theta[2]=beta.
func garchLogLik(theta []float64, returns []float64) float64 {
	omega, alpha, beta := theta[0], theta[1], theta[2]

	// Parameter constraints (soft — likelihood will penalize)
	if omega <= 0 || alpha < 0 || beta < 0 || alpha+beta >= 1 {
		return math.Inf(-1)
	}

	n := len(returns)
	if n == 0 {
		return math.Inf(-1)
	}

	// Initialize with unconditional variance
	varVar := 0.0
	for _, r := range returns {
		varVar += r * r
	}
	varVar /= float64(n)
	if varVar <= 0 {
		varVar = 1e-6
	}

	sigma2 := make([]float64, n)
	sigma2[0] = varVar

	loglik := -0.5 * (math.Log(2*math.Pi) + math.Log(sigma2[0]) + returns[0]*returns[0]/sigma2[0])

	for t := 1; t < n; t++ {
		sigma2[t] = omega + alpha*returns[t-1]*returns[t-1] + beta*sigma2[t-1]
		if sigma2[t] <= 0 {
			sigma2[t] = 1e-8
		}
		loglik -= 0.5 * (math.Log(2*math.Pi) + math.Log(sigma2[t]) + returns[t]*returns[t]/sigma2[t])
	}

	return loglik
}

// fitGARCH performs grid search over GARCH(1,1) parameter space, then refines with
// coordinate ascent. Returns omega, alpha, beta, and last conditional variance.
func fitGARCH(returns []float64) (omega, alpha, beta, lastSigma float64) {
	// Grid search: 6×6×6 = 216 evaluations
	omegaGrid := []float64{1e-6, 5e-6, 1e-5, 5e-5, 1e-4, 5e-4}
	alphaGrid := []float64{0.02, 0.05, 0.10, 0.15, 0.25, 0.40}
	betaGrid := []float64{0.50, 0.65, 0.75, 0.85, 0.92, 0.97}

	bestLik := math.Inf(-1)
	bestOmega, bestAlpha, bestBeta := 1e-5, 0.1, 0.85

	for _, ow := range omegaGrid {
		for _, al := range alphaGrid {
			for _, be := range betaGrid {
				if al+be >= 1 {
					continue
				}
				lik := garchLogLik([]float64{ow, al, be}, returns)
				if lik > bestLik {
					bestLik = lik
					bestOmega, bestAlpha, bestBeta = ow, al, be
				}
			}
		}
	}

	// Coordinate ascent refinement (simple hill climbing)
	params := []float64{bestOmega, bestAlpha, bestBeta}
	stepSizes := []float64{1e-7, 0.01, 0.01}
	improved := true

	for iter := 0; iter < 50 && improved; iter++ {
		improved = false
		for i := 0; i < 3; i++ {
			// Try positive step
			candidate := make([]float64, 3)
			copy(candidate, params)
			candidate[i] += stepSizes[i]
			if candidate[i] > 0 && (i == 0 || candidate[1]+candidate[2] < 1) {
				lik := garchLogLik(candidate, returns)
				if lik > bestLik {
					bestLik = lik
					params[i] = candidate[i]
					improved = true
				}
			}
			// Try negative step
			candidate2 := make([]float64, 3)
			copy(candidate2, params)
			candidate2[i] -= stepSizes[i]
			if candidate2[i] > 0 && (i == 0 || candidate2[1]+candidate2[2] < 1) {
				lik := garchLogLik(candidate2, returns)
				if lik > bestLik {
					bestLik = lik
					params[i] = candidate2[i]
					improved = true
				}
			}
		}
		// Shrink step size
		for i := range stepSizes {
			stepSizes[i] *= 0.8
		}
	}

	omega, alpha, beta = params[0], params[1], params[2]

	// Compute final sigma2 sequence to get last conditional variance
	varVar := 0.0
	for _, r := range returns {
		varVar += r * r
	}
	varVar /= float64(len(returns))
	if varVar <= 0 {
		varVar = 1e-6
	}

	n := len(returns)
	sigma2 := make([]float64, n)
	sigma2[0] = varVar
	for t := 1; t < n; t++ {
		sigma2[t] = omega + alpha*returns[t-1]*returns[t-1] + beta*sigma2[t-1]
		if sigma2[t] <= 0 {
			sigma2[t] = 1e-8
		}
	}
	lastSigma = math.Sqrt(sigma2[n-1])

	return omega, alpha, beta, lastSigma
}

// predictVol predicts annualized volatility.
// Returns annualized volatility (as a decimal, e.g. 0.25 = 25%).
func predictVol(returns []float64, nDays int) float64 {
	_, _, _, lastSigma := fitGARCH(returns)

	// Annualize: σ_annual = σ_daily × √252
	annualSigma := lastSigma * math.Sqrt(252)
	return annualSigma
}

// calcHistoricalProb computes win probability and win/loss ratio from close prices.
// winProb = number of up days / total days
// winLossRatio = average positive return / average negative return (absolute)
func calcHistoricalProb(closePrices []float64) (winProb, winLossRatio float64) {
	if len(closePrices) < 2 {
		return 0.5, 1.0
	}

	var wins, losses int
	var totalWin, totalLoss float64

	for i := 1; i < len(closePrices); i++ {
		ret := (closePrices[i] - closePrices[i-1]) / closePrices[i-1]
		if ret > 0 {
			wins++
			totalWin += ret
		} else if ret < 0 {
			losses++
			totalLoss += -ret
		}
	}

	total := wins + losses
	if total == 0 {
		return 0.5, 1.0
	}

	winProb = float64(wins) / float64(total)

	if wins > 0 && losses > 0 {
		avgWin := totalWin / float64(wins)
		avgLoss := totalLoss / float64(losses)
		if avgLoss > 0 {
			winLossRatio = avgWin / avgLoss
		} else {
			winLossRatio = 1.0
		}
	} else if wins > 0 {
		winLossRatio = 2.0 // All wins — favorable but cap it
	} else {
		winLossRatio = 0.5 // All losses
	}

	return winProb, winLossRatio
}

// computeReturns converts close prices to log returns.
func computeReturns(prices []float64) []float64 {
	if len(prices) < 2 {
		return []float64{0}
	}
	ret := make([]float64, len(prices)-1)
	for i := 1; i < len(prices); i++ {
		if prices[i-1] > 0 {
			ret[i-1] = math.Log(prices[i] / prices[i-1])
		} else {
			ret[i-1] = 0
		}
	}
	return ret
}

// extractCloses extracts close prices from PricePoint slice.
func extractCloses(points []PricePoint) []float64 {
	prices := make([]float64, len(points))
	for i, p := range points {
		prices[i] = p.Close
	}
	return prices
}

// medianFloat64 computes the median of a float64 slice.
func medianFloat64(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}
	sorted := make([]float64, len(values))
	copy(sorted, values)
	sort.Float64s(sorted)
	mid := len(sorted) / 2
	if len(sorted)%2 == 0 {
		return (sorted[mid-1] + sorted[mid]) / 2.0
	}
	return sorted[mid]
}
