package auth

import (
	"context"
	"testing"

	"telesrv/internal/domain"
	"telesrv/internal/store/memory"
)

type fakeVirtualNumberRegistry struct {
	allowed bool
	checks  []int64
	phone   string
	userID  int64
}

func (r *fakeVirtualNumberRegistry) CanLogin(_ context.Context, phone string, userID int64) (bool, error) {
	r.phone = phone
	r.checks = append(r.checks, userID)
	return r.allowed, nil
}

func (r *fakeVirtualNumberRegistry) Activate(_ context.Context, phone string, userID int64) error {
	r.phone = phone
	r.userID = userID
	return nil
}

func TestVirtualNumberRegistryRejectsUnissuedNumberBeforeCodeCreation(t *testing.T) {
	ctx := context.Background()
	registry := &fakeVirtualNumberRegistry{allowed: false}
	codes := memory.NewCodeStore()
	svc := NewService(
		memory.NewUserStore(),
		memory.NewAuthorizationStore(),
		codes,
		nil,
		nil,
		"12345",
		WithVirtualNumberRegistry(registry),
	)

	if hash, err := svc.SendCode(ctx, "+888 123 456 789"); hash != "" || err != ErrVirtualNumberUnavailable {
		t.Fatalf("SendCode hash=%q err=%v, want empty/ErrVirtualNumberUnavailable", hash, err)
	}
	if len(registry.checks) != 1 || registry.checks[0] != 0 {
		t.Fatalf("registry checks = %v, want one unbound-number check", registry.checks)
	}
}

func TestVirtualNumberRegistryActivatesNumberAfterVerifiedSignUp(t *testing.T) {
	ctx := context.Background()
	registry := &fakeVirtualNumberRegistry{allowed: true}
	users := memory.NewUserStore()
	svc := NewService(
		users,
		memory.NewAuthorizationStore(),
		memory.NewCodeStore(),
		nil,
		nil,
		"12345",
		WithVirtualNumberRegistry(registry),
	)

	phone := "888123456789"
	hash, err := svc.SendCode(ctx, phone)
	if err != nil || hash == "" {
		t.Fatalf("SendCode hash=%q err=%v", hash, err)
	}
	var authKey [8]byte
	authKey[0] = 0x71
	if _, _, needSignUp, err := svc.SignIn(ctx, domain.Authorization{AuthKeyID: authKey}, phone, hash, "12345"); err != nil || !needSignUp {
		t.Fatalf("SignIn needSignUp=%v err=%v, want signup required", needSignUp, err)
	}
	u, _, err := svc.SignUp(ctx, domain.Authorization{AuthKeyID: authKey}, phone, hash, "VGRAM", "User")
	if err != nil {
		t.Fatalf("SignUp: %v", err)
	}
	if registry.userID != u.ID || registry.phone != phone {
		t.Fatalf("registry activation phone=%q user=%d, want %q/%d", registry.phone, registry.userID, phone, u.ID)
	}
	stored, found, err := users.ByPhone(ctx, phone)
	if err != nil || !found || stored.ID != u.ID {
		t.Fatalf("stored user=%+v found=%v err=%v", stored, found, err)
	}
}

func TestVirtualNumberRegistryRechecksBeforeSignUp(t *testing.T) {
	ctx := context.Background()
	registry := &fakeVirtualNumberRegistry{allowed: true}
	svc := NewService(
		memory.NewUserStore(),
		memory.NewAuthorizationStore(),
		memory.NewCodeStore(),
		nil,
		nil,
		"12345",
		WithVirtualNumberRegistry(registry),
	)
	phone := "888123456780"
	hash, err := svc.SendCode(ctx, phone)
	if err != nil {
		t.Fatalf("SendCode: %v", err)
	}
	var authKey [8]byte
	authKey[0] = 0x72
	if _, _, needSignUp, err := svc.SignIn(ctx, domain.Authorization{AuthKeyID: authKey}, phone, hash, "12345"); err != nil || !needSignUp {
		t.Fatalf("SignIn needSignUp=%v err=%v", needSignUp, err)
	}
	registry.allowed = false
	if _, _, err := svc.SignUp(ctx, domain.Authorization{AuthKeyID: authKey}, phone, hash, "VGRAM", "User"); err != ErrVirtualNumberUnavailable {
		t.Fatalf("SignUp err=%v, want ErrVirtualNumberUnavailable", err)
	}
}
