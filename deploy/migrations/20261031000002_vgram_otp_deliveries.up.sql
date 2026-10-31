CREATE TABLE vgram_otp_deliveries (
    delivery_id varchar(128) PRIMARY KEY,
    phone varchar(32) NOT NULL REFERENCES vgram_virtual_numbers(phone) ON DELETE CASCADE,
    request_fingerprint bytea NOT NULL,
    status text NOT NULL DEFAULT 'pending',
    telegram_message_id bigint,
    created_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz,
    expires_at timestamptz NOT NULL,
    CONSTRAINT vgram_otp_deliveries_fingerprint_size CHECK (octet_length(request_fingerprint) = 32),
    CONSTRAINT vgram_otp_deliveries_status_check CHECK (status IN ('pending', 'sent')),
    CONSTRAINT vgram_otp_deliveries_sent_check CHECK (
        (status = 'pending' AND telegram_message_id IS NULL AND sent_at IS NULL)
        OR (status = 'sent' AND telegram_message_id IS NOT NULL AND sent_at IS NOT NULL)
    )
);

CREATE INDEX vgram_otp_deliveries_expiry_idx ON vgram_otp_deliveries (expires_at);
