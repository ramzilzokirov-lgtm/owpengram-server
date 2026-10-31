package store

import "context"

// VirtualNumberStore is the durable allowlist and account binding for VGRAM bot-issued numbers.
type VirtualNumberStore interface {
	CanLogin(ctx context.Context, phone string, userID int64) (bool, error)
	Activate(ctx context.Context, phone string, userID int64) error
}
