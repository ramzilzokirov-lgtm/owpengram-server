package store

import "context"

// StarsStore exposes the VGRAM internal Stars ledger.
type StarsStore interface {
	Balance(ctx context.Context, userID int64) (int64, error)
}
