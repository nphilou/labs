package main

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestSummarizeItem(t *testing.T) {
	var result map[string]any
	err := json.Unmarshal([]byte(`{
		"display_name": "Cote Sushi",
		"items_available": 4,
		"item": {"price_including_taxes": {"minor_units": 1090, "decimals": 2, "code": "CHF"}},
		"pickup_interval": {"start": "2026-09-13T18:00:00+02:00", "end": "2026-09-13T18:30:00+02:00"},
		"pickup_location": {"address": {"address_line": "Rue du Test 1"}}
	}`), &result)
	if err != nil {
		t.Fatal(err)
	}

	summary := summarizeItem("1198174", result)
	if summary.DisplayName != "Cote Sushi" || summary.Available != 4 {
		t.Fatalf("unexpected summary: %+v", summary)
	}
	if summary.Price == nil || *summary.Price != 10.9 || summary.Currency != "CHF" {
		t.Fatalf("unexpected price: %v %s", summary.Price, summary.Currency)
	}
	if summary.Address != "Rue du Test 1" {
		t.Fatalf("unexpected address: %q", summary.Address)
	}
}

func TestAlertMessage(t *testing.T) {
	price := 10.9
	message := alertMessage(itemSummary{
		ItemID:      "1198174",
		DisplayName: "Cote Sushi",
		Available:   3,
		Price:       &price,
		Currency:    "CHF",
	})

	for _, expected := range []string{
		"Cote Sushi: 3 paniers available",
		"Price: 10.90 CHF",
		"Pickup: ? - ?",
		"https://share.toogoodtogo.com/item/1198174/",
	} {
		if !strings.Contains(message, expected) {
			t.Fatalf("message %q does not contain %q", message, expected)
		}
	}
}

func TestPriceAmountDefaultsToTwoDecimals(t *testing.T) {
	price, currency := priceAmount(map[string]any{
		"minor_units": float64(499),
		"code":        "CHF",
	})
	if price == nil || *price != 4.99 || currency != "CHF" {
		t.Fatalf("unexpected price: %v %s", price, currency)
	}
}

func TestOptionalCookieCanBeEmpty(t *testing.T) {
	t.Setenv("TGTG_COOKIE", "")
	if cookie := optionalCredential("", "TGTG_COOKIE"); cookie != "" {
		t.Fatalf("unexpected cookie: %q", cookie)
	}
}

func TestRedact(t *testing.T) {
	got := redact("Post https://api.telegram.org/botsecret/sendMessage failed", "secret")
	if strings.Contains(got, "secret") || !strings.Contains(got, "<redacted>") {
		t.Fatalf("token was not redacted: %q", got)
	}
}

func TestCompatibilityUserAgentMatchesAPKVersion(t *testing.T) {
	if !strings.Contains(compatibilityUserAgent, "TGTG/"+compatibilityAPKVersion+" ") {
		t.Fatalf("user agent %q does not match APK version %q", compatibilityUserAgent, compatibilityAPKVersion)
	}
}
