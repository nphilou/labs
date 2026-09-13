package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	tgtg "github.com/mikispag/tgtg-go"
)

const (
	defaultItemID        = "1198174"
	defaultMinStock      = 3
	defaultMaxPrice      = 11.0
	defaultStatePath     = "/var/lib/labs-tgtg-monitor/state.json"
	defaultHTTPTimeout   = 30 * time.Second
	versionCheckInterval = 24 * time.Hour
	fallbackAPKVersion   = "26.9.4"
	modernUserAgent      = "TGTG/%s Dalvik/2.1.0 (Linux; U; Android 17; Pixel 8 Pro Build/CP2A.260705.006)"
)

type monitorState struct {
	Credentials          tgtg.Credentials `json:"credentials,omitempty"`
	LastTokenRefreshTime *time.Time       `json:"last_token_refresh_time,omitempty"`
	LastAlertKey         string           `json:"last_alert_key,omitempty"`
	LastStatus           string           `json:"last_status,omitempty"`
	LastSeen             *lastSeen        `json:"last_seen,omitempty"`
	APKVersion           string           `json:"apk_version,omitempty"`
	APKVersionCheckedAt  *time.Time       `json:"apk_version_checked_at,omitempty"`
}

type lastSeen struct {
	ItemID      string   `json:"item_id"`
	DisplayName string   `json:"display_name"`
	Available   int      `json:"available"`
	Price       *float64 `json:"price"`
	Currency    string   `json:"currency"`
	Qualifies   bool     `json:"qualifies"`
}

type itemSummary struct {
	ItemID      string
	DisplayName string
	Available   int
	Price       *float64
	Currency    string
	PickupStart string
	PickupEnd   string
	Address     string
}

func main() {
	if err := run(context.Background()); err != nil {
		fmt.Fprintf(os.Stderr, "tgtg monitor failed: %v\n", err)
		os.Exit(1)
	}
}

func run(ctx context.Context) error {
	itemID := envOrDefault("TGTG_MONITOR_ITEM_ID", defaultItemID)
	minStock, err := envInt("TGTG_MONITOR_MIN_AVAILABLE", defaultMinStock)
	if err != nil {
		return err
	}
	maxPrice, err := envFloat("TGTG_MONITOR_MAX_PRICE_CHF", defaultMaxPrice)
	if err != nil {
		return err
	}
	statePath := envOrDefault("TGTG_MONITOR_STATE", defaultStatePath)

	state, err := loadState(statePath)
	if err != nil {
		return err
	}
	accessToken, err := credential(state.Credentials.AccessToken, "TGTG_ACCESS_TOKEN")
	if err != nil {
		return err
	}
	refreshToken, err := credential(state.Credentials.RefreshToken, "TGTG_REFRESH_TOKEN")
	if err != nil {
		return err
	}
	cookie := optionalCredential(state.Credentials.Cookie, "TGTG_COOKIE")
	apkVersion, userAgent, versionErr := resolveClientIdentity(ctx, &state, time.Now(), tgtg.GetLastAPKVersion)
	if versionErr != nil {
		fmt.Fprintf(os.Stderr, "failed to discover current TGTG app version; using %s: %v\n", apkVersion, versionErr)
	}
	fmt.Fprintf(os.Stderr, "using TGTG app identity version %s\n", apkVersion)

	clientConfig := tgtg.Config{
		AccessToken:  accessToken,
		RefreshToken: refreshToken,
		Cookie:       cookie,
		APKVersion:   apkVersion,
		UserAgent:    userAgent,
		Timeout:      defaultHTTPTimeout,
		Output:       os.Stderr,
	}
	if state.LastTokenRefreshTime != nil {
		clientConfig.LastTimeTokenRefreshed = *state.LastTokenRefreshTime
	}
	client := tgtg.New(clientConfig)

	result, requestErr := client.GetItem(ctx, itemID)
	updateCredentials(&state, client)
	if requestErr != nil {
		var apiError *tgtg.APIError
		if errors.As(requestErr, &apiError) && apiError.StatusCode == http.StatusForbidden {
			state.LastStatus = "captcha_challenged"
			if saveErr := saveState(statePath, state); saveErr != nil {
				return saveErr
			}
			fmt.Fprintf(os.Stderr, "tgtg monitor skipped this cycle after a persistent DataDome challenge: %v\n", requestErr)
			return nil
		}
		if saveErr := saveState(statePath, state); saveErr != nil {
			return errors.Join(fmt.Errorf("get item %s: %w", itemID, requestErr), saveErr)
		}
		return fmt.Errorf("get item %s: %w", itemID, requestErr)
	}

	summary := summarizeItem(itemID, result)
	qualifies := summary.Available >= minStock && summary.Price != nil &&
		summary.Currency == "CHF" && *summary.Price < maxPrice
	alertKey := makeAlertKey(summary)

	needsAlert := qualifies && state.LastAlertKey != alertKey
	if !qualifies {
		state.LastStatus = "below_threshold"
	}

	state.LastSeen = &lastSeen{
		ItemID:      summary.ItemID,
		DisplayName: summary.DisplayName,
		Available:   summary.Available,
		Price:       summary.Price,
		Currency:    summary.Currency,
		Qualifies:   qualifies,
	}
	// Persist rotated credentials before contacting Telegram. If notification
	// delivery fails, the next cycle can still authenticate and retry the alert.
	if err := saveState(statePath, state); err != nil {
		return err
	}

	if needsAlert {
		if err := sendTelegram(ctx, alertMessage(summary)); err != nil {
			return err
		}
		state.LastAlertKey = alertKey
		state.LastStatus = "alerted"
		if err := saveState(statePath, state); err != nil {
			return err
		}
	}

	price := "<unknown>"
	if summary.Price != nil {
		price = strconv.FormatFloat(*summary.Price, 'f', -1, 64)
	}
	fmt.Printf("%s: available=%d price=%s %s qualifies=%t\n",
		summary.DisplayName, summary.Available, price, summary.Currency, qualifies)
	return nil
}

func resolveClientIdentity(
	ctx context.Context,
	state *monitorState,
	now time.Time,
	fetchVersion func(context.Context) (string, error),
) (string, string, error) {
	apkVersion := strings.TrimSpace(os.Getenv("TGTG_APK_VERSION"))
	var fetchErr error
	if apkVersion == "" {
		apkVersion = strings.TrimSpace(state.APKVersion)
		needsRefresh := apkVersion == "" || state.APKVersionCheckedAt == nil ||
			now.Sub(*state.APKVersionCheckedAt) >= versionCheckInterval
		if needsRefresh {
			if discovered, err := fetchVersion(ctx); err != nil {
				fetchErr = err
			} else if discovered = strings.TrimSpace(discovered); discovered != "" {
				apkVersion = discovered
				checkedAt := now
				state.APKVersion = discovered
				state.APKVersionCheckedAt = &checkedAt
			}
		}
	}
	if apkVersion == "" {
		apkVersion = fallbackAPKVersion
	}

	userAgent := strings.TrimSpace(os.Getenv("TGTG_USER_AGENT"))
	if userAgent == "" {
		userAgent = fmt.Sprintf(modernUserAgent, apkVersion)
	}
	return apkVersion, userAgent, fetchErr
}

func updateCredentials(state *monitorState, client *tgtg.Client) {
	state.Credentials = tgtg.Credentials{
		AccessToken:  client.AccessToken,
		RefreshToken: client.RefreshToken,
		Cookie:       client.Cookie,
	}
	if refreshed := client.LastTimeTokenRefreshed; !refreshed.IsZero() {
		state.LastTokenRefreshTime = &refreshed
	}
}

func loadState(path string) (monitorState, error) {
	data, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return monitorState{}, nil
	}
	if err != nil {
		return monitorState{}, fmt.Errorf("read state: %w", err)
	}
	var state monitorState
	if err := json.Unmarshal(data, &state); err != nil {
		fmt.Fprintf(os.Stderr, "tgtg monitor ignored invalid state: %v\n", err)
		return monitorState{}, nil
	}
	return state, nil
}

func saveState(path string, state monitorState) error {
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return fmt.Errorf("create state directory: %w", err)
	}
	temporary, err := os.CreateTemp(dir, ".state-*.json")
	if err != nil {
		return fmt.Errorf("create temporary state: %w", err)
	}
	temporaryPath := temporary.Name()
	defer os.Remove(temporaryPath)

	if err := temporary.Chmod(0o600); err != nil {
		temporary.Close()
		return fmt.Errorf("protect temporary state: %w", err)
	}
	encoder := json.NewEncoder(temporary)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(state); err != nil {
		temporary.Close()
		return fmt.Errorf("encode state: %w", err)
	}
	if err := temporary.Close(); err != nil {
		return fmt.Errorf("close temporary state: %w", err)
	}
	if err := os.Rename(temporaryPath, path); err != nil {
		return fmt.Errorf("replace state: %w", err)
	}
	return nil
}

func requiredEnv(name string) (string, error) {
	value := strings.TrimSpace(os.Getenv(name))
	if value == "" {
		return "", fmt.Errorf("%s is required", name)
	}
	return value, nil
}

func credential(saved, environmentName string) (string, error) {
	if value := strings.TrimSpace(saved); value != "" {
		return value, nil
	}
	return requiredEnv(environmentName)
}

func optionalCredential(saved, environmentName string) string {
	if value := strings.TrimSpace(saved); value != "" {
		return value
	}
	return strings.TrimSpace(os.Getenv(environmentName))
}

func envOrDefault(name, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(name)); value != "" {
		return value
	}
	return fallback
}

func envInt(name string, fallback int) (int, error) {
	value := strings.TrimSpace(os.Getenv(name))
	if value == "" {
		return fallback, nil
	}
	parsed, err := strconv.Atoi(value)
	if err != nil {
		return 0, fmt.Errorf("parse %s: %w", name, err)
	}
	return parsed, nil
}

func envFloat(name string, fallback float64) (float64, error) {
	value := strings.TrimSpace(os.Getenv(name))
	if value == "" {
		return fallback, nil
	}
	parsed, err := strconv.ParseFloat(value, 64)
	if err != nil {
		return 0, fmt.Errorf("parse %s: %w", name, err)
	}
	return parsed, nil
}

func summarizeItem(itemID string, result map[string]any) itemSummary {
	item := object(result["item"])
	store := object(result["store"])
	pickup := object(result["pickup_interval"])
	pickupLocation := object(result["pickup_location"])
	address := object(pickupLocation["address"])

	price, currency := priceAmount(firstObject(item["price_including_taxes"], item["item_price"]))
	displayName := text(result["display_name"])
	if displayName == "" {
		displayName = text(store["store_name"])
	}
	if displayName == "" {
		displayName = "TGTG item " + itemID
	}

	return itemSummary{
		ItemID:      itemID,
		DisplayName: displayName,
		Available:   integer(result["items_available"]),
		Price:       price,
		Currency:    currency,
		PickupStart: text(pickup["start"]),
		PickupEnd:   text(pickup["end"]),
		Address:     text(address["address_line"]),
	}
}

func priceAmount(value map[string]any) (*float64, string) {
	currency := text(value["code"])
	minorUnits, ok := number(value["minor_units"])
	if !ok {
		return nil, currency
	}
	decimals := integer(value["decimals"])
	if _, exists := value["decimals"]; !exists {
		decimals = 2
	}
	amount := minorUnits / pow10(decimals)
	return &amount, currency
}

func makeAlertKey(summary itemSummary) string {
	price := "<unknown>"
	if summary.Price != nil {
		price = strconv.FormatFloat(*summary.Price, 'f', -1, 64)
	}
	return strings.Join([]string{
		summary.ItemID,
		strconv.Itoa(summary.Available),
		price,
		summary.PickupStart,
		summary.PickupEnd,
	}, ":")
}

func alertMessage(summary itemSummary) string {
	price := "?"
	if summary.Price != nil {
		price = strconv.FormatFloat(*summary.Price, 'f', 2, 64)
	}
	return strings.Join([]string{
		fmt.Sprintf("%s: %d paniers available", summary.DisplayName, summary.Available),
		fmt.Sprintf("Price: %s %s", price, summary.Currency),
		fmt.Sprintf("Pickup: %s - %s", fallback(summary.PickupStart, "?"), fallback(summary.PickupEnd, "?")),
		"Address: " + summary.Address,
		"https://share.toogoodtogo.com/item/" + url.PathEscape(summary.ItemID) + "/",
	}, "\n")
}

func sendTelegram(ctx context.Context, message string) error {
	if os.Getenv("TGTG_MONITOR_DRY_RUN") == "1" {
		fmt.Println(message)
		return nil
	}
	token, err := requiredEnv("TELEGRAM_BOT_TOKEN")
	if err != nil {
		return err
	}
	chatID, err := requiredEnv("TELEGRAM_CHAT_ID")
	if err != nil {
		return err
	}

	form := url.Values{
		"chat_id":                  {chatID},
		"text":                     {message},
		"disable_web_page_preview": {"true"},
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodPost,
		"https://api.telegram.org/bot"+token+"/sendMessage", strings.NewReader(form.Encode()))
	if err != nil {
		return fmt.Errorf("create Telegram request: %s", redact(err.Error(), token))
	}
	request.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	response, err := (&http.Client{Timeout: 20 * time.Second}).Do(request)
	if err != nil {
		return fmt.Errorf("send Telegram message: %s", redact(err.Error(), token))
	}
	defer response.Body.Close()
	if response.StatusCode >= http.StatusBadRequest {
		return fmt.Errorf("Telegram send failed with HTTP %d", response.StatusCode)
	}
	return nil
}

func object(value any) map[string]any {
	result, _ := value.(map[string]any)
	return result
}

func firstObject(values ...any) map[string]any {
	for _, value := range values {
		if result := object(value); result != nil {
			return result
		}
	}
	return nil
}

func text(value any) string {
	result, _ := value.(string)
	return result
}

func number(value any) (float64, bool) {
	switch typed := value.(type) {
	case float64:
		return typed, true
	case float32:
		return float64(typed), true
	case int:
		return float64(typed), true
	case int64:
		return float64(typed), true
	case json.Number:
		parsed, err := typed.Float64()
		return parsed, err == nil
	default:
		return 0, false
	}
}

func integer(value any) int {
	n, _ := number(value)
	return int(n)
}

func pow10(exponent int) float64 {
	result := 1.0
	for range exponent {
		result *= 10
	}
	return result
}

func fallback(value, alternative string) string {
	if value == "" {
		return alternative
	}
	return value
}

func redact(value, secret string) string {
	if secret == "" {
		return value
	}
	return strings.ReplaceAll(value, secret, "<redacted>")
}
