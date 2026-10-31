package postgres

import (
	"context"
	"fmt"

	"github.com/jackc/pgx/v5/pgxpool"
)

// VirtualNumberStore binds VGRAM-issued phone identities to the account that
// successfully completed its first registration.
type VirtualNumberStore struct {
	pool *pgxpool.Pool
}

func NewVirtualNumberStore(pool *pgxpool.Pool) *VirtualNumberStore {
	return &VirtualNumberStore{pool: pool}
}

func (s *VirtualNumberStore) CanLogin(ctx context.Context, phone string, userID int64) (bool, error) {
	if s == nil || s.pool == nil || phone == "" {
		return false, nil
	}
	var allowed bool
	err := s.pool.QueryRow(ctx, `
		SELECT EXISTS (
			SELECT 1
			FROM vgram_virtual_numbers
			WHERE phone = $1
			  AND (
				($2 = 0 AND status = 'issued' AND user_id IS NULL)
				OR ($2 > 0 AND status = 'active' AND user_id = $2)
			  )
		)`, phone, userID).Scan(&allowed)
	if err != nil {
		return false, fmt.Errorf("query VGRAM virtual number: %w", err)
	}
	return allowed, nil
}

func (s *VirtualNumberStore) Activate(ctx context.Context, phone string, userID int64) error {
	if s == nil || s.pool == nil || phone == "" || userID <= 0 {
		return fmt.Errorf("activate VGRAM virtual number: invalid input")
	}
	tag, err := s.pool.Exec(ctx, `
		UPDATE vgram_virtual_numbers
		SET status = 'active', user_id = $2, activated_at = now()
		WHERE phone = $1 AND status = 'issued' AND user_id IS NULL`, phone, userID)
	if err != nil {
		return fmt.Errorf("activate VGRAM virtual number: %w", err)
	}
	if tag.RowsAffected() == 1 {
		return nil
	}
	// Idempotent retry after the account row was committed but the caller
	// did not receive the activation acknowledgement.
	var alreadyActive bool
	if err := s.pool.QueryRow(ctx, `
		SELECT EXISTS (
			SELECT 1 FROM vgram_virtual_numbers
			WHERE phone = $1 AND status = 'active' AND user_id = $2
		)`, phone, userID).Scan(&alreadyActive); err != nil {
		return fmt.Errorf("verify VGRAM virtual number activation: %w", err)
	}
	if !alreadyActive {
		return fmt.Errorf("virtual number is unavailable or bound to another account")
	}
	return nil
}
