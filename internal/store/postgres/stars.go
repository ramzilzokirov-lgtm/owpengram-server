package postgres

import (
	"context"
	"fmt"

	"github.com/jackc/pgx/v5/pgxpool"
)

const initialVGRAMStars int64 = 1000

// StarsStore reads and initializes balances in the durable VGRAM Stars ledger.
type StarsStore struct {
	pool *pgxpool.Pool
}

func NewStarsStore(pool *pgxpool.Pool) *StarsStore {
	return &StarsStore{pool: pool}
}

// Balance grants the one-time welcome balance on first access and returns the
// committed balance. The grant flag and ledger row are updated atomically.
func (s *StarsStore) Balance(ctx context.Context, userID int64) (int64, error) {
	if s == nil || s.pool == nil || userID <= 0 {
		return 0, fmt.Errorf("read VGRAM Stars balance: invalid store or user")
	}
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return 0, fmt.Errorf("begin VGRAM Stars transaction: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	if _, err := tx.Exec(ctx, `
		INSERT INTO stars_balances (user_id, balance, granted)
		VALUES ($1, 0, false)
		ON CONFLICT (user_id) DO NOTHING
	`, userID); err != nil {
		return 0, fmt.Errorf("ensure VGRAM Stars balance: %w", err)
	}

	var balance int64
	var granted bool
	if err := tx.QueryRow(ctx, `
		SELECT balance, granted
		FROM stars_balances
		WHERE user_id = $1
		FOR UPDATE
	`, userID).Scan(&balance, &granted); err != nil {
		return 0, fmt.Errorf("lock VGRAM Stars balance: %w", err)
	}

	if !granted {
		balance += initialVGRAMStars
		if _, err := tx.Exec(ctx, `
			UPDATE stars_balances
			SET balance = $2, granted = true, updated_at = now()
			WHERE user_id = $1
		`, userID, balance); err != nil {
			return 0, fmt.Errorf("grant initial VGRAM Stars: %w", err)
		}
		if _, err := tx.Exec(ctx, `
			INSERT INTO stars_transactions
				(user_id, amount, reason, title, description, date)
			VALUES ($1, $2, 'registration_grant', 'VGRAM Welcome Bonus',
				'Initial 1,000 VGRAM Stars', EXTRACT(EPOCH FROM now())::integer)
		`, userID, initialVGRAMStars); err != nil {
			return 0, fmt.Errorf("record initial VGRAM Stars grant: %w", err)
		}
	}

	if err := tx.Commit(ctx); err != nil {
		return 0, fmt.Errorf("commit VGRAM Stars balance: %w", err)
	}
	return balance, nil
}
