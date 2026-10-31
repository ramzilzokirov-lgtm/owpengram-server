CREATE TABLE vgram_virtual_numbers (
    phone varchar(32) PRIMARY KEY,
    telegram_user_id bigint NOT NULL,
    telegram_chat_id bigint NOT NULL,
    status text NOT NULL DEFAULT 'issued',
    user_id bigint UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    revoked_at timestamptz,
    last_code_sent_at timestamptz,
    CONSTRAINT vgram_virtual_numbers_phone_digits CHECK (phone ~ '^[0-9]{5,32}$'),
    CONSTRAINT vgram_virtual_numbers_status_check CHECK (status IN ('issued', 'active', 'revoked')),
    CONSTRAINT vgram_virtual_numbers_activation_check CHECK (
        (status = 'issued' AND user_id IS NULL AND activated_at IS NULL)
        OR (status = 'active' AND user_id IS NOT NULL AND activated_at IS NOT NULL)
        OR status = 'revoked'
    ),
    CONSTRAINT vgram_virtual_numbers_telegram_user_unique UNIQUE (telegram_user_id)
);

CREATE INDEX vgram_virtual_numbers_chat_idx ON vgram_virtual_numbers (telegram_chat_id);
CREATE INDEX vgram_virtual_numbers_status_created_idx ON vgram_virtual_numbers (status, created_at DESC);
