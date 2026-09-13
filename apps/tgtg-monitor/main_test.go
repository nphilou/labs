package main

import (
	"context"
	"encoding/json"
	"errors"
	"strings"
	"testing"
	"time"
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

func TestResolveClientIdentityDiscoversAndCachesVersion(t *testing.T) {
	t.Setenv("TGTG_APK_VERSION", "")
	t.Setenv("TGTG_USER_AGENT", "")
	now := time.Date(2026, 9, 13, 20, 0, 0, 0, time.UTC)
	state := monitorState{}
	fetches := 0

	apkVersion, userAgent, err := resolveClientIdentity(context.Background(), &state, now, func(context.Context) (string, error) {
		fetches++
		return "26.9.4", nil
	})
	if err != nil {
		t.Fatal(err)
	}
	if apkVersion != "26.9.4" || !strings.Contains(userAgent, "TGTG/26.9.4 ") {
		t.Fatalf("unexpected identity: %q %q", apkVersion, userAgent)
	}
	if fetches != 1 || state.APKVersion != apkVersion || state.APKVersionCheckedAt == nil {
		t.Fatalf("version was not cached: fetches=%d state=%+v", fetches, state)
	}

	apkVersion, _, err = resolveClientIdentity(context.Background(), &state, now.Add(time.Hour), func(context.Context) (string, error) {
		fetches++
		return "99.0.0", nil
	})
	if err != nil || apkVersion != "26.9.4" || fetches != 1 {
		t.Fatalf("fresh cached version was not reused: version=%q fetches=%d err=%v", apkVersion, fetches, err)
	}
}

func TestResolveClientIdentityFallsBack(t *testing.T) {
	t.Setenv("TGTG_APK_VERSION", "")
	t.Setenv("TGTG_USER_AGENT", "")
	state := monitorState{}
	wantErr := errors.New("offline")

	apkVersion, userAgent, err := resolveClientIdentity(context.Background(), &state, time.Now(), func(context.Context) (string, error) {
		return "", wantErr
	})
	if !errors.Is(err, wantErr) || apkVersion != fallbackAPKVersion {
		t.Fatalf("unexpected fallback: version=%q err=%v", apkVersion, err)
	}
	if !strings.Contains(userAgent, "TGTG/"+fallbackAPKVersion+" ") {
		t.Fatalf("user agent %q does not match fallback version", userAgent)
	}
}
