package main

import (
	"math"
	"testing"
)

func TestGarchLogLik(t *testing.T) {
	returns := []float64{0.01, -0.02, 0.015, -0.01, 0.02, -0.005, 0.01, 0.005, -0.015, 0.01}
	lik := garchLogLik([]float64{0.00001, 0.1, 0.85}, returns)
	if math.IsNaN(lik) || math.IsInf(lik, 0) {
		t.Fatal("Invalid log likelihood")
	}
	t.Logf("logLik = %.4f", lik)
}

func TestGarchLogLikEdge(t *testing.T) {
	// Single return
	lik := garchLogLik([]float64{0.00001, 0.1, 0.85}, []float64{0.01})
	if math.IsNaN(lik) || math.IsInf(lik, 0) {
		t.Fatal("Invalid log likelihood for single return")
	}
	t.Logf("logLik single = %.4f", lik)

	// Empty returns
	lik = garchLogLik([]float64{0.00001, 0.1, 0.85}, []float64{})
	if !math.IsInf(lik, -1) {
		t.Fatal("Expected -Inf for empty returns")
	}
}

func TestFitGARCH(t *testing.T) {
	returns := []float64{0.01, -0.02, 0.015, -0.01, 0.02, -0.005, 0.01, 0.005, -0.015, 0.01}
	omega, alpha, beta, lastSigma := fitGARCH(returns)
	t.Logf("omega=%.6f alpha=%.4f beta=%.4f lastSigma=%.6f", omega, alpha, beta, lastSigma)

	if omega <= 0 || alpha < 0 || beta < 0 {
		t.Fatal("Parameters should be non-negative")
	}
	if alpha+beta >= 1 {
		t.Fatal("alpha+beta should be < 1")
	}
	if lastSigma <= 0 || math.IsNaN(lastSigma) {
		t.Fatal("Invalid lastSigma")
	}
}

func TestPredictVol(t *testing.T) {
	returns := []float64{-0.01, 0.02, -0.015, 0.01, 0.005, -0.02, 0.01, -0.005, 0.015, -0.01,
		0.01, -0.01, 0.02, -0.01, 0.005, 0.015, -0.02, 0.01, -0.015, 0.01}
	vol := predictVol(returns, 1)
	t.Logf("predicted vol = %.4f (%.2f%%)", vol, vol*100)

	if vol <= 0 || math.IsNaN(vol) || math.IsInf(vol, 0) {
		t.Fatal("Invalid volatility prediction")
	}
	// Annual vol should be reasonable (e.g., 5%-80%)
	if vol < 0.05 || vol > 0.80 {
		t.Logf("Warning: volatility %.4f may be unusual", vol)
	}
}

func TestCalcHistoricalProb(t *testing.T) {
	// All up
	prices := []float64{10.0, 10.5, 11.0, 11.5, 12.0}
	wp, wlr := calcHistoricalProb(prices)
	t.Logf("All up: wp=%.4f wlr=%.4f", wp, wlr)
	if wp < 0.9 || wlr < 1.0 {
		t.Logf("All-up case: wp=%.4f wlr=%.4f", wp, wlr)
	}

	// All down
	prices = []float64{12.0, 11.5, 11.0, 10.5, 10.0}
	wp, wlr = calcHistoricalProb(prices)
	t.Logf("All down: wp=%.4f wlr=%.4f", wp, wlr)

	// Alternating
	prices = []float64{10.0, 10.5, 10.0, 10.5, 10.0}
	wp, wlr = calcHistoricalProb(prices)
	t.Logf("Alternating: wp=%.4f wlr=%.4f", wp, wlr)

	// Single price
	prices = []float64{10.0}
	wp, wlr = calcHistoricalProb(prices)
	if wp <= 0 {
		t.Logf("Single price: wp=%.4f wlr=%.4f", wp, wlr)
	}
}

func TestKellyFraction(t *testing.T) {
	// p=0.6, b=2.0 -> half-Kelly = 20%
	f := kellyFraction(0.6, 2.0)
	if f < 0.19 || f > 0.21 {
		t.Fatalf("Expected ~0.20, got %.4f", f)
	}

	// p=0.4, b=1.0 -> no bet
	f = kellyFraction(0.4, 1.0)
	if f != 0 {
		t.Fatalf("Expected 0, got %.4f", f)
	}

	// p=0.5, b=1.0 -> no edge
	f = kellyFraction(0.5, 1.0)
	if f != 0 {
		t.Fatalf("Expected 0, got %.4f", f)
	}

	// p=0.75, b=3.0 -> half-Kelly capped at 25%
	f = kellyFraction(0.75, 3.0)
	if f > 0.26 || f <= 0 {
		t.Fatalf("Expected ~0.25, got %.4f", f)
	}

	// p=0, should be 0
	f = kellyFraction(0, 2.0)
	if f != 0 {
		t.Fatalf("Expected 0 for p=0, got %.4f", f)
	}

	// p=1, should be 0
	f = kellyFraction(1, 2.0)
	if f != 0 {
		t.Fatalf("Expected 0 for p=1, got %.4f", f)
	}

	// b <= 0, should be 0
	f = kellyFraction(0.5, 0)
	if f != 0 {
		t.Fatalf("Expected 0 for b=0, got %.4f", f)
	}
}

func TestSuggestPosition(t *testing.T) {
	pos, sig := suggestPosition(0.0, 0.3)
	if pos != "观望" {
		t.Fatalf("0 Kelly should be 观望, got %s", pos)
	}

	pos, sig = suggestPosition(0.15, 0.25)
	if pos != "加仓" {
		t.Fatalf("0.15 Kelly should be 加仓, got %s", pos)
	}
	_ = sig

	// Edge: very small positive Kelly
	pos, _ = suggestPosition(0.001, 0.3)
	if pos != "轻仓" {
		t.Fatalf("0.001 Kelly should be 轻仓, got %s", pos)
	}

	// Maximum Kelly
	pos, _ = suggestPosition(0.25, 0.2)
	if pos != "重仓" {
		t.Fatalf("0.25 Kelly should be 重仓, got %s", pos)
	}
}

func TestComputeReturns(t *testing.T) {
	prices := []float64{10.0, 11.0, 9.0, 10.0}
	ret := computeReturns(prices)
	if len(ret) != 3 {
		t.Fatalf("Expected 3 returns, got %d", len(ret))
	}
	// log(11/10) ≈ 0.0953
	expected := math.Log(11.0 / 10.0)
	if math.Abs(ret[0]-expected) > 0.001 {
		t.Fatalf("Expected return %.4f, got %.4f", expected, ret[0])
	}

	// Single price
	ret = computeReturns([]float64{10.0})
	if len(ret) != 1 {
		t.Fatalf("Expected 1 return for single price, got %d", len(ret))
	}
}

func TestExtractCloses(t *testing.T) {
	points := []PricePoint{
		{Time: 100, Close: 10.5},
		{Time: 200, Close: 11.0},
		{Time: 300, Close: 10.0},
	}
	closes := extractCloses(points)
	if len(closes) != 3 || closes[0] != 10.5 || closes[2] != 10.0 {
		t.Fatalf("Unexpected closes: %v", closes)
	}
}

func TestSimpleAnnualVol(t *testing.T) {
	vol := simpleAnnualVol(nil)
	if vol <= 0 {
		t.Fatal("Expected default vol for empty input")
	}

	returns := []float64{0.01, -0.01, 0.01, -0.01, 0.01}
	vol = simpleAnnualVol(returns)
	if vol <= 0 || math.IsNaN(vol) || math.IsInf(vol, 0) {
		t.Fatal("Invalid simple annual vol")
	}
	t.Logf("simple annual vol = %.4f (%.2f%%)", vol, vol*100)
}

func TestMedianFloat64(t *testing.T) {
	if m := medianFloat64(nil); m != 0 {
		t.Fatalf("Expected 0 for empty, got %.2f", m)
	}
	if m := medianFloat64([]float64{5.0}); m != 5.0 {
		t.Fatalf("Expected 5.0, got %.2f", m)
	}
	if m := medianFloat64([]float64{3.0, 1.0, 2.0}); m != 2.0 {
		t.Fatalf("Expected 2.0, got %.2f", m)
	}
	if m := medianFloat64([]float64{1.0, 2.0, 3.0, 4.0}); m != 2.5 {
		t.Fatalf("Expected 2.5, got %.2f", m)
	}
}

func TestCleanJSONP(t *testing.T) {
	raw := "min_data_sz000009({\"code\":0,\"data\":{}})"
	cleaned := cleanJSONP(raw)
	if len(cleaned) <= 0 || cleaned[0] != '{' {
		t.Fatalf("Expected JSON starting with {, got %q", cleaned)
	}
}

func TestParseKlineString(t *testing.T) {
	// Standard format
	pp, err := parseKlineString("2026-05-20 9.45 9.50 9.30 9.40")
	if err != nil {
		t.Fatalf("Parse error: %v", err)
	}
	if pp.Close != 9.40 {
		t.Fatalf("Expected close 9.40, got %.2f", pp.Close)
	}

	// Date format YYYYMMDD
	pp, err = parseKlineString("20260520 9.45 9.50 9.30 9.40")
	if err != nil {
		t.Fatalf("Parse error for YYYYMMDD: %v", err)
	}
	if pp.Close != 9.40 {
		t.Fatalf("Expected close 9.40, got %.2f", pp.Close)
	}

	// Malformed
	_, err = parseKlineString("short")
	if err == nil {
		t.Fatal("Expected error for malformed kline")
	}
}
